import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ubuntu_agent.bootstrap import seed_trusted_state
from ubuntu_agent.cli import main
from ubuntu_agent.database import MIGRATIONS, Database
from ubuntu_agent.desktop.actions import validate_action
from ubuntu_agent.desktop.capabilities import detect_desktop_capabilities
from ubuntu_agent.desktop.grounding import parse_grounding_payload
from ubuntu_agent.loop.graph import LoopGraph
from ubuntu_agent.loop.orchestrator import LoopOrchestrator, ROLE_NAMES
from ubuntu_agent.loop.role_protocol import ROLE_SCHEMAS
from ubuntu_agent.models import Actor
from ubuntu_agent.providers import (
    GeminiProvider,
    GenerationResult,
    OllamaProvider,
    ProviderUnavailableError,
)
from ubuntu_agent.services import ConflictError, ValidationError


class FakeOllama:
    provider_id = "ollama"
    model_id = "fake-model"

    def __init__(self):
        self.calls = []

    def generate_text(self, prompt, *, response_schema=None):
        self.calls.append((prompt, response_schema))
        payloads = {
            "blue_team": {
                "recommended_solution": "Use a bounded local workflow.",
                "assumptions": ["The local provider is available."],
                "constraints": ["Keep the task in the local workspace."],
                "expected_outcomes": ["Persist each role result."],
                "claims_requiring_evidence": ["The workflow meets its budget."],
            },
            "red_team": {
                "counterarguments": ["A local model may be unavailable."],
                "failure_modes": ["The provider can time out."],
                "security_concerns": ["Untrusted prompt content may be misleading."],
                "missing_cases": ["Process interruption."],
                "unsupported_assumptions": ["Every call will succeed."],
            },
            "judge": {
                "accepted_arguments": ["Provider failure is possible."],
                "rejected_arguments": [],
                "revised_arguments": ["Record uncertainty explicitly."],
                "final_recommendation": "Persist role outputs and require review on failure.",
                "rationale": "This responds to the proposal and critique.",
                "unresolved_objections": ["The local model may be unavailable."],
                "confidence_limitations": ["No grounded sources were supplied."],
                "evidence_gaps": ["No grounded evidence was ingested."],
                "evidence_references": [],
            },
            "unbiased_reviewer": {
                "verdict": "pass",
                "reasons": ["The synthesis addresses the proposal and critique."],
                "unsupported_claims": ["The actual runtime still requires verification."],
                "potential_bias": ["The same local model produced every role output."],
                "unanswered_questions": ["How will the workflow behave after a process restart?"],
            },
        }
        role = next(name for name, schema in ROLE_SCHEMAS.items() if schema == response_schema)
        payload = payloads[role]
        return GenerationResult(self.provider_id, self.model_id, json.dumps(payload))


