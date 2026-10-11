import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from ubuntu_agent.api import ApiError, MAX_REQUEST_BYTES, ApiSessionService, PairingRateLimiter, configured_origins, create_app
from ubuntu_agent.cli import main
from ubuntu_agent.database import Database
from ubuntu_agent.loop.orchestrator import LoopOrchestrator
from ubuntu_agent.loop.role_protocol import ROLE_SCHEMAS
from ubuntu_agent.memory import MemoryService
from ubuntu_agent.models import Actor
from ubuntu_agent.providers import GenerationResult

ORIGIN = "http://localhost:5173"


class FakeLocalProvider:
    provider_id = "ollama"
    model_id = "api-test-model"

    def generate_text(self, prompt, *, response_schema=None):
        role = next(name for name, schema in ROLE_SCHEMAS.items() if schema == response_schema)
        outputs = {
            "blue_team": {
                "recommended_solution": "A bounded local workflow.",
                "assumptions": [],
                "constraints": [],
                "expected_outcomes": [],
                "claims_requiring_evidence": [],
            },
            "red_team": {
                "counterarguments": [],
                "failure_modes": [],
                "security_concerns": [],
                "missing_cases": [],
                "unsupported_assumptions": [],
            },
            "judge": {
                "accepted_arguments": [],
                "rejected_arguments": [],
                "revised_arguments": [],
                "final_recommendation": "Proceed locally.",
                "rationale": "The proposal is bounded.",
                "unresolved_objections": [],
                "confidence_limitations": [],
                "evidence_gaps": [],
                "evidence_references": [],
            },
            "unbiased_reviewer": {
                "verdict": "pass",
                "reasons": ["The output is bounded."],
                "unsupported_claims": [],
                "potential_bias": [],
                "unanswered_questions": [],
            },
        }
        return GenerationResult(self.provider_id, self.model_id, json.dumps(outputs[role]))


class FakeConversationMemory:
    def __init__(self):
        self.indexed = []
        self.deleted = []
        self.hits = []

    def search_memory(self, query, purpose, actor, **kwargs):
        return list(self.hits)

    def ingest_document(self, path, actor, room_id):
        self.indexed.append((str(path), room_id))
        return {"document_id": "fake-memory-document", "status": "ready"}

    def delete_document(self, document_id, actor):
        self.deleted.append(document_id)
        return {"document_id": document_id, "status": "deleted"}


class TinyEmbedder:
    model = "api-memory-fake"
    dimensions = 3

    def embed(self, texts):
        return [[float(len(text)), 1.0, 2.0] for text in texts]


class TinyVectorStore:
    dimensions = 3

    def __init__(self):
        self.items = {}
        self.fail_delete = False

    def upsert(self, points):
        self.items.update({point["id"]:point for point in points})

    def search(self, vector, *, room_ids, limit):
        return [(point_id, 0.9) for point_id in list(self.items)[:limit]]

    def contains(self, point_ids):
        return [point_id for point_id in point_ids if point_id in self.items]

    def delete(self, point_ids):
        if self.fail_delete:
            raise RuntimeError("simulated vector deletion outage")
        for point_id in point_ids:
            self.items.pop(point_id, None)

    def reset(self, dimensions):
        self.items.clear()


