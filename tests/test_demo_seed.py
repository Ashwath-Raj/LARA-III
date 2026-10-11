import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from ubuntu_agent.cli import main
from ubuntu_agent.database import Database
from ubuntu_agent.demo_seed import (
    DEMO_LOOP_ID,
    DEMO_MARKER,
    DEMO_WORKSPACE_ID,
    DemoSeedError,
    inspect_demo,
    seed_demo,
)
from ubuntu_agent.models import Actor
from ubuntu_agent.services import ConflictError, TaskService


FIXED_NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "lara-iv-demo.sqlite3"
        self.db = Database(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def seed(self, **kwargs):
        return seed_demo(self.db, clock=lambda: FIXED_NOW, **kwargs)

    def test_fresh_database_seeds_supported_demo_records(self):
        result = self.seed()

        self.assertEqual("seeded", result["status"])
        self.assertEqual(9, result["counts"]["tasks"])
        self.assertEqual(3, result["counts"]["reminders"])
        self.assertEqual(1, result["counts"]["ai_loops"])
        self.assertEqual(4, result["counts"]["loop_roles"])
        self.assertEqual(1, result["counts"]["loop_rounds"])
        self.assertEqual(1, result["counts"]["loop_sources"])
        self.assertEqual(1, result["counts"]["loop_artifacts"])
        self.assertEqual(1, result["counts"]["desktop_workspaces"])
        self.assertEqual(4, result["counts"]["desktop_slots"])
        self.assertEqual(0, result["counts"]["desktop_runs"])
        self.assertEqual("ok", self.db.integrity_check())
        self.assertEqual(
            {"inbox", "next", "in_progress", "waiting", "review", "ready_to_submit", "done", "archived"},
            set(result["counts"]["tasks_by_status"]),
        )

    def test_repeated_seed_is_idempotent_and_preserves_existing_records(self):
        self.db.initialize()
        actor = Actor("local-user", "task_deadline_manager")
        user_task = TaskService(self.db).create_task(
            {"title": "User's existing task", "source_text": "Created before demo seed."},
            actor,
            "user-task-before-demo",
        )
        first = self.seed()
        with self.db.connect() as connection:
            sample = connection.execute(
                """SELECT t.id FROM tasks t JOIN task_idempotency_keys k ON k.task_id=t.id
                   WHERE k.idempotency_key='lara-iv-demo:v1:research-reading'""",
            ).fetchone()
            reminder = connection.execute(
                """SELECT r.id FROM reminders r JOIN task_idempotency_keys k ON k.task_id=r.task_id
                   WHERE k.idempotency_key='lara-iv-demo:v1:algorithms-assignment'""",
            ).fetchone()
            connection.execute(
                "UPDATE reminders SET message='User-edited demo reminder' WHERE id=?",
                (reminder["id"],),
            )
        TaskService(self.db).transition_task(sample["id"], "next", actor)
        second = self.seed()

        self.assertEqual(9, first["counts"]["tasks"])
        self.assertEqual(0, sum(second["created"].values()))
        self.assertEqual(9, second["counts"]["tasks"])
        preserved = TaskService(self.db).get_task(user_task["id"], actor)
        self.assertEqual("User's existing task", preserved["title"])
        with self.db.connect() as connection:
            self.assertEqual("next", connection.execute(
                "SELECT status FROM tasks WHERE id=?", (sample["id"],)
            ).fetchone()["status"])
            self.assertEqual(10, connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            self.assertEqual(3, connection.execute("SELECT COUNT(*) FROM reminders").fetchone()[0])
            self.assertEqual("User-edited demo reminder", connection.execute(
                "SELECT message FROM reminders WHERE id=?", (reminder["id"],)
            ).fetchone()["message"])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM ai_loops").fetchone()[0])
            self.assertEqual(1, connection.execute(
                "SELECT COUNT(*) FROM desktop_workspaces WHERE id=?", (DEMO_WORKSPACE_ID,)
            ).fetchone()[0])

    def test_foreign_keys_and_ownership_are_valid(self):
        self.seed()
        with self.db.connect() as connection:
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual(0, connection.execute(
                """SELECT COUNT(*) FROM tasks t LEFT JOIN personas p ON p.id=t.persona_owner
                   WHERE t.source_text LIKE ? AND p.id IS NULL""",
                (f"{DEMO_MARKER}%",),
            ).fetchone()[0])
            self.assertEqual(0, connection.execute(
                """SELECT COUNT(*) FROM loop_roles r LEFT JOIN ai_loops l ON l.id=r.loop_id
                   WHERE r.loop_id=? AND l.id IS NULL""",
                (DEMO_LOOP_ID,),
            ).fetchone()[0])
            self.assertEqual(4, connection.execute(
                "SELECT COUNT(*) FROM desktop_slots WHERE workspace_id=?", (DEMO_WORKSPACE_ID,)
            ).fetchone()[0])

    def test_demo_aggregate_counts_match_the_seeded_rows(self):
        result = self.seed()
        counts = result["counts"]
        with self.db.connect() as connection:
            self.assertEqual(counts["tasks"], connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE source_text LIKE ?", (f"{DEMO_MARKER}%",)
            ).fetchone()[0])
            self.assertEqual(counts["reminders"], connection.execute(
                """SELECT COUNT(*) FROM reminders r JOIN tasks t ON t.id=r.task_id
                   WHERE t.source_text LIKE ?""", (f"{DEMO_MARKER}%",)
            ).fetchone()[0])
            self.assertEqual(counts["overdue_active_tasks"], connection.execute(
                """SELECT COUNT(*) FROM tasks WHERE source_text LIKE ? AND due_date < ?
                   AND status NOT IN ('done','archived')""",
                (f"{DEMO_MARKER}%", FIXED_NOW.date().isoformat()),
            ).fetchone()[0])
        self.assertGreaterEqual(counts["overdue_active_tasks"], 1)
        self.assertGreaterEqual(counts["due_within_7_days"], 1)

    def test_demo_loop_is_visibly_synthetic_and_not_marked_as_executed(self):
        self.seed()
        with self.db.connect() as connection:
            loop = connection.execute("SELECT * FROM ai_loops WHERE id=?", (DEMO_LOOP_ID,)).fetchone()
            roles = connection.execute(
                "SELECT role_name,status FROM loop_roles WHERE loop_id=?", (DEMO_LOOP_ID,)
            ).fetchall()
            round_row = connection.execute(
                "SELECT * FROM loop_rounds WHERE loop_id=?", (DEMO_LOOP_ID,)
            ).fetchone()
            source = connection.execute(
                "SELECT * FROM loop_sources WHERE loop_id=?", (DEMO_LOOP_ID,)
            ).fetchone()
            artifact = connection.execute(
                "SELECT * FROM loop_artifacts WHERE loop_id=?", (DEMO_LOOP_ID,)
            ).fetchone()
            execution = connection.execute(
                "SELECT status,error_class,invocation_count FROM loop_execution_state WHERE loop_id=?",
                (DEMO_LOOP_ID,),
            ).fetchone()
            workspace = connection.execute(
                "SELECT * FROM desktop_workspaces WHERE id=?", (DEMO_WORKSPACE_ID,)
            ).fetchone()

        self.assertTrue(loop["goal"].startswith(DEMO_MARKER))
        self.assertEqual("cancelled", loop["status"])
        self.assertIsNone(loop["job_id"])
        self.assertEqual({"red_team", "blue_team", "judge", "unbiased_reviewer"},
                         {role["role_name"] for role in roles})
        self.assertTrue(all(role["status"] == "cancelled" for role in roles))
        self.assertEqual("cancelled", round_row["status"])
        self.assertTrue(json.loads(round_row["output_json"])["demo"])
        self.assertEqual("demo_synthetic", source["trust_label"])
        self.assertEqual(0, source["ingested"])
        self.assertEqual("demo_preview", artifact["artifact_type"])
        self.assertTrue(artifact["content"].startswith(DEMO_MARKER))
        self.assertEqual(("cancelled", "demo_seed_not_executed", 0), tuple(execution))
        self.assertEqual("unavailable", workspace["status"])
        self.assertTrue(json.loads(workspace["layout_json"])["simulated"])

    def test_seeding_does_not_call_models_or_desktop_adapters(self):
        with (
            patch("ubuntu_agent.providers.OllamaProvider.generate_text", side_effect=AssertionError("model called")) as ollama,
            patch("ubuntu_agent.providers.GeminiProvider.generate_text", side_effect=AssertionError("cloud called")) as gemini,
            patch("ubuntu_agent.desktop.bridge.LinuxDesktopBridge._run",
                  side_effect=AssertionError("desktop command called")) as desktop,
        ):
            self.seed()
        ollama.assert_not_called()
        gemini.assert_not_called()
        desktop.assert_not_called()

    def test_non_development_environment_requires_explicit_opt_in(self):
        with self.assertRaises(DemoSeedError):
            self.seed(environment="staging")
        self.assertFalse(self.path.exists())
        with self.assertRaises(DemoSeedError):
            self.seed(environment="production", allow_non_development=True)
        self.assertFalse(self.path.exists())
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            with self.assertRaises(DemoSeedError):
                self.seed()
        self.assertFalse(self.path.exists())
        with patch.dict("os.environ", {"APP_ENV": "staging"}):
            with self.assertRaises(DemoSeedError):
                self.seed(allow_non_development=True)
            self.assertFalse(self.path.exists())
            result = self.seed(environment="staging", allow_non_development=True)
        self.assertEqual("staging", result["environment"])

    def test_production_requires_both_opt_ins(self):
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            with self.assertRaises(DemoSeedError):
                self.seed(environment="production", allow_non_development=True)
            result = self.seed(environment="production", allow_non_development=True,
                               allow_production=True)
        self.assertEqual(9, result["counts"]["tasks"])

    def test_cli_requires_explicit_database_and_checks_environment_before_initializing(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(2, main(["seed-demo"]))
        self.assertIn("explicit --db", error.getvalue())
        self.assertFalse(self.path.exists())

        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(2, main([
                "--db", str(self.path), "seed-demo", "--environment", "production",
            ]))
        self.assertIn("--allow-non-development", error.getvalue())
        self.assertFalse(self.path.exists())

    def test_inspection_requires_an_existing_initialized_database(self):
        with self.assertRaises(DemoSeedError):
            inspect_demo(self.db)
        self.assertFalse(self.path.exists())

    def test_conflicting_stable_task_key_fails_before_adding_partial_demo_data(self):
        self.db.initialize()
        TaskService(self.db).create_task(
            {"title": "Not demo data", "source_text": "Existing user content."},
            Actor("local-user", "task_deadline_manager"),
            "lara-iv-demo:v1:algorithms-assignment",
        )
        with self.assertRaises(ConflictError):
            self.seed()
        with self.db.connect() as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM ai_loops").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM desktop_workspaces").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