class DesktopLoopTests(unittest.TestCase):
    def test_desktop_capability_detection_is_honest_without_display(self):
        caps = detect_desktop_capabilities({"XDG_SESSION_TYPE": "tty"})
        self.assertEqual("unsupported", caps.session_type)
        self.assertTrue(any("display session" in item for item in caps.blockers))
        self.assertFalse(caps.pointer_keyboard)

    def test_action_validation_rejects_shell_commands_and_sensitive_fields(self):
        with self.assertRaises(Exception):
            validate_action({"type": "open_url", "url": "https://example.com", "command": "rm -rf /"})
        with self.assertRaises(Exception):
            validate_action({"type": "type_text", "text": "secret", "field_hint": "one-time password"})
        normalized = validate_action({"type": "move_pointer", "x": 10, "y": 20, "label": "Save", "confidence": 0.9})
        self.assertEqual(10.0, normalized["x"])
        self.assertEqual("Save", normalized["label"])

    def test_visual_grounding_validates_window_and_bounds(self):
        payload = {
            "label": "Submit",
            "bounding_box": {"x": 0.25, "y": 0.25, "width": 0.2, "height": 0.1},
            "confidence": 0.9,
            "reasoning_summary": "Center of the CTA",
            "window_id": "window-1",
        }
        target = parse_grounding_payload(payload, screenshot_width=1000, screenshot_height=800,
                                        window_id="window-1", expected_window_id="window-1")
        self.assertEqual(350, target.screen_x)
        self.assertEqual(240, target.screen_y)
        with self.assertRaises(Exception):
            parse_grounding_payload({"label": "Bad", "bounding_box": {"x": 0.0, "y": 0.0, "width": 1.1, "height": 0.1},
                                    "confidence": 0.9, "reasoning_summary": "bad"}, screenshot_width=1000, screenshot_height=800)

    def test_loop_roles_are_persisted_and_cancellation_marks_loop_closed(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "loop.sqlite3")
            db.initialize()
            actor = Actor("local-user", "desktop_operator")
            orchestrator = LoopOrchestrator(db, ollama=FakeOllama())
            loop = orchestrator.create_loop(actor, goal="Review a draft", constraints=["Be evidence-based."], max_rounds=4)
            self.assertEqual(set(ROLE_NAMES), {row["role_name"] for row in loop["roles"]})
            with db.connect() as connection:
                rows = connection.execute("SELECT role_name, status FROM loop_roles WHERE loop_id=? ORDER BY role_name", (loop["id"],)).fetchall()
                self.assertEqual("pending", rows[0]["status"])
            cancelled = orchestrator.cancel(loop["id"], actor)
            self.assertEqual("cancelled", cancelled["status"])

    def test_loop_graph_keeps_data_isolated_by_loop(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "graph.sqlite3")
            db.initialize()
            with db.connect() as connection:
                connection.execute("INSERT INTO ai_loops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                   ("loop-1", "operations", "desktop_operator", "Goal one",
                                    "[]", "ollama_api", 0, "created", 4, None,
                                    "2027-01-01T00:00:00Z", "2027-01-01T00:00:00Z", None))
                connection.execute("INSERT INTO ai_loops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                   ("loop-2", "operations", "desktop_operator", "Goal two",
                                    "[]", "ollama_api", 0, "created", 4, None,
                                    "2027-01-01T00:00:00Z", "2027-01-01T00:00:00Z", None))
            graph = LoopGraph(db)
            node1 = graph.add_node("loop-1", "goal", "Goal one", "Goal text", room_id="operations", sensitivity="internal")
            graph.add_node("loop-2", "goal", "Goal two", "Other goal", room_id="operations", sensitivity="internal")
            self.assertEqual(1, len(graph.nodes("loop-1")))
            self.assertEqual(1, len(graph.nodes("loop-2")))
            self.assertEqual("Goal text", graph.get_node("loop-1", node1["id"])["content"])

    def test_database_migration_installs_loop_roles_schema(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "schema.sqlite3")
            db.initialize()
            with db.connect() as connection:
                names = {row["name"] for row in connection.execute("PRAGMA table_info(loop_roles)").fetchall()}
                self.assertIn("role_name", names)
                self.assertIn("loop_id", names)

    def test_existing_v5_database_receives_loop_roles_without_losing_loops(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "legacy-v5.sqlite3")
            with db.connect() as connection:
                connection.execute(
                    "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
                )
                for version, migration in MIGRATIONS:
                    if version > 5:
                        break
                    Database._execute_statements(connection, migration)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, "2026-10-11T00:00:00Z"),
                    )
                seed_trusted_state(connection)
                connection.execute(
                    "INSERT INTO ai_loops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("legacy-loop", "operations", "desktop_operator", "Existing loop",
                     "[]", "ollama_api", 0, "created", 4, None,
                     "2026-10-11T00:00:00Z", "2026-10-11T00:00:00Z", None),
                )

            db.initialize()
            actor = Actor("local-user", "desktop_operator")
            loop = LoopOrchestrator(db, ollama=FakeOllama()).create_loop(
                actor, goal="Loop created after migration", max_rounds=4
            )
            with db.connect() as connection:
                version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
                existing = connection.execute(
                    "SELECT goal FROM ai_loops WHERE id='legacy-loop'"
                ).fetchone()
                role_count = connection.execute(
                    "SELECT COUNT(*) FROM loop_roles WHERE loop_id=?", (loop["id"],)
                ).fetchone()[0]
            self.assertEqual(max(version for version, _ in MIGRATIONS), version)
            self.assertEqual("Existing loop", existing["goal"])
            self.assertEqual(4, role_count)

    def test_pre_release_v5_loop_roles_table_is_preserved_by_migration_six(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "preview-v5.sqlite3")
            with db.connect() as connection:
                connection.execute(
                    "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
                )
                for version, migration in MIGRATIONS:
                    if version > 5:
                        break
                    Database._execute_statements(connection, migration)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, "2026-10-11T00:00:00Z"),
                    )
                for version in (6, 7):
                    Database._execute_statements(connection, next(sql for item_version, sql in MIGRATIONS if item_version == version))
                    connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                                       (version, "2026-10-11T00:00:00Z"))
            db.initialize()
            with db.connect() as connection:
                self.assertEqual(
                    max(version for version, _ in MIGRATIONS), connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
                )
                self.assertIsNotNone(connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='loop_roles'"
                ).fetchone())

    def test_loop_run_debate_writes_rounds_and_synthesis(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "debate.sqlite3")
            db.initialize()
            actor = Actor("local-user", "desktop_operator")
            fake_ollama = FakeOllama()
            orchestrator = LoopOrchestrator(db, ollama=fake_ollama)
            loop = orchestrator.create_loop(actor, goal="Assess the plan", constraints=["Keep it short."])
            result = orchestrator.run_debate(loop["id"], actor)
            self.assertEqual("succeeded", result["status"])
            self.assertEqual(4, len(result["rounds"]))
            self.assertTrue(all(row["status"] == "succeeded" for row in result["rounds"]))
            self.assertTrue(fake_ollama.calls)
            self.assertTrue(all(role["status"] == "succeeded" for role in result["roles"]))
            self.assertEqual(4, sum(len(role["executions"]) for role in result["roles"]))
            self.assertTrue(all(row["job_id"] is None for row in result["rounds"]))
            with db.connect() as connection:
                self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            with self.assertRaises(ConflictError):
                orchestrator.run_debate(loop["id"], actor)
            self.assertEqual("succeeded", orchestrator.get_loop(loop["id"], actor)["status"])
            self.assertEqual(4, len(orchestrator.get_loop(loop["id"], actor)["rounds"]))

    def test_loop_run_cli_configures_local_adapter_without_cloud_fallback(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "cli-loop.sqlite3"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(0, main([
                    "--db", str(db_path), "--persona", "desktop_operator",
                    "loop-create", "Review a local-only test plan", "--max-rounds", "4",
                ]))
            loop_id = json.loads(output.getvalue())["id"]
            responses = {
                "blue_team": {
                    "recommended_solution": "Use local inference.",
                    "assumptions": [], "constraints": [], "expected_outcomes": [],
                    "claims_requiring_evidence": [],
                },
                "red_team": {
                    "counterarguments": [], "failure_modes": [], "security_concerns": [],
                    "missing_cases": [], "unsupported_assumptions": [],
                },
                "judge": {
                    "accepted_arguments": [], "rejected_arguments": [], "revised_arguments": [],
                    "final_recommendation": "Use local inference.", "rationale": "The proposal is safe.",
                    "unresolved_objections": [], "confidence_limitations": [],
                    "evidence_gaps": [], "evidence_references": [],
                },
                "unbiased_reviewer": {
                    "verdict": "pass", "reasons": [], "unsupported_claims": [],
                    "potential_bias": [], "unanswered_questions": [],
                },
            }
            def local_response(prompt, *, response_schema=None):
                role = next(name for name, schema in ROLE_SCHEMAS.items() if schema == response_schema)
                return GenerationResult("ollama", "test-model", json.dumps(responses[role]))
            with (
                patch.dict("os.environ", {
                    "UBUNTU_AGENT_DEFAULT_PROVIDER": "ollama",
                    "UBUNTU_AGENT_FALLBACK_POLICY": "local_only",
                    "UBUNTU_AGENT_ALLOW_EXTERNAL": "false",
                }),
                patch.object(OllamaProvider, "generate_text", side_effect=local_response) as ollama,
                patch.object(GeminiProvider, "generate_text",
                             side_effect=AssertionError("cloud provider invoked")) as gemini,
                redirect_stdout(output := io.StringIO()),
            ):
                self.assertEqual(0, main([
                    "--db", str(db_path), "--persona", "desktop_operator", "loop-run", loop_id,
                ]))
            result = json.loads(output.getvalue())
            self.assertEqual(loop_id, result["id"])
            self.assertEqual("succeeded", result["status"])
            self.assertEqual(4, ollama.call_count)
            gemini.assert_not_called()
            for _ in range(2):
                with redirect_stdout(output := io.StringIO()):
                    self.assertEqual(0, main([
                        "--db", str(db_path), "--persona", "desktop_operator", "loop-show", loop_id,
                    ]))
                inspected = json.loads(output.getvalue())
                self.assertEqual(loop_id, inspected["id"])
                self.assertEqual(4, len(inspected["rounds"]))
            reopened = Database(db_path)
            with reopened.connect() as connection:
                self.assertEqual(4, connection.execute(
                    "SELECT COUNT(*) FROM loop_rounds WHERE loop_id=? AND status='succeeded'",
                    (loop_id,),
                ).fetchone()[0])
                self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    def test_model_failure_persists_failed_loop_and_round_states(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "failed-loop.sqlite3")
            db.initialize()

            class FailingOllama:
                provider_id = "ollama"
                model_id = "test-model"

                def generate_text(self, prompt, *, response_schema=None):
                    raise ProviderUnavailableError("Local inference unavailable.")

            actor = Actor("local-user", "desktop_operator")
            orchestrator = LoopOrchestrator(db, ollama=FailingOllama())
            loop = orchestrator.create_loop(actor, goal="Check failure persistence", max_rounds=4)
            with self.assertRaises(ValidationError):
                orchestrator.run_debate(loop["id"], actor)
            persisted = orchestrator.get_loop(loop["id"], actor)
            self.assertEqual("failed", persisted["status"])
            self.assertEqual(["failed"], [round_row["status"] for round_row in persisted["rounds"]])
            self.assertEqual("failed", next(
                role["status"] for role in persisted["roles"] if role["role_name"] == "blue_team"
            ))
            self.assertTrue(all(
                role["status"] == "pending" for role in persisted["roles"]
                if role["role_name"] != "blue_team"
            ))

    def test_cancellation_during_inference_is_not_overwritten_by_completion(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db = Database(Path(tempdir) / "cancel-loop.sqlite3")
            db.initialize()
            actor = Actor("local-user", "desktop_operator")
            orchestrator = LoopOrchestrator(db)

            class CancellingOllama(FakeOllama):
                def generate_text(self, prompt, *, response_schema=None):
                    orchestrator.cancel(loop_id, actor)
                    return super().generate_text(prompt, response_schema=response_schema)

            orchestrator.ollama = CancellingOllama()
            loop = orchestrator.create_loop(actor, goal="Check cancellation persistence", max_rounds=4)
            loop_id = loop["id"]
            result = orchestrator.run_debate(loop_id, actor)
            self.assertEqual("cancelled", result["status"])
            self.assertEqual(["cancelled"], [round_row["status"] for round_row in result["rounds"]])
            self.assertFalse(any(item["artifact_type"] == "final_prompt"
                                 for item in orchestrator.artifacts(loop_id, actor)))