class TestApiContract(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Database(f"{self.tempdir.name}/api.sqlite3")
        self.database.initialize()
        self.actor = Actor("local-user", "desktop_operator")
        self.orchestrator = LoopOrchestrator(self.database, ollama=FakeLocalProvider())
        self.memory = FakeConversationMemory()
        self.app = create_app(
            self.database,
            loop_orchestrator=self.orchestrator,
            allowed_origins=(ORIGIN, "http://127.0.0.1:5173"),
            provider_probe=lambda: {"status": "model_missing", "provider": "ollama", "model": "test"},
            conversation_generator=lambda prompt, actor, room: GenerationResult("ollama", "test-gemma", "Persisted local answer."),
            memory_service=self.memory,
        )
        self.client = TestClient(self.app, base_url="http://localhost:8765")
        self.pairing_token, self.expires_at = ApiSessionService(
            self.database, (ORIGIN, "http://127.0.0.1:5173")
        ).issue_pairing_token([ORIGIN])
        response = self.client.post(
            "/api/v1/auth/session",
            json={"pairing_token": self.pairing_token},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(200, response.status_code, response.text)

    def tearDown(self):
        self.client.close()
        self.tempdir.cleanup()

    def test_health_and_readiness_are_honest_and_do_not_run_inference(self):
        health = self.client.get("/api/v1/health")
        ready = self.client.get("/api/v1/ready")
        self.assertEqual("alive", health.json()["status"])
        self.assertEqual("implemented", health.json()["capabilities"]["conversations"])
        self.assertEqual(200, ready.status_code)
        self.assertEqual("ready", ready.json()["database"])
        self.assertEqual("model_missing", ready.json()["local_model"]["status"])
        self.assertEqual("not_initialized", ready.json()["vector_store"]["status"])

    def test_conversation_persists_user_and_assistant_turns(self):
        created = self.client.post("/api/v1/conversations", json={}, headers={"Origin": ORIGIN})
        self.assertEqual(201, created.status_code, created.text)
        conversation_id = created.json()["id"]
        reply = self.client.post(f"/api/v1/conversations/{conversation_id}/messages",
                                 json={"content":"Remember that my project is called Aurora."},
                                 headers={"Origin": ORIGIN})
        self.assertEqual(200, reply.status_code, reply.text)
        self.assertEqual("Persisted local answer.", reply.json()["content"])
        messages = self.client.get(f"/api/v1/conversations/{conversation_id}/messages",
                                   headers={"Origin": ORIGIN}).json()
        self.assertEqual(["user", "assistant"], [message["sender"] for message in messages])
        self.assertEqual("complete", messages[0]["status"])
        self.assertEqual("indexed", reply.json()["memory_status"])
        self.assertEqual(1, len(self.memory.indexed))
        self.assertEqual(2, self.client.get("/api/v1/conversations", headers={"Origin": ORIGIN}).json()[0]["message_count"])

    def test_conversation_memory_can_be_disabled_and_excluded(self):
        conversation_id = self.client.post("/api/v1/conversations", json={}, headers={"Origin": ORIGIN}).json()["id"]
        response = self.client.post(f"/api/v1/conversations/{conversation_id}/messages",
                                    json={"content":"A non-secret durable fact."}, headers={"Origin":ORIGIN,"Idempotency-Key":"conversation-once-001"})
        self.assertEqual(200, response.status_code, response.text)
        repeated = self.client.post(f"/api/v1/conversations/{conversation_id}/messages",
                                    json={"content":"A non-secret durable fact."}, headers={"Origin":ORIGIN,"Idempotency-Key":"conversation-once-001"})
        self.assertEqual(response.json()["id"], repeated.json()["id"])
        self.assertEqual(2, len(self.client.get(f"/api/v1/conversations/{conversation_id}/messages", headers={"Origin":ORIGIN}).json()))
        message_id = self.client.get(f"/api/v1/conversations/{conversation_id}/messages", headers={"Origin":ORIGIN}).json()[0]["id"]
        excluded = self.client.post(f"/api/v1/conversations/{conversation_id}/memory/{message_id}/exclude", headers={"Origin":ORIGIN})
        self.assertEqual("excluded", excluded.json()["status"])
        disabled = self.client.patch(f"/api/v1/conversations/{conversation_id}", json={"memory_enabled":False}, headers={"Origin":ORIGIN})
        self.assertEqual(False, disabled.json()["memory_enabled"])
        self.assertEqual([], self.memory.deleted)

    def test_excluding_a_memory_invalidates_indexed_answers_derived_from_it(self):
        vectors = TinyVectorStore()
        memory = MemoryService(self.database, TinyEmbedder(), vectors, data_dir=self.tempdir.name)
        app = create_app(
            self.database,
            loop_orchestrator=self.orchestrator,
            allowed_origins=(ORIGIN,),
            provider_probe=lambda: {"status":"available", "provider":"ollama", "model":"test"},
            conversation_generator=lambda prompt, actor, room: GenerationResult("ollama", "test-gemma", "The code is QA-SHARD-971."),
            memory_service=memory,
        )
        client = TestClient(app, base_url="http://localhost:8765")
        token, _ = ApiSessionService(self.database, (ORIGIN,)).issue_pairing_token([ORIGIN])
        paired = client.post("/api/v1/auth/session", json={"pairing_token":token}, headers={"Origin":ORIGIN})
        self.assertEqual(200, paired.status_code, paired.text)
        headers = {"Origin":ORIGIN}
        source_conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()
        source_reply = client.post(f"/api/v1/conversations/{source_conversation['id']}/messages",
                                   json={"content":"Remember the test code QA-SHARD-971."}, headers=headers)
        self.assertEqual("indexed", source_reply.json()["memory_status"])
        derived_conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()
        derived_reply = client.post(f"/api/v1/conversations/{derived_conversation['id']}/messages",
                                    json={"content":"What was the test code?"}, headers=headers)
        self.assertEqual(source_conversation["id"], derived_reply.json()["retrieved_memories"][0]["conversation_id"])
        with self.database.connect() as connection:
            source_row = connection.execute("SELECT user_message_id,document_id FROM conversation_memory_sources WHERE conversation_id=?",
                                            (source_conversation["id"],)).fetchone()
            derived_document = connection.execute("SELECT document_id FROM conversation_memory_sources WHERE conversation_id=?",
                                                  (derived_conversation["id"],)).fetchone()[0]
        vectors.fail_delete = True
        excluded = client.post(f"/api/v1/conversations/{source_conversation['id']}/memory/{source_row['user_message_id']}/exclude",
                               headers=headers)
        self.assertEqual("excluded", excluded.json()["status"])
        with self.database.connect() as connection:
            statuses = {row["document_id"]:row["status"] for row in connection.execute(
                "SELECT document_id,status FROM conversation_memory_sources WHERE document_id IN (?,?)",
                (source_row["document_id"], derived_document))}
        self.assertEqual({source_row["document_id"]:"excluded", derived_document:"excluded"}, statuses)
        self.assertEqual([], memory.search_memory("QA-SHARD-971", "after source exclusion",
                                                  Actor("local-user", "task_deadline_manager")))
        client.close()

    def test_detected_secret_exchange_is_never_indexed(self):
        conversation_id = self.client.post("/api/v1/conversations", json={}, headers={"Origin":ORIGIN}).json()["id"]
        response = self.client.post(f"/api/v1/conversations/{conversation_id}/messages",
                                    json={"content":"password: DoNotStoreThis123"}, headers={"Origin":ORIGIN})
        self.assertEqual("excluded", response.json()["memory_status"])
        self.assertEqual([], self.memory.indexed)

    def test_task_delete_is_persistent_and_scoped(self):
        created = self.client.post("/api/v1/tasks", json={"title":"Delete me","category":"Personal / Admin",
            "room_id":"operations","priority":"normal","timezone":"UTC"}, headers={"Origin":ORIGIN})
        self.assertEqual(201, created.status_code, created.text)
        task_id = created.json()["id"]
        self.assertEqual(204, self.client.delete(f"/api/v1/tasks/{task_id}", headers={"Origin":ORIGIN}).status_code)
        self.assertEqual(404, self.client.get(f"/api/v1/tasks/{task_id}", headers={"Origin":ORIGIN}).status_code)

    def test_projects_link_tasks_and_calendar_events_persist_with_timezone(self):
        project = self.client.post("/api/v1/projects", json={"name":"Aurora project","room_id":"operations"}, headers={"Origin":ORIGIN})
        self.assertEqual(201, project.status_code, project.text)
        project_id = project.json()["id"]
        task = self.client.post("/api/v1/tasks", json={"title":"Project task","category":"Projects","room_id":"operations",
            "priority":"normal","timezone":"UTC","project_id":project_id}, headers={"Origin":ORIGIN})
        self.assertEqual(201, task.status_code, task.text)
        listed = self.client.get("/api/v1/projects", headers={"Origin":ORIGIN}).json()
        self.assertEqual([task.json()["id"]], listed[0]["task_ids"])
        milestone = {"id":"m1","title":"First review","dueDate":"2026-11-01","completed":False}
        updated = self.client.patch(f"/api/v1/projects/{project_id}", json={"milestones":[milestone]}, headers={"Origin":ORIGIN})
        self.assertEqual(milestone, updated.json()["milestones"][0])
        event = self.client.post("/api/v1/calendar/events", json={"title":"Demo planning","room_id":"operations",
            "starts_at":"2026-10-12T10:00:00+05:30","timezone":"Asia/Kolkata"}, headers={"Origin":ORIGIN})
        self.assertEqual(201, event.status_code, event.text)
        events = self.client.get("/api/v1/calendar/events", headers={"Origin":ORIGIN}).json()["items"]
        self.assertEqual(event.json()["id"], events[0]["id"])
        self.assertEqual("2026-10-12T04:30:00Z", events[0]["starts_at"])

    def test_session_is_origin_bound_one_time_and_revocable(self):
        replay_client = TestClient(self.app, base_url="http://localhost:8765")
        mismatch_token, _ = ApiSessionService(
            self.database, (ORIGIN, "http://127.0.0.1:5173")
        ).issue_pairing_token([ORIGIN])
        mismatch = replay_client.post(
            "/api/v1/auth/session",
            json={"pairing_token": mismatch_token},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        self.assertEqual(403, mismatch.status_code)
        replay = replay_client.post(
            "/api/v1/auth/session",
            json={"pairing_token": self.pairing_token},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(401, replay.status_code)
        logout = self.client.delete("/api/v1/auth/session", headers={"Origin": ORIGIN})
        self.assertEqual(204, logout.status_code)
        self.assertEqual(401, self.client.get("/api/v1/loops", headers={"Origin": ORIGIN}).status_code)
        replay_client.close()

    def test_https_tunnel_pairing_sets_secure_cookie_and_requires_origin_for_writes(self):
        tunnel_origin = "https://lara-demo.ngrok-free.app"
        tunnel_app = create_app(
            self.database,
            loop_orchestrator=self.orchestrator,
            allowed_origins=(tunnel_origin,),
            provider_probe=lambda: {"status": "model_missing", "provider": "ollama", "model": "test"},
            conversation_generator=lambda prompt, actor, room: GenerationResult("ollama", "test-gemma", "answer"),
            memory_service=self.memory,
        )
        client = TestClient(tunnel_app, base_url="https://localhost:8765")
        token, _ = ApiSessionService(self.database, (tunnel_origin,)).issue_pairing_token([tunnel_origin])
        paired = client.post("/api/v1/auth/session", json={"pairing_token": token}, headers={"Origin": tunnel_origin})
        self.assertEqual(200, paired.status_code, paired.text)
        cookie = paired.headers["set-cookie"].lower()
        self.assertIn("secure", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertEqual(200, client.get("/api/v1/tasks").status_code)  # safe same-origin read may omit Origin
        mutation = client.post("/api/v1/tasks", json={"title":"must be protected","category":"Personal / Admin"})
        self.assertEqual(403, mutation.status_code)
        bad_origin = client.post("/api/v1/tasks", json={"title":"must be protected","category":"Personal / Admin"},
                                 headers={"Origin":"https://evil.example"})
        self.assertIn(bad_origin.status_code, (401, 403))
        logout = client.delete("/api/v1/auth/session", headers={"Origin":tunnel_origin})
        self.assertEqual(204, logout.status_code)
        self.assertIn("secure", logout.headers.get("set-cookie", "").lower())
        client.close()

    def test_pairing_token_has_separate_five_minute_expiry(self):
        token, _ = ApiSessionService(self.database, (ORIGIN,)).issue_pairing_token([ORIGIN])
        with self.database.connect() as connection:
            row = connection.execute("SELECT created_at,pairing_expires_at,expires_at FROM local_api_sessions WHERE token_hash=?",
                                     (ApiSessionService._hash(token),)).fetchone()
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            pairing_expiry = datetime.fromisoformat(row["pairing_expires_at"].replace("Z", "+00:00"))
            session_expiry = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        self.assertEqual(300, int((pairing_expiry-created).total_seconds()))
        self.assertGreater((session_expiry-created).total_seconds(), 300)
        with self.database.connect() as connection:
            connection.execute("UPDATE local_api_sessions SET pairing_expires_at='1970-01-01T00:00:00Z' WHERE token_hash=?",
                               (ApiSessionService._hash(token),))
        with self.assertRaises(ApiError):
            ApiSessionService(self.database, (ORIGIN,)).consume_pairing_token(token, ORIGIN)

    def test_https_origins_are_explicit_and_http_is_limited_to_loopback(self):
        self.assertEqual(("https://lara-demo.ngrok-free.app",),
                         configured_origins(("https://lara-demo.ngrok-free.app",)))
        with self.assertRaises(ValueError):
            configured_origins(("http://public.example:8080",))
        with self.assertRaises(ValueError):
            configured_origins(("https://lara-demo.ngrok-free.app/",))

    def test_unauthenticated_and_untrusted_origin_requests_are_rejected(self):
        client = TestClient(self.app, base_url="http://localhost:8765")
        self.assertEqual(401, client.get("/api/v1/loops", headers={"Origin": ORIGIN}).status_code)
        forbidden = self.client.get("/api/v1/loops", headers={"Origin": "http://evil.example"})
        self.assertEqual(401, forbidden.status_code)
        preflight = client.options(
            "/api/v1/loops",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(400, preflight.status_code)
        self.assertNotIn("access-control-allow-origin", preflight.headers)
        bad_host = client.get("/api/v1/health", headers={"Host": "attacker.example"})
        self.assertEqual(400, bad_host.status_code)
        client.close()

    def test_local_demo_skips_pairing_but_requires_exact_loopback_origin(self):
        demo_app = create_app(
            self.database,
            loop_orchestrator=self.orchestrator,
            allowed_origins=("http://127.0.0.1:5173",),
            local_demo=True,
            bind_host="127.0.0.1",
            provider_probe=lambda: {"status":"model_missing", "provider":"ollama", "model":"test"},
            conversation_generator=lambda prompt, actor, room: GenerationResult("ollama", "test-gemma", "Local answer."),
            memory_service=self.memory,
        )
        client = TestClient(demo_app, base_url="http://127.0.0.1:8765")
        try:
            headers = {"Origin":"http://127.0.0.1:5173"}
            created = client.post("/api/v1/tasks", json={"title":"Local demo task", "category":"Personal / Admin"}, headers=headers)
            self.assertEqual(201, created.status_code, created.text)
            self.assertEqual(0, len(client.cookies))
            pairing = client.post("/api/v1/auth/session", json={"pairing_token":"p" * 48}, headers=headers)
            self.assertEqual(409, pairing.status_code)
            untrusted = client.get("/api/v1/tasks", headers={"Origin":"http://localhost:5173"})
            self.assertEqual(403, untrusted.status_code)
            missing_origin = client.post("/api/v1/tasks", json={"title":"No origin", "category":"Personal / Admin"})
            self.assertEqual(403, missing_origin.status_code)
        finally:
            client.close()

    def test_local_demo_rejects_non_loopback_bind(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            create_app(self.database, allowed_origins=("http://127.0.0.1:5173",), local_demo=True, bind_host="0.0.0.0")
        with self.assertRaisesRegex(ValueError, "loopback"):
            create_app(self.database, allowed_origins=("http://127.0.0.1:5173",), local_demo=True)

    def test_local_demo_rejects_non_loopback_frontend_origin(self):
        with self.assertRaisesRegex(ValueError, "loopback HTTP"):
            create_app(self.database, allowed_origins=("https://lara.example",), local_demo=True, bind_host="127.0.0.1")

    def test_loop_crud_execution_roles_artifacts_and_cancellation_use_real_services(self):
        create = self.client.post(
            "/api/v1/loops",
            json={"goal": "Test local loop API", "constraints": ["Stay local"], "max_rounds": 4},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(201, create.status_code, create.text)
        loop_id = create.json()["id"]

        listed = self.client.get("/api/v1/loops?limit=1&offset=0", headers={"Origin": ORIGIN}).json()
        self.assertEqual(1, listed["page"]["total"])
        self.assertEqual(loop_id, listed["items"][0]["id"])

        run = self.client.post(
            f"/api/v1/loops/{loop_id}/run",
            json={"invocation_limit": 4},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(200, run.status_code, run.text)
        self.assertEqual("succeeded", run.json()["status"])
        self.assertEqual(4, run.json()["execution"]["invocation_count"])
        roles = self.client.get(f"/api/v1/loops/{loop_id}/roles", headers={"Origin": ORIGIN}).json()
        self.assertEqual(4, sum(len(role["executions"]) for role in roles))
        rounds = self.client.get(f"/api/v1/loops/{loop_id}/rounds", headers={"Origin": ORIGIN}).json()
        self.assertEqual(4, rounds["page"]["total"])
        artifacts = self.client.get(f"/api/v1/loops/{loop_id}/artifacts", headers={"Origin": ORIGIN}).json()
        self.assertEqual(1, artifacts["page"]["total"])
        self.assertEqual("final_synthesis", artifacts["items"][0]["artifact_type"])

        cancelled_loop = self.client.post(
            "/api/v1/loops",
            json={"goal": "Cancel this loop", "constraints": [], "max_rounds": 4},
            headers={"Origin": ORIGIN},
        ).json()
        cancelled = self.client.post(
            f"/api/v1/loops/{cancelled_loop['id']}/cancel",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual("cancelled", cancelled.json()["status"])

    def test_task_and_reminder_routes_are_backed_by_domain_services(self):
        payload = {
            "title": "API task",
            "description": "Persist through TaskService.",
            "category": "Personal / Admin",
            "room_id": "operations",
            "priority": "normal",
        }
        headers = {"Origin": ORIGIN, "Idempotency-Key": "api-task-once"}
        first = self.client.post("/api/v1/tasks", json=payload, headers=headers)
        repeated = self.client.post("/api/v1/tasks", json=payload, headers=headers)
        self.assertEqual(201, first.status_code, first.text)
        self.assertEqual(first.json()["id"], repeated.json()["id"])
        self.assertEqual(1, self.client.get("/api/v1/tasks", headers={"Origin": ORIGIN}).json()["page"]["total"])

        task_id = first.json()["id"]
        when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(timespec="seconds").replace("+00:00", "Z")
        reminder = self.client.post(
            "/api/v1/reminders",
            json={"task_id": task_id, "scheduled_at": when, "message": "Review the task"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(201, reminder.status_code, reminder.text)
        reminder_id = reminder.json()["id"]
        page = self.client.get(f"/api/v1/reminders?limit=1", headers={"Origin": ORIGIN}).json()
        self.assertEqual(1, page["page"]["total"])
        self.assertEqual(reminder_id, page["items"][0]["id"])

        snoozed_until = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(timespec="seconds").replace("+00:00", "Z")
        snoozed = self.client.post(
            f"/api/v1/reminders/{reminder_id}/snooze",
            json={"until": snoozed_until},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual("snoozed", snoozed.json()["status"])

    def test_request_validation_is_structured_and_clients_cannot_assert_identity(self):
        response = self.client.post(
            "/api/v1/loops",
            json={"goal": "No self-assigned roles", "persona_id": "desktop_operator"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("VALIDATION_ERROR", response.json()["error"]["code"])
        self.assertTrue(response.json()["error"]["request_id"])
        self.assertEqual(response.json()["error"]["request_id"], response.headers["X-Request-ID"])
        self.assertNotIn("desktop_operator", response.text)

    def test_request_size_limit_and_pairing_rate_limit(self):
        oversized = self.client.post(
            "/api/v1/loops",
            content=b"x" * (MAX_REQUEST_BYTES + 1),
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
        )
        self.assertEqual(413, oversized.status_code)
        self.assertEqual("REQUEST_TOO_LARGE", oversized.json()["error"]["code"])
        self.assertIn("X-Request-ID", oversized.headers)
        chunked = self.client.post(
            "/api/v1/loops",
            content=(b"x" * 400_000 for _ in range(3)),
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
        )
        self.assertEqual(413, chunked.status_code, chunked.text)
        self.assertEqual("REQUEST_TOO_LARGE", chunked.json()["error"]["code"])
        self.assertEqual(ORIGIN, chunked.headers["access-control-allow-origin"])

        limiter = PairingRateLimiter()
        for _ in range(8):
            limiter.check("test-peer")
        with self.assertRaises(ApiError) as raised:
            limiter.check("test-peer")
        self.assertEqual(429, raised.exception.status_code)

    def test_cli_reports_invalid_api_origin_without_traceback(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"UBUNTU_AGENT_API_ORIGINS": "http://invalid.example:5173"}), \
                contextlib.redirect_stderr(stderr):
            result = main(["--db", f"{directory}/api.sqlite3", "api-serve", "--port", "8876"])
        self.assertEqual(2, result)
        self.assertEqual("API_CONFIGURATION_ERROR", json.loads(stderr.getvalue())["error"]["code"])


if __name__ == "__main__":
    unittest.main()
