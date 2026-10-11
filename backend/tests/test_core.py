import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ubuntu_agent.database import Database, MIGRATIONS
from ubuntu_agent.models import AccessContext, Actor, DecisionKind, RiskTier
from ubuntu_agent.policy import PolicyEngine
from ubuntu_agent.services import (
    ConflictError,
    NotFoundError,
    PolicyDeniedError,
    ReminderService,
    TaskService,
    ValidationError,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.db = Database(self.path)
        self.db.initialize()
        self.actor = Actor("local-user", "task_deadline_manager")
        self.tasks = TaskService(self.db)
        self.reminders = ReminderService(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_database_initialization_and_persistence_after_reopen(self):
        task = self.tasks.create_task({"title": "Persist me"}, self.actor)
        reopened = Database(self.path)
        reopened.initialize()
        self.assertEqual("Persist me", TaskService(reopened).get_task(task["id"], self.actor)["title"])
        self.assertEqual("ok", reopened.integrity_check())

    def test_migration_failure_rolls_back_schema_and_version_then_retries(self):
        fresh = Database(Path(self.temp.name) / "migration-retry.sqlite3")
        failed_migrations = ((1, MIGRATIONS[0][1] + "\nCREATE TABLE migration_failure_injection (id INTEGER);\nINVALID SQL;"),)
        with patch("ubuntu_agent.database.MIGRATIONS", failed_migrations):
            with self.assertRaises(sqlite3.Error):
                fresh.initialize()
        with fresh.connect() as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("rooms", names)
        self.assertNotIn("migration_failure_injection", names)
        fresh.initialize()
        with fresh.connect() as connection:
            self.assertEqual(max(version for version, _ in MIGRATIONS),
                             connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='task_idempotency_keys'").fetchone())

    def test_sticky_migration_preserves_existing_tasks_and_defaults_regular_tasks(self):
        legacy = Database(Path(self.temp.name) / "sticky-migration.sqlite3")
        with patch("ubuntu_agent.database.MIGRATIONS", MIGRATIONS[:12]):
            legacy.initialize()
        with legacy.connect() as connection:
            category_id = connection.execute(
                "SELECT id FROM categories WHERE name='Personal / Admin'"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO tasks
                   (id,title,item_type,status,priority,category_id,room_id,timezone,created_at,updated_at)
                   VALUES ('existing-task','Existing task','task','inbox','normal',?,'operations','UTC','now','now')""",
                (category_id,),
            )

        legacy.initialize()
        with legacy.connect() as connection:
            existing = connection.execute(
                "SELECT title,is_sticky,sticky_color FROM tasks WHERE id='existing-task'"
            ).fetchone()
            self.assertEqual(("Existing task", 0, None), tuple(existing))
            self.assertEqual(13, connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])

        service = TaskService(legacy)
        regular = service.create_task({"title": "Regular task"}, self.actor)
        sticky = service.create_task(
            {"title": "Sticky note", "is_sticky": True, "sticky_color": "ash"}, self.actor
        )
        self.assertFalse(regular["is_sticky"])
        self.assertIsNone(regular["sticky_color"])
        self.assertTrue(sticky["is_sticky"])
        self.assertEqual("ash", sticky["sticky_color"])

    def test_migration_backfills_existing_idempotency_records(self):
        legacy = Database(Path(self.temp.name) / "legacy.sqlite3")
        with patch("ubuntu_agent.database.MIGRATIONS", MIGRATIONS[:1]):
            legacy.initialize()
        with legacy.connect() as connection:
            category_id = connection.execute("SELECT id FROM categories WHERE name='Personal / Admin'").fetchone()[0]
            connection.execute("""INSERT INTO tasks
                (id,title,description,item_type,status,priority,category_id,room_id,persona_owner,due_date,due_at,timezone,
                 source_text,created_at,updated_at,idempotency_key)
                VALUES ('legacy-task','Legacy','', 'task','inbox','normal',?,'operations','task_deadline_manager',NULL,NULL,
                        'UTC','', '2027-01-01T00:00:00Z','2027-01-01T00:00:00Z','legacy-key')""", (category_id,))
        legacy.initialize()
        returned = TaskService(legacy).create_task({"title": "Legacy"}, self.actor, "legacy-key")
        self.assertEqual("legacy-task", returned["id"])

    def test_task_and_reminder_create_and_retrieve_without_providers(self):
        task = self.tasks.create_task({"title": "Study", "category": "Academics", "room_id": "operations"}, self.actor)
        reminder = self.reminders.create_reminder(task["id"], "2027-01-02T03:04:05Z", "Review notes", self.actor)
        self.assertEqual(task["id"], self.tasks.get_task(task["id"], self.actor)["id"])
        self.assertEqual(reminder["id"], self.reminders.list_reminders(self.actor)[0]["id"])
        self.assertEqual("scheduled", reminder["status"])

    def test_invalid_labels_and_malformed_inputs_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.tasks.create_task({"title": "Bad", "category": "Not a real label"}, self.actor)
        with self.assertRaises(ValidationError):
            self.tasks.create_task({"title": "Bad", "room_id": "made_up"}, self.actor)
        with self.assertRaises(ValidationError):
            self.tasks.create_task({"title": "Bad", "due_date": "2027-02-30"}, self.actor)
        with self.assertRaises(ValidationError):
            self.reminders.create_reminder("missing", "2027-01-02T03:04:05", "No timezone", self.actor)

    def test_policy_context_validation_fails_closed(self):
        engine = PolicyEngine()
        base = dict(principal_id="local-user", persona_id="task_deadline_manager", job_id=None, room_id="operations",
                    resource_id="task-1", action_id="task.read", sensitivity_label="internal", destination="local",
                    risk_tier="read", system_mode="normal")
        for changes in ({"principal_id": None}, {"persona_id": "unknown"}, {"room_id": None},
                        {"sensitivity_label": None}, {"risk_tier": "mystery"}, {"system_mode": "paused"},
                        {"action_id": "unknown.action"}, {"job_id": "unscoped-job"}):
            self.assertEqual(DecisionKind.DENY, engine.evaluate_access(AccessContext(**(base | changes))).decision)
        self.assertEqual(DecisionKind.DENY, engine.evaluate_access(None).decision)
        self.assertEqual(DecisionKind.DENY, engine.evaluate_access({}).decision)
        self.assertEqual(DecisionKind.DENY, engine.evaluate_access(AccessContext(**(base | {"action_id": []}))).decision)

    def test_task_room_write_grants_do_not_enable_other_write_actions(self):
        engine = PolicyEngine()
        for persona, room, sensitivity in (
            ("task_deadline_manager", "opportunities", "internal"),
            ("ai_ml_researcher", "public_research", "public"),
        ):
            task_context = AccessContext(
                "local-user", persona, None, room, "task-1", "task.create",
                sensitivity, "local", RiskTier.PREPARE.value, "normal",
            )
            memory_context = AccessContext(
                "local-user", persona, None, room, "document-1", "memory.ingest",
                sensitivity, "local", RiskTier.PREPARE.value, "normal",
            )
            self.assertEqual(DecisionKind.ALLOW, engine.evaluate_access(task_context).decision)
            self.assertEqual(DecisionKind.DENY, engine.evaluate_access(memory_context).decision)

    def test_policy_evaluation_exception_is_denied_at_service_boundary(self):
        task = self.tasks.create_task({"title": "Protected"}, self.actor)

        class BrokenPolicy(PolicyEngine):
            def evaluate_access(self, context):
                raise RuntimeError("policy backend failure")

        with self.assertRaises(NotFoundError):
            TaskService(self.db, BrokenPolicy()).get_task(task["id"], self.actor)

    def test_conflicting_persisted_room_sensitivity_fails_closed(self):
        task = self.tasks.create_task({"title": "Sensitive", "category": "Academics", "room_id": "academic"},
                                      Actor("local-user", "exam_study_coach"))
        with self.db.connect() as connection:
            connection.execute("UPDATE rooms SET sensitivity_default='public' WHERE id='academic'")
        with self.assertRaises(NotFoundError):
            TaskService(self.db).get_task(task["id"], Actor("local-user", "exam_study_coach"))

    def test_dangerous_actions_cannot_be_downgraded_to_read_risk(self):
        base = dict(principal_id="local-user", persona_id="desktop_operator", job_id=None, room_id="operations",
                    resource_id="target", sensitivity_label="internal", destination="local", risk_tier="read",
                    system_mode="normal")
        engine = PolicyEngine()
        for action in ("shell.execute", "file.delete", "message.send", "system.configure", "classroom.submit"):
            with self.subTest(action=action):
                self.assertEqual(DecisionKind.DENY, engine.evaluate_access(AccessContext(action_id=action, **base)).decision)
        self.assertEqual(DecisionKind.DENY,
                         engine.evaluate_access(AccessContext(**(base | {"action_id": "task.read", "risk_tier": RiskTier.PREPARE.value}))).decision)

    def test_cross_room_reads_and_writes_are_denied_at_service_boundary(self):
        task = self.tasks.create_task({"title": "Academic", "room_id": "academic", "category": "Academics"},
                                      Actor("local-user", "exam_study_coach"))
        with self.assertRaises(NotFoundError):
            self.tasks.get_task(task["id"], self.actor)
        with self.assertRaises(NotFoundError):
            self.tasks.update_task(task["id"], {"title": "Changed"}, self.actor)
        self.assertEqual([], self.tasks.list_tasks(self.actor))

    def test_inaccessible_and_missing_task_errors_are_identical(self):
        task = self.tasks.create_task({"title": "Hidden", "category": "Academics", "room_id": "academic"},
                                      Actor("local-user", "exam_study_coach"))
        outcomes = []
        for task_id in (task["id"], "missing-task-id"):
            with self.assertRaises(NotFoundError) as raised:
                self.tasks.get_task(task_id, self.actor)
            outcomes.append((raised.exception.code, str(raised.exception)))
        self.assertEqual(outcomes[0], outcomes[1])

    def test_authorization_audit_records_final_denial_for_direct_and_list_reads(self):
        task = self.tasks.create_task({"title": "Hidden", "category": "Academics", "room_id": "academic"},
                                      Actor("local-user", "exam_study_coach"))
        with self.assertRaises(NotFoundError):
            self.tasks.get_task(task["id"], self.actor)
        self.assertEqual([], self.tasks.list_tasks(self.actor))
        with self.db.connect() as connection:
            events = connection.execute("SELECT policy_decision,result_status FROM audit_events WHERE action='task.read'").fetchall()
        self.assertEqual(2, len(events))
        self.assertTrue(all(event["policy_decision"] == "deny" for event in events))
        self.assertFalse(any(event["result_status"] == "authorized" for event in events))

    def test_unsupported_approval_actions_remain_denied(self):
        context = AccessContext(principal_id="local-user", persona_id="desktop_operator", job_id=None,
            room_id="operations", resource_id="submission-1", action_id="classroom.submit",
            sensitivity_label="internal", destination="local", risk_tier="external_destructive",
            system_mode="normal", approval_id="unverified")
        self.assertEqual(DecisionKind.DENY, PolicyEngine().evaluate_access(context).decision)

    def test_task_state_validation_and_idempotency(self):
        task = self.tasks.create_task({"title": "One"}, self.actor, "retry-1")
        same = self.tasks.create_task({"title": "One"}, self.actor, "retry-1")
        self.assertEqual(task["id"], same["id"])
        with self.assertRaises(ConflictError):
            self.tasks.create_task({"title": "Different request"}, self.actor, "retry-1")
        with self.assertRaises(ConflictError):
            self.tasks.transition_task(task["id"], "done", self.actor, evidence="proof")
        with self.assertRaises(NotFoundError):
            self.tasks.get_task("unknown", self.actor)
        with self.assertRaises(ValidationError):
            self.tasks.create_task({"title": "Cannot start completed", "status": "done"}, self.actor)

    def test_idempotency_key_is_actor_scoped_and_cannot_replay_another_personas_task(self):
        coach = Actor("local-user", "exam_study_coach")
        private = self.tasks.create_task({"title": "Private academic work", "category": "Academics", "room_id": "academic"},
                                         coach, "shared-key")
        with self.assertRaises(PolicyDeniedError):
            self.tasks.create_task({"title": "Private academic work", "category": "Academics", "room_id": "academic"},
                                   self.actor, "shared-key")
        own = self.tasks.create_task({"title": "My operations task"}, self.actor, "shared-key")
        self.assertNotEqual(private["id"], own["id"])
        self.assertEqual("My operations task", own["title"])

    def test_task_update_and_completion_require_evidence(self):
        task = self.tasks.create_task({"title": "Change me"}, self.actor)
        updated = self.tasks.update_task(task["id"], {"title": "Updated", "priority": "high"}, self.actor)
        self.assertEqual("Updated", updated["title"])
        in_progress = self.tasks.transition_task(task["id"], "in_progress", self.actor)
        self.assertEqual("in_progress", in_progress["status"])
        with self.assertRaises(ValidationError):
            self.tasks.transition_task(task["id"], "done", self.actor)
        done = self.tasks.transition_task(task["id"], "done", self.actor, evidence="Verified complete")
        self.assertEqual("done", done["status"])
        self.assertEqual("Verified complete", done["completion_evidence"])

    def test_due_deadline_reschedules_relative_reminder_and_survives_reopen(self):
        task = self.tasks.create_task({"title": "Timed task", "due_date": "2027-05-01", "due_at": "2027-05-01T12:00:00Z"}, self.actor)
        reminder = self.reminders.create_reminder(task["id"], "2027-05-01T11:00:00Z", "One hour before", self.actor,
                                                  reminder_type="relative_to_due_at", offset_minutes=60)
        self.tasks.update_task(task["id"], {"due_date": "2027-06-01", "due_at": "2027-06-01T12:00:00Z"}, self.actor)
        reopened = Database(self.path)
        current = ReminderService(reopened).list_reminders(self.actor)[0]
        self.assertEqual(reminder["id"], current["id"])
        self.assertEqual("2027-06-01T11:00:00Z", current["scheduled_at"])
        self.assertEqual("2027-06-01T12:00:00Z", TaskService(reopened).get_task(task["id"], self.actor)["due_at"])

    def test_deadline_change_rejects_fixed_reminder_without_partial_update(self):
        task = self.tasks.create_task({"title": "Fixed reminder", "due_at": "2027-05-01T12:00:00Z"}, self.actor)
        reminder = self.reminders.create_reminder(task["id"], "2027-05-01T11:00:00Z", "Fixed time", self.actor)
        with self.assertRaises(ConflictError):
            self.tasks.update_task(task["id"], {"due_at": "2027-06-01T12:00:00Z"}, self.actor)
        self.assertEqual("2027-05-01T12:00:00Z", self.tasks.get_task(task["id"], self.actor)["due_at"])
        self.assertEqual("2027-05-01T11:00:00Z", self.reminders.list_reminders(self.actor)[0]["scheduled_at"])
        self.assertEqual("scheduled", reminder["status"])

    def test_reschedule_database_failure_rolls_back_task_and_reminder_together(self):
        task = self.tasks.create_task({"title": "Atomic reminder", "due_at": "2027-05-01T12:00:00Z"}, self.actor)
        self.reminders.create_reminder(task["id"], "2027-05-01T11:00:00Z", "One hour before", self.actor,
                                       reminder_type="relative_to_due_at", offset_minutes=60)
        with self.db.connect() as connection:
            connection.execute("""CREATE TRIGGER reject_reminder_reschedule BEFORE UPDATE OF scheduled_at ON reminders
                               BEGIN SELECT RAISE(ABORT,'injected reschedule failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.tasks.update_task(task["id"], {"due_at": "2027-06-01T12:00:00Z"}, self.actor)
        self.assertEqual("2027-05-01T12:00:00Z", self.tasks.get_task(task["id"], self.actor)["due_at"])
        self.assertEqual("2027-05-01T11:00:00Z", self.reminders.list_reminders(self.actor)[0]["scheduled_at"])

    def test_local_database_file_is_private(self):
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
