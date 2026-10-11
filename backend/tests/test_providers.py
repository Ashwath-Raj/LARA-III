import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ubuntu_agent.database import Database
from ubuntu_agent.models import Actor
from ubuntu_agent.provider_config import ProviderConfig
from ubuntu_agent.providers import (
    GeminiProvider,
    OllamaProvider,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderRouter,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ubuntu_agent.services import PolicyDeniedError, TaskService, ValidationError
from ubuntu_agent.task_capture import TaskCaptureService, _validate_candidate


ACTOR = Actor("local-user", "task_deadline_manager")


def provider_config(**kwargs):
    values = {"default_provider": "ollama", "ollama_model": "gemma4:e2b-it-q4_K_M", "ollama_timeout": 2,
              "gemini_model": "gemma-4-26b-a4b-it", "gemini_timeout": 2, "gemini_api_key": None}
    values.update(kwargs)
    return ProviderConfig(**values)


def task_json(**changes):
    value = {"title": "Study algorithms", "description": "", "priority": "normal",
             "category": "Academics", "due_date": "2027-11-07", "due_at": None,
             "timezone": "Asia/Kolkata", "item_type": "assignment"}
    value.update(changes)
    return json.dumps(value)


class FakeProvider:
    def __init__(self, provider_id="ollama", output=None, error=None):
        self.provider_id, self.model_id = provider_id, "fake-model"
        self.output, self.error, self.calls = output, error, []

    def generate_text(self, prompt, *, response_schema=None):
        self.calls.append((prompt, response_schema))
        if self.error:
            raise self.error
        from ubuntu_agent.providers import GenerationResult
        return GenerationResult(self.provider_id, self.model_id, self.output or "OK")


class ProviderTests(unittest.TestCase):
    def test_default_provider_is_local_and_provider_failure_never_falls_back(self):
        local = FakeProvider(error=ProviderUnavailableError("offline"))
        cloud = FakeProvider("gemini")
        router = ProviderRouter(provider_config(), ollama=local, gemini=cloud)
        self.assertEqual("ollama", router.selected(None))
        with self.assertRaises(ProviderUnavailableError):
            router.generate_task_capture("private", ACTOR)
        self.assertEqual(1, len(local.calls))
        self.assertEqual([], cloud.calls)

    def test_ollama_network_error_timeout_and_bad_response_are_sanitized(self):
        cfg = provider_config()
        with self.assertRaises(ProviderUnavailableError):
            OllamaProvider(cfg, lambda _request, _timeout: (_ for _ in ()).throw(ConnectionRefusedError("secret"))).generate_text("hi")
        with self.assertRaises(ProviderTimeoutError):
            OllamaProvider(cfg, lambda _request, _timeout: (_ for _ in ()).throw(TimeoutError("private prompt"))).generate_text("hi")
        with self.assertRaises(ProviderResponseError):
            OllamaProvider(cfg, lambda _request, _timeout: b"not json").generate_text("hi")

    def test_ollama_sends_non_streaming_schema_constrained_request(self):
        seen = []
        def transport(request, timeout):
            seen.append((request.full_url, json.loads(request.data), timeout))
            return b'{"response":"{}"}'
        adapter = OllamaProvider(provider_config(), transport)
        adapter.generate_text("task text", response_schema={"type": "object"})
        url, body, timeout = seen[0]
        self.assertFalse(body["stream"])
        self.assertEqual({"type": "object"}, body["format"])
        self.assertEqual({"temperature": 0}, body["options"])
        self.assertEqual(2, timeout)
        self.assertEqual("http://127.0.0.1:11434/api/generate", url)

    def test_gemini_missing_key_and_auth_failure_are_sanitized(self):
        with self.assertRaises(ProviderConfigurationError):
            GeminiProvider(provider_config()).generate_text("safe")

        class SecretAuthError(Exception):
            code = 401
        # Exercise the SDK exception mapping without importing or calling the SDK.
        class Models:
            def generate_content(self, **_kwargs):
                raise SecretAuthError("API_KEY=not-for-logs private prompt")
        class Client:
            models = Models()
        adapter = GeminiProvider(provider_config(gemini_api_key="secret-never-reported"), client=Client())
        with patch("ubuntu_agent.providers.GeminiProvider._client_or_raise", return_value=adapter._client):
            with self.assertRaises(ProviderAuthenticationError) as raised:
                adapter.generate_text("sensitive prompt")
        self.assertNotIn("not-for-logs", str(raised.exception))
        self.assertNotIn("sensitive prompt", str(raised.exception))

    def test_gemini_timeout_and_invalid_response_errors(self):
        class Models:
            def __init__(self, response): self.response = response
            def generate_content(self, **_kwargs):
                if isinstance(self.response, Exception): raise self.response
                return self.response
        class Client:
            def __init__(self, response): self.models = Models(response)
        with self.assertRaises(ProviderTimeoutError):
            GeminiProvider(provider_config(gemini_api_key="key"), Client(TimeoutError())).generate_text("safe")
        with self.assertRaises(ProviderResponseError):
            GeminiProvider(provider_config(gemini_api_key="key"), Client(object())).generate_text("safe")

    def test_candidate_json_is_strict_and_checks_categories_dates_and_fields(self):
        cats = {"Academics", "Projects"}
        candidate, _ = _validate_candidate(task_json(), "Due 2027-11-07", cats)
        self.assertEqual("2027-11-07", candidate.due_date)
        for invalid in (task_json(category="Injected"), task_json(due_date="2027-02-30"),
                        task_json(priority="impossible"), task_json(timezone="Unknown/Zone"),
                        task_json(due_date="2027-11-08"),
                        task_json()[:-1] + ', "room_id":"health"}',
                        task_json()[:-1] + ', "title":"Overwritten"}'):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                _validate_candidate(invalid, "Due 2027-11-07", cats)

    def test_ambiguous_dates_and_timezones_are_cleared_and_asked(self):
        candidate, questions = _validate_candidate(task_json(), "Assignment due November 7", {"Academics"})
        self.assertIsNone(candidate.due_date)
        self.assertTrue(any("year" in question for question in questions))
        candidate, questions = _validate_candidate(
            task_json(due_date=None, due_at="2027-11-07T14:00:00Z"),
            "Meet the deadline on 2027-11-07 at 2pm", {"Academics"})
        self.assertIsNone(candidate.due_at)
        self.assertTrue(any("timezone" in question for question in questions))
        candidate, questions = _validate_candidate(
            task_json(due_at=None), "Assignment due 2027-11-07 at 7", {"Academics"})
        self.assertEqual("2027-11-07", candidate.due_date)
        self.assertTrue(any("morning or evening" in question for question in questions))
        candidate, questions = _validate_candidate(
            task_json(due_at="2027-11-07T14:00:00Z", timezone="UTC"),
            "Assignment due 2027-11-07 at 14:00 UTC", {"Academics"})
        self.assertEqual("2027-11-07T14:00:00Z", candidate.due_at)
        self.assertEqual((), questions)
        with self.assertRaises(ValidationError):
            _validate_candidate(task_json(due_at="2027-11-07T13:00:00Z", timezone="UTC"),
                                "Assignment due 2027-11-07 at 14:00 UTC", {"Academics"})

    def test_preview_is_non_persisting_and_provider_cannot_set_security_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "agent.sqlite3")
            db.initialize()
            fake = FakeProvider(output=task_json())
            router = ProviderRouter(provider_config(), ollama=fake, gemini=FakeProvider("gemini"))
            capture = TaskCaptureService(db, router)
            preview = capture.capture_task("Assignment due 2027-11-07", ACTOR)
            self.assertTrue(preview.requires_confirmation)
            self.assertEqual("ollama", preview.provider_id)
            self.assertEqual("fake-model", preview.model_id)
            self.assertEqual([], TaskService(db).list_tasks(ACTOR))
            self.assertIn("Allowed categories:", fake.calls[0][0])

            for key, value in (("room_id", "health"), ("persona_id", "desktop_operator"),
                               ("sensitivity_label", "public"), ("permissions", ["shell.execute"]),
                               ("status", "done")):
                malicious = FakeProvider(output=task_json()[:-1] + ", " + json.dumps(key) + ":" + json.dumps(value) + "}")
                with self.subTest(metadata=key), self.assertRaises(ValidationError):
                    TaskCaptureService(db, ProviderRouter(provider_config(), ollama=malicious)).capture_task(
                        "Assignment due 2027-11-07", ACTOR)
            self.assertEqual([], TaskService(db).list_tasks(ACTOR))

    def test_cloud_task_capture_denied_before_provider_receives_prompt_even_with_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "agent.sqlite3")
            db.initialize()
            cloud = FakeProvider("gemini")
            capture = TaskCaptureService(db, ProviderRouter(provider_config(), gemini=cloud))
            for opted_in in (False, True):
                with self.subTest(opted_in=opted_in), self.assertRaises(PolicyDeniedError):
                    capture.capture_task("private assignment information", ACTOR, provider="gemini",
                                         cloud_opt_in=opted_in)
            self.assertEqual([], cloud.calls)

    def test_confirmation_calls_existing_task_service_and_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "agent.sqlite3")
            db.initialize()
            router = ProviderRouter(provider_config(), ollama=FakeProvider(output=task_json()))
            capture = TaskCaptureService(db, router)
            preview = capture.capture_task("Assignment due 2027-11-07", ACTOR)
            with self.assertRaises(ValidationError):
                capture.confirm_and_create(preview, ACTOR, confirmed=False)
            created = capture.confirm_and_create(preview, ACTOR, confirmed=True, idempotency_key="capture-1")
            self.assertEqual("Study algorithms", created["title"])
            self.assertEqual("operations", created["room_id"])
            with self.assertRaises(PolicyDeniedError):
                capture.confirm_and_create(preview, Actor("local-user", "desktop_operator"), confirmed=True)
            self.assertEqual(1, len(TaskService(db).list_tasks(ACTOR)))

    def test_cloud_health_check_uses_only_generic_prompt_and_status_redacts_credentials(self):
        local = FakeProvider()
        local_result = ProviderRouter(provider_config(), ollama=local).health_check(None, ACTOR)
        self.assertEqual("ollama", local_result.provider_id)
        self.assertEqual("Reply with the single word OK.", local.calls[0][0])

        cloud = FakeProvider("gemini")
        router = ProviderRouter(provider_config(gemini_api_key="must-not-print"), gemini=cloud)
        result = router.health_check("gemini", ACTOR)
        self.assertEqual("gemini", result.provider_id)
        self.assertEqual("Reply with the single word OK.", cloud.calls[0][0])

        out = io.StringIO()
        with patch.dict("os.environ", {"GEMINI_API_KEY": "must-not-print"}), redirect_stdout(out):
            from ubuntu_agent.cli import main
            self.assertEqual(0, main(["provider-status"]))
        self.assertNotIn("must-not-print", out.getvalue())
        self.assertIn('"gemini"', out.getvalue())

    def test_environment_key_loading_is_environment_first_and_config_repr_is_redacted(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "environment-only"}, clear=True), \
                patch("ubuntu_agent.provider_config._project_env_value", return_value="dotenv-only"):
            config = ProviderConfig.from_environment()
        self.assertEqual("environment-only", config.gemini_api_key)
        self.assertNotIn("environment-only", repr(config))
        with patch.dict("os.environ", {}, clear=True), \
                patch("ubuntu_agent.provider_config._project_env_value", return_value="dotenv-only"):
            self.assertEqual("dotenv-only", ProviderConfig.from_environment().gemini_api_key)

    def test_manual_task_cli_does_not_load_or_require_provider_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with patch.dict("os.environ", {"UBUNTU_AGENT_DEFAULT_PROVIDER": "gemini",
                                           "OLLAMA_TIMEOUT_SECONDS": "invalid"}), redirect_stdout(output):
                from ubuntu_agent.cli import main
                self.assertEqual(0, main(["--db", str(Path(temp) / "cli.sqlite3"), "task-create", "Offline task"]))
            self.assertIn("Offline task", output.getvalue())


if __name__ == "__main__":
    unittest.main()
