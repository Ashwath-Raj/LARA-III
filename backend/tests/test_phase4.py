import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ubuntu_agent.approvals import ApprovalService
from ubuntu_agent.database import Database
from ubuntu_agent.jobs import JobQueue, Worker
from ubuntu_agent.models import Actor, DecisionKind, PolicyDecision, utc_now
from ubuntu_agent.notifications import FakeNotificationAdapter, UbuntuNotificationAdapter
from ubuntu_agent.policy import ACTION_RISK
from ubuntu_agent.reminder_delivery import ReminderDeliveryHandler
from ubuntu_agent.runtime import RuntimeControlService
from ubuntu_agent.services import ConflictError, PolicyDeniedError, ReminderService, TaskService


class Clock:
    def __init__(self, value=None):
        self.value = value or datetime(2027, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def iso(self):
        return self.value.isoformat(timespec="seconds").replace("+00:00", "Z")

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class RequireThenAllowPolicy:
    def __init__(self):
        self.denied = False

    def evaluate_access(self, context):
        if self.denied:
            decision, reason = DecisionKind.DENY, "changed policy"
        elif context.approval_id:
            decision, reason = DecisionKind.ALLOW, "revalidated"
        else:
            decision, reason = DecisionKind.REQUIRES_APPROVAL, "approval required"
        return PolicyDecision(decision, "test-policy", reason, utc_now())


class Phase4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "phase4.sqlite3"
        self.db = Database(self.path)
        self.db.initialize()
        self.actor = Actor("local-user", "task_deadline_manager")
        self.clock = Clock()

    def tearDown(self):
        self.temp.cleanup()

    def test_job_persists_and_repeated_enqueue_is_idempotent(self):
        queue = JobQueue(self.db, clock=self.clock)
        job = queue.enqueue("reminder.deliver", {"reminder_id": "r1", "generation": 1}, "reconcile:r1")
        same = queue.enqueue("reminder.deliver", {"reminder_id": "r1", "generation": 1}, "reconcile:r1")
        self.assertEqual(job["id"], same["id"])
        reopened = Database(self.path)
        self.assertEqual(job["id"], JobQueue(reopened, clock=self.clock).list_jobs()[0]["id"])

    def test_concurrent_claims_never_claim_same_job(self):
        queue = JobQueue(self.db, clock=self.clock)
        queue.enqueue("reminder.deliver", {"reminder_id": "r1", "generation": 1}, "claim:1")
        barrier = threading.Barrier(3)
        results = []

        def claim(name):
            barrier.wait()
            results.extend(queue.claim(name, limit=1))

        workers = [threading.Thread(target=claim, args=(f"worker-{i}",)) for i in range(2)]
        for thread in workers: thread.start()
        barrier.wait()
        for thread in workers: thread.join()
        self.assertEqual(1, len(results))
        self.assertEqual(1, results[0]["attempts"])

    def test_expired_lease_retry_backoff_limit_and_cancel(self):
        queue = JobQueue(self.db, clock=self.clock)
        job = queue.enqueue("reminder.deliver", {"reminder_id": "x", "generation": 1}, "lease:x", max_attempts=2)
        queue.claim("dead", limit=1, lease_seconds=5)
        self.clock.advance(6)
        self.assertEqual([], queue.claim("next", limit=1))
        recovered = queue.list_jobs()[0]
        self.assertEqual("retry_wait", recovered["status"])
        self.assertEqual("2027-01-01T00:00:36Z", recovered["available_at"])
        self.clock.advance(30)
        queue.claim("next", limit=1)
        queue.finish(job["id"], "next", error_class="handler_failed")
        terminal = queue.list_jobs()[0]
        self.assertEqual("failed", terminal["status"])
        pending = queue.enqueue("reminder.deliver", {"reminder_id": "y", "generation": 1}, "cancel:y")
        self.assertEqual("cancelled", queue.cancel(pending["id"])["status"])

    def test_malformed_persisted_payload_fails_closed(self):
        queue = JobQueue(self.db, clock=self.clock)
        job = queue.enqueue("reminder.deliver", {"reminder_id": "safe", "generation": 1}, "bad-payload")
        with self.db.connect() as connection:
            connection.execute("UPDATE jobs SET payload_json=? WHERE id=?", ("{broken", job["id"]))
        self.assertEqual([], queue.claim("worker"))
        result = queue.list_jobs()[0]
        self.assertEqual("failed", result["status"])
        self.assertEqual("invalid_payload", result["error_class"])

    def test_shutdown_releases_claimed_but_unstarted_job(self):
        queue = JobQueue(self.db, clock=self.clock)
        queue.enqueue("reminder.deliver", {"reminder_id": "r1", "generation": 1}, "shutdown:r1")
        worker = Worker(queue, {}, owner="stopper")
        worker.request_shutdown()
        self.assertEqual(1, worker.run_once())
        job = queue.list_jobs()[0]
        self.assertEqual("queued", job["status"])
        self.assertEqual(0, job["attempts"])

    def test_phase_worker_never_dispatches_unimplemented_autonomy_jobs(self):
        queue = JobQueue(self.db, clock=self.clock)
        queue.enqueue("autonomy.action", {"approval_id": "a1", "action_type": "shell.execute", "arguments": {}}, "blocked-action")
        dispatched = []
        worker = Worker(queue, {"autonomy.action": lambda payload: dispatched.append(payload)})
        worker.run_once()
        self.assertEqual([], dispatched)
        self.assertEqual("failed", queue.list_jobs()[0]["status"])
        self.assertEqual("handler_unavailable", queue.list_jobs()[0]["error_class"])

    def test_pause_and_kill_persist_and_preserve_pending_jobs(self):
        queue = JobQueue(self.db, clock=self.clock)
        queue.enqueue("autonomy.action", {"approval_id": "a1", "action_type": "unsupported", "arguments": {}}, "autonomy")
        queue.enqueue("reminder.deliver", {"reminder_id": "r1", "generation": 1}, "reminder")
        controls = RuntimeControlService(self.db)
        controls.pause(self.actor)
        paused_claim = queue.claim("paused-worker")
        self.assertEqual(1, len(paused_claim))
        self.assertEqual("reminder.deliver", paused_claim[0]["job_type"])
        controls.kill(self.actor)
        self.assertEqual([], JobQueue(Database(self.path), clock=self.clock).claim("killed-worker"))
        with self.assertRaises(PolicyDeniedError): controls.resume(self.actor)
        controls.recover(self.actor)
        self.assertEqual(1, len(queue.claim("recovered-worker")))

    def _reminder(self, *, scheduled="2027-01-01T00:00:00Z", relative=False):
        tasks = TaskService(self.db)
        reminder_service = ReminderService(self.db)
        task = tasks.create_task({"title": "Study", "due_at": "2027-01-01T02:00:00Z"}, self.actor)
        args = {"reminder_type": "relative_to_due_at", "offset_minutes": 60} if relative else {}
        item = reminder_service.create_reminder(task["id"], scheduled, "Review the notes", self.actor, **args)
        return task, item, tasks, reminder_service

    def test_due_reminder_reconcile_and_delivery_success_are_idempotent(self):
        task, reminder, tasks, service = self._reminder()
        queue = JobQueue(self.db, clock=self.clock)
        self.assertEqual(1, service.reconcile_reminders(now=self.clock.iso())["enqueued"])
        self.assertEqual(1, service.reconcile_reminders(now=self.clock.iso())["enqueued"])
        self.assertEqual(1, len(queue.list_jobs()))
        reopened = Database(self.path)
        service = ReminderService(reopened, clock=self.clock.iso)
        self.assertEqual(1, service.reconcile_reminders()["enqueued"])
        self.assertEqual(1, len(JobQueue(reopened, clock=self.clock).list_jobs()))
        with reopened.connect() as connection:
            reminder_columns = {row["name"] for row in connection.execute("PRAGMA table_info(reminders)")}
        self.assertNotIn("due_now", reminder_columns)
        adapter = FakeNotificationAdapter()
        worker = Worker(JobQueue(reopened, clock=self.clock), {"reminder.deliver": ReminderDeliveryHandler(reopened, adapter, clock=self.clock.iso)})
        self.assertEqual(1, worker.run_once())
        current = service.list_reminders(self.actor)[0]
        self.assertEqual("delivered", current["status"])
        self.assertEqual(1, len(adapter.notifications))

    def test_upcoming_reminder_exposes_derived_due_now_and_task_timezone(self):
        task, reminder, _, service = self._reminder()
        service = ReminderService(self.db, clock=self.clock.iso)
        listed = service.list_upcoming_reminders(self.actor, now=self.clock.iso())
        self.assertTrue(next(item for item in listed if item["id"] == reminder["id"])["due_now"])
        self.assertEqual("UTC", next(item for item in listed if item["id"] == reminder["id"])["timezone"])

    def test_ubuntu_adapter_uses_fixed_argv_without_a_shell_and_bounds_text(self):
        with patch("pathlib.Path.is_file", return_value=True), patch("subprocess.run") as run:
            run.return_value.returncode = 0
            UbuntuNotificationAdapter(timeout_seconds=3).notify("T" * 200, "M" * 900)
        args, kwargs = run.call_args
        self.assertEqual("/usr/bin/notify-send", args[0][0])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(3, kwargs["timeout"])
        self.assertEqual(100, len(args[0][1]))
        self.assertEqual(500, len(args[0][2]))

    def test_snooze_dismiss_and_deadline_change_invalidate_old_occurrence(self):
        task, reminder, tasks, service = self._reminder()
        queue = JobQueue(self.db, clock=self.clock)
        service.reconcile_reminders(now=self.clock.iso())
        snoozed = service.snooze_reminder(reminder["id"], "2027-01-01T00:05:00Z", self.actor)
        self.assertEqual(2, snoozed["generation"])
        self.assertEqual("cancelled", queue.list_jobs()[0]["status"])
        adapter = FakeNotificationAdapter()
        Worker(queue, {"reminder.deliver": ReminderDeliveryHandler(self.db, adapter, clock=self.clock.iso)}).run_once()
        self.assertEqual([], adapter.notifications)
        service.dismiss_reminder(reminder["id"], self.actor)
        self.assertEqual("dismissed", service.list_reminders(self.actor)[0]["status"])

        task, relative, tasks, service = self._reminder(scheduled="2027-01-01T01:00:00Z", relative=True)
        service.reconcile_reminders(now="2027-01-01T01:00:00Z")
        before = next(item for item in service.list_reminders(self.actor) if item["id"] == relative["id"])
        tasks.update_task(task["id"], {"due_at": "2027-01-02T02:00:00Z", "due_date": "2027-01-02"}, self.actor)
        after = next(item for item in service.list_reminders(self.actor) if item["id"] == relative["id"])
        self.assertEqual(before["generation"] + 1, after["generation"])
        self.assertEqual("2027-01-02T01:00:00Z", after["scheduled_at"])

    def test_failed_notification_retries_and_never_marks_delivered(self):
        _, reminder, _, service = self._reminder()
        queue = JobQueue(self.db, clock=self.clock)
        service.reconcile_reminders(now=self.clock.iso())
        worker = Worker(queue, {"reminder.deliver": ReminderDeliveryHandler(self.db, FakeNotificationAdapter(fail=True), clock=self.clock.iso)})
        worker.run_once()
        self.assertEqual("scheduled", service.list_reminders(self.actor)[0]["status"])
        self.assertEqual("retry_wait", queue.list_jobs()[0]["status"])

    def test_terminal_notification_failure_is_a_missed_reminder(self):
        _, reminder, _, service = self._reminder()
        queue = JobQueue(self.db, clock=self.clock)
        queue.enqueue("reminder.deliver", {"reminder_id": reminder["id"], "generation": reminder["generation"]},
                      f"reminder:{reminder['id']}:generation:{reminder['generation']}", max_attempts=1)
        worker = Worker(queue, {"reminder.deliver": ReminderDeliveryHandler(self.db, FakeNotificationAdapter(fail=True), clock=self.clock.iso)})
        worker.run_once()
        self.assertEqual("missed", service.list_reminders(self.actor)[0]["status"])
        self.assertEqual("failed", queue.list_jobs()[0]["status"])

    def test_reminder_cancel_invalidates_queued_delivery(self):
        _, reminder, _, service = self._reminder()
        queue = JobQueue(self.db, clock=self.clock)
        service.reconcile_reminders(now=self.clock.iso())
        service.cancel_reminder(reminder["id"], self.actor)
        self.assertEqual("cancelled", queue.list_jobs()[0]["status"])
        self.assertEqual("cancelled", service.list_reminders(self.actor)[0]["status"])

    def test_approval_lifecycle_exact_arguments_single_use_and_policy_recheck(self):
        policy = RequireThenAllowPolicy()
        fired = []
        service = ApprovalService(self.db, policy, clock=self.clock,
                                  handlers={"workspace.write": lambda args: fired.append(args.copy())})
        ACTION_RISK["workspace.write"] = __import__("ubuntu_agent.models", fromlist=["RiskTier"]).RiskTier.REVERSIBLE_WRITE
        self.addCleanup(ACTION_RISK.pop, "workspace.write", None)
        approval = service.request_approval(action_type="workspace.write", resource_id="file-1", room_id="operations",
            destination="local", arguments={"path": "notes.txt", "content": "safe"}, actor=self.actor)
        with self.assertRaises(PolicyDeniedError):
            service.consume(approval["id"], action_type="workspace.write", resource_id="file-1", room_id="operations",
                destination="local", arguments={"path": "notes.txt", "content": "changed"}, actor=self.actor)
        # Changed arguments invalidated the approval.
        invalidated = next(item for item in service.list_approvals(self.actor, include_terminal=True) if item["id"] == approval["id"])
        self.assertEqual("invalidated", invalidated["status"])

        approval = service.request_approval(action_type="workspace.write", resource_id="file-1", room_id="operations",
            destination="local", arguments={"path": "notes.txt", "content": "safe"}, actor=self.actor)
        service.decide(approval["id"], "approve", self.actor)
        result = service.consume(approval["id"], action_type="workspace.write", resource_id="file-1", room_id="operations",
            destination="local", arguments={"path": "notes.txt", "content": "safe"}, actor=self.actor)
        self.assertIsNone(result)
        with self.assertRaises(ConflictError):
            service.consume(approval["id"], action_type="workspace.write", resource_id="file-1", room_id="operations",
                destination="local", arguments={"path": "notes.txt", "content": "safe"}, actor=self.actor)
        self.assertEqual(1, len(fired))

    def test_approval_expiry_rejection_revocation_policy_denial_and_unsupported_action(self):
        policy = RequireThenAllowPolicy()
        service = ApprovalService(self.db, policy, clock=self.clock, handlers={})
        ACTION_RISK["workspace.write"] = __import__("ubuntu_agent.models", fromlist=["RiskTier"]).RiskTier.REVERSIBLE_WRITE
        self.addCleanup(ACTION_RISK.pop, "workspace.write", None)
        make = lambda: service.request_approval(action_type="workspace.write", resource_id="x", room_id="operations",
            destination="local", arguments={"x": 1}, actor=self.actor)
        rejected = make()
        service.decide(rejected["id"], "reject", self.actor)
        with self.assertRaises(ConflictError): service.consume(rejected["id"], action_type="workspace.write", resource_id="x", room_id="operations", destination="local", arguments={"x": 1}, actor=self.actor)
        revoked = make()
        service.decide(revoked["id"], "approve", self.actor)
        service.revoke(revoked["id"], self.actor)
        with self.assertRaises(ConflictError): service.consume(revoked["id"], action_type="workspace.write", resource_id="x", room_id="operations", destination="local", arguments={"x": 1}, actor=self.actor)
        expiring = make()
        self.clock.advance(901)
        service.list_approvals(self.actor)
        self.assertEqual("expired", next(x for x in service.list_approvals(self.actor, include_terminal=True) if x["id"] == expiring["id"])["status"])
        policy.denied = True
        with self.assertRaises(PolicyDeniedError): make()
        with self.assertRaises(PolicyDeniedError):
            ApprovalService(self.db).request_approval(action_type="shell.execute", resource_id="shell", room_id="operations",
                destination="local", arguments={"command": "anything"}, actor=self.actor)
        unsupported = ApprovalService(self.db, RequireThenAllowPolicy(), clock=self.clock, handlers={})
        request = unsupported.request_approval(action_type="shell.execute", resource_id="shell", room_id="operations",
            destination="local", arguments={"command": "anything"}, actor=self.actor)
        unsupported.decide(request["id"], "approve", self.actor)
        with self.assertRaises(PolicyDeniedError):
            unsupported.consume(request["id"], action_type="shell.execute", resource_id="shell", room_id="operations",
                destination="local", arguments={"command": "anything"}, actor=self.actor)

    def test_approval_concurrent_consumption_and_policy_denial_at_execution(self):
        policy = RequireThenAllowPolicy()
        fired = []
        service = ApprovalService(self.db, policy, clock=self.clock,
                                  handlers={"workspace.write": lambda args: fired.append(args.copy())})
        ACTION_RISK["workspace.write"] = __import__("ubuntu_agent.models", fromlist=["RiskTier"]).RiskTier.REVERSIBLE_WRITE
        self.addCleanup(ACTION_RISK.pop, "workspace.write", None)
        approval = service.request_approval(action_type="workspace.write", resource_id="file-2", room_id="operations",
            destination="local", arguments={"path": "x"}, actor=self.actor)
        service.decide(approval["id"], "approve", self.actor)
        policy.denied = True
        with self.assertRaises(PolicyDeniedError):
            service.consume(approval["id"], action_type="workspace.write", resource_id="file-2", room_id="operations",
                destination="local", arguments={"path": "x"}, actor=self.actor)
        policy.denied = False
        results = []
        barrier = threading.Barrier(3)

        def consume():
            barrier.wait()
            try:
                service.consume(approval["id"], action_type="workspace.write", resource_id="file-2", room_id="operations",
                    destination="local", arguments={"path": "x"}, actor=self.actor)
                results.append("ok")
            except Exception:
                results.append("denied")

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertCountEqual(["ok", "denied"], results)
        self.assertEqual(1, len(fired))

    def test_persisted_pause_and_kill_block_approved_action_service_dispatch(self):
        policy = RequireThenAllowPolicy()
        fired = []
        service = ApprovalService(self.db, policy, clock=self.clock,
                                  handlers={"workspace.write": lambda args: fired.append(args.copy())})
        ACTION_RISK["workspace.write"] = __import__("ubuntu_agent.models", fromlist=["RiskTier"]).RiskTier.REVERSIBLE_WRITE
        self.addCleanup(ACTION_RISK.pop, "workspace.write", None)
        approval = service.request_approval(action_type="workspace.write", resource_id="file-3", room_id="operations",
            destination="local", arguments={"path": "x"}, actor=self.actor)
        service.decide(approval["id"], "approve", self.actor)
        runtime = RuntimeControlService(self.db)
        runtime.pause(self.actor)
        with self.assertRaises(PolicyDeniedError):
            service.consume(approval["id"], action_type="workspace.write", resource_id="file-3", room_id="operations",
                destination="local", arguments={"path": "x"}, actor=self.actor)
        runtime.resume(self.actor)
        runtime.kill(self.actor)
        with self.assertRaises(PolicyDeniedError):
            service.consume(approval["id"], action_type="workspace.write", resource_id="file-3", room_id="operations",
                destination="local", arguments={"path": "x"}, actor=self.actor)
        runtime.recover(self.actor)
        service.consume(approval["id"], action_type="workspace.write", resource_id="file-3", room_id="operations",
            destination="local", arguments={"path": "x"}, actor=self.actor)
        self.assertEqual(1, len(fired))


if __name__ == "__main__":
    unittest.main()
