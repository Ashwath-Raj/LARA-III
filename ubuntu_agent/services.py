"""Task and reminder application services; all protected access is policy checked here."""

import json
import re
import sqlite3
import uuid
import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bootstrap import PRINCIPAL_ID
from .database import Database
from .models import AccessContext, Actor, DecisionKind, utc_now
from .policy import ACTION_RISK, IMPLEMENTED_ACTIONS, PolicyEngine

TASK_STATUSES = {"inbox", "next", "in_progress", "waiting", "review", "ready_to_submit", "done", "archived"}
PRIORITIES = {"low", "normal", "high", "urgent"}
ITEM_TYPES = {"task", "assignment", "exam", "event", "idea", "follow_up", "research_job", "reminder"}
REMINDER_STATUSES = {"scheduled", "delivered", "missed", "snoozed", "dismissed", "cancelled"}
ROOM_SENSITIVITY = {"operations": "internal", "academic": "sensitive", "projects": "sensitive", "public_research": "public", "opportunities": "internal"}


class AgentError(Exception):
    code = "INTERNAL_ERROR"


class ValidationError(AgentError):
    code = "VALIDATION_ERROR"


class NotFoundError(AgentError):
    code = "NOT_FOUND"


class PolicyDeniedError(AgentError):
    code = "POLICY_DENIED"


class ApprovalRequiredError(AgentError):
    code = "APPROVAL_REQUIRED"


class ConflictError(AgentError):
    code = "CONFLICT"


def _validate_string(value: Any, field: str, *, required: bool = True, maximum: int = 4000) -> str:
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > maximum:
        raise ValidationError(f"Invalid {field}.")
    return value.strip()


def _validate_due_date(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("due_date must use YYYY-MM-DD.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValidationError("due_date must use YYYY-MM-DD.") from exc


def _validate_instant(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO 8601 timezone-aware instant.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO 8601 timezone-aware instant.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{field} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fingerprint(fields: dict[str, Any]) -> str:
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative_schedule(due_at: str, offset_minutes: int) -> str:
    due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    return (due - timedelta(minutes=offset_minutes)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_deadline_pair(due_date: str | None, due_at: str | None, timezone_name: str) -> None:
    if due_date is None or due_at is None:
        return
    instant = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    local_date = instant.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    if local_date != due_date:
        raise ValidationError("due_date must match due_at in the task timezone.")


def _invalidate_reminder_jobs(connection: sqlite3.Connection, reminder_id: str, generation: int, now: str) -> None:
    """Cancel queued work for one superseded occurrence in the caller's transaction."""
    rows = connection.execute("SELECT id,payload_json FROM jobs WHERE job_type='reminder.deliver' AND status IN ('queued','retry_wait')").fetchall()
    for job in rows:
        try:
            payload = json.loads(job["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("reminder_id") == reminder_id and payload.get("generation") == generation:
            connection.execute("UPDATE jobs SET status='cancelled',cancelled_at=?,finished_at=?,updated_at=? WHERE id=?",
                               (now, now, now, job["id"]))


class BaseService:
    def __init__(self, database: Database, policy: PolicyEngine | None = None):
        self.database = database
        self.policy = policy or PolicyEngine()

    def _authorize(self, connection: sqlite3.Connection, actor: Actor, room_id: str, resource_id: str,
                   action_id: str, *, hide_denial: bool = False, approval_id: str | None = None) -> None:
        """Resolve trusted metadata, evaluate policy, apply owner scope, then audit final result."""
        reason_code = "context_invalid"
        allowed = False
        actor_valid = (isinstance(actor, Actor) and type(actor.principal_id) is str
                       and type(actor.persona_id) is str and actor.principal_id == PRINCIPAL_ID)
        persona = None
        room = None
        if actor_valid:
            persona = connection.execute("SELECT policy_profile_id,is_enabled FROM personas WHERE id=?", (actor.persona_id,)).fetchone()
            room = connection.execute("SELECT sensitivity_default FROM rooms WHERE id=?", (room_id,)).fetchone() if type(room_id) is str else None
        if actor_valid and persona is not None and persona["is_enabled"] and room is not None and ROOM_SENSITIVITY.get(room_id) == room["sensitivity_default"]:
            risk = ACTION_RISK.get(action_id)
            if risk is not None and action_id in IMPLEMENTED_ACTIONS:
                try:
                    context = AccessContext(actor.principal_id, actor.persona_id, None, room_id, resource_id,
                                            action_id, room["sensitivity_default"], "local", risk.value,
                                            "normal", approval_id)
                    decision = self.policy.evaluate_access(context)
                    allowed = decision.decision == DecisionKind.ALLOW
                    reason_code = "policy_allow" if allowed else "policy_deny"
                except Exception:
                    allowed = False
                    reason_code = "policy_failure"
                if allowed and action_id != "task.create" and room_id != "operations":
                    owner = connection.execute("SELECT persona_owner FROM tasks WHERE id=?", (resource_id,)).fetchone()
                    if owner is None or owner["persona_owner"] != actor.persona_id:
                        allowed = False
                        reason_code = "owner_scope_denied"
        self._audit(connection, actor if isinstance(actor, Actor) else None, action_id, resource_id,
                    "allow" if allowed else "deny", "authorized" if allowed else reason_code)
        if not allowed:
            # This commits only the read-side authorization audit; all callers invoke
            # the check before their protected mutation.
            connection.commit()
            if hide_denial:
                raise NotFoundError("Task not found.")
            raise PolicyDeniedError("Access denied.")

    @staticmethod
    def _audit(connection: sqlite3.Connection, actor: Actor | None, action: str, target: str | None,
               decision: str, result: str) -> None:
        actor_id = actor.principal_id if actor is not None and type(actor.principal_id) is str else "unresolved"
        metadata = json.dumps({"diagnostic": result}, separators=(",", ":"))
        connection.execute("INSERT INTO audit_events VALUES (?, ?, 'user', ?, ?, ?, ?, NULL, ?, NULL, ?)",
                           (str(uuid.uuid4()), utc_now(), actor_id, action, target, decision, result, metadata))

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None


class TaskService(BaseService):
    def create_task(self, candidate: dict[str, Any], actor: Actor, idempotency_key: str | None = None) -> dict[str, Any]:
        if not isinstance(candidate, dict):
            raise ValidationError("Task candidate must be an object.")
        candidate_fields = {"title", "description", "item_type", "status", "priority", "category", "room_id",
                            "due_date", "due_at", "timezone", "source_text"}
        if set(candidate) - candidate_fields:
            raise ValidationError("Task candidate contains unsupported fields.")
        title = _validate_string(candidate.get("title"), "title", maximum=300)
        description = _validate_string(candidate.get("description", ""), "description", required=False)
        item_type = candidate.get("item_type", "task")
        status = candidate.get("status", "inbox")
        priority = candidate.get("priority", "normal")
        category = candidate.get("category", "Personal / Admin")
        room_id = candidate.get("room_id", "operations")
        due_date = _validate_due_date(candidate.get("due_date"))
        due_at = _validate_instant(candidate["due_at"], "due_at") if candidate.get("due_at") is not None else None
        timezone_name = candidate.get("timezone", "UTC")
        if (type(item_type) is not str or item_type not in ITEM_TYPES or type(status) is not str or status != "inbox"
            or type(priority) is not str or priority not in PRIORITIES):
            raise ValidationError("Invalid item_type, status, or priority.")
        if type(category) is not str or type(room_id) is not str:
            raise ValidationError("Invalid category or room identifier.")
        if not isinstance(timezone_name, str) or not re.fullmatch(r"[A-Za-z0-9_+./-]{1,64}", timezone_name):
            raise ValidationError("Invalid timezone.")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Unknown timezone.") from exc
        _validate_deadline_pair(due_date, due_at, timezone_name)
        if idempotency_key is not None:
            _validate_string(idempotency_key, "idempotency_key", maximum=200)
        if room_id not in ROOM_SENSITIVITY:
            raise ValidationError("Unknown task room.")
        source_text = _validate_string(candidate.get("source_text", ""), "source_text", required=False)
        task_id = str(uuid.uuid4())
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            category_row = connection.execute("SELECT id FROM categories WHERE name = ? AND is_active = 1", (category,)).fetchone()
            if category_row is None:
                raise ValidationError("Unknown or inactive category.")
            fingerprint = _fingerprint({"title": title, "description": description, "item_type": item_type,
                "status": status, "priority": priority, "category_id": category_row["id"], "room_id": room_id,
                "due_date": due_date, "due_at": due_at, "timezone": timezone_name, "source_text": source_text})
            if idempotency_key:
                if not isinstance(actor, Actor) or type(actor.principal_id) is not str or type(actor.persona_id) is not str:
                    raise PolicyDeniedError("Access denied.")
                existing = connection.execute("""SELECT keys.request_fingerprint,keys.task_id,tasks.room_id
                    FROM task_idempotency_keys AS keys JOIN tasks ON tasks.id=keys.task_id
                    WHERE keys.principal_id=? AND keys.persona_id=? AND keys.idempotency_key=?""",
                    (actor.principal_id, actor.persona_id, idempotency_key)).fetchone()
                if existing:
                    self._authorize(connection, actor, existing["room_id"], existing["task_id"], "task.read", hide_denial=True)
                    if existing["request_fingerprint"] != fingerprint:
                        self._audit(connection, actor, "task.create", existing["task_id"], "allow", "idempotency_conflict")
                        raise ConflictError("Idempotency key was already used for a different request.")
                    return self._task_row(connection, existing["task_id"])
            self._authorize(connection, actor, room_id, task_id, "task.create")
            connection.execute("""INSERT INTO tasks
              (id,title,description,item_type,status,priority,category_id,room_id,persona_owner,due_date,due_at,timezone,source_text,created_at,updated_at,idempotency_key)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
              (task_id,title,description,item_type,status,priority,category_row["id"],room_id,actor.persona_id,due_date,due_at,
               timezone_name,source_text,now,now))
            if idempotency_key:
                connection.execute("""INSERT INTO task_idempotency_keys
                    (principal_id,persona_id,idempotency_key,request_fingerprint,task_id,created_at)
                    VALUES (?,?,?,?,?,?)""", (actor.principal_id,actor.persona_id,idempotency_key,fingerprint,task_id,now))
            self._audit(connection, actor, "task.create", task_id, "allow", "succeeded")
            return self._task_row(connection, task_id)

    @staticmethod
    def _task_row(connection: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        row = connection.execute("""SELECT tasks.*, categories.name AS category FROM tasks
          JOIN categories ON categories.id=tasks.category_id WHERE tasks.id=?""", (task_id,)).fetchone()
        return dict(row)

    def get_task(self, task_id: str, actor: Actor) -> dict[str, Any]:
        _validate_string(task_id, "task_id", maximum=100)
        with self.database.connect() as connection:
            row = connection.execute("SELECT id,room_id FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise NotFoundError("Task not found.")
            self._authorize(connection, actor, row["room_id"], task_id, "task.read", hide_denial=True)
            return self._task_row(connection, task_id)

    def list_tasks(self, actor: Actor, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and (type(status) is not str or status not in TASK_STATUSES):
            raise ValidationError("Invalid task status.")
        with self.database.connect() as connection:
            rows = connection.execute("SELECT id,room_id FROM tasks WHERE (? IS NULL OR status=?) ORDER BY due_date,created_at", (status,status)).fetchall()
            result = []
            for row in rows:
                try:
                    self._authorize(connection, actor, row["room_id"], row["id"], "task.read", hide_denial=True)
                except NotFoundError:
                    continue
                result.append(self._task_row(connection, row["id"]))
            return result

    def update_task(self, task_id: str, patch: dict[str, Any], actor: Actor) -> dict[str, Any]:
        _validate_string(task_id, "task_id", maximum=100)
        if not isinstance(patch, dict) or not patch:
            raise ValidationError("Patch must be a non-empty object.")
        allowed = {"title", "description", "priority", "category", "due_date", "due_at", "timezone"}
        if set(patch) - allowed:
            raise ValidationError("Patch contains unsupported fields.")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id,room_id FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise NotFoundError("Task not found.")
            self._authorize(connection, actor, row["room_id"], task_id, "task.update", hide_denial=True)
            current = self._task_row(connection, task_id)
            values = {"title": current["title"], "description": current["description"], "priority": current["priority"],
                      "category_id": current["category_id"], "due_date": current["due_date"],
                      "due_at": current["due_at"], "timezone": current["timezone"]}
            if "title" in patch: values["title"] = _validate_string(patch["title"], "title", maximum=300)
            if "description" in patch: values["description"] = _validate_string(patch["description"], "description", required=False)
            if "priority" in patch:
                if type(patch["priority"]) is not str or patch["priority"] not in PRIORITIES: raise ValidationError("Invalid priority.")
                values["priority"] = patch["priority"]
            if "category" in patch:
                category_name = _validate_string(patch["category"], "category", maximum=100)
                rowcat = connection.execute("SELECT id FROM categories WHERE name=? AND is_active=1", (category_name,)).fetchone()
                if rowcat is None: raise ValidationError("Unknown or inactive category.")
                values["category_id"] = rowcat["id"]
            if "due_date" in patch: values["due_date"] = _validate_due_date(patch["due_date"])
            if "due_at" in patch:
                values["due_at"] = _validate_instant(patch["due_at"], "due_at") if patch["due_at"] is not None else None
            if "timezone" in patch:
                if not isinstance(patch["timezone"], str) or not re.fullmatch(r"[A-Za-z0-9_+./-]{1,64}", patch["timezone"]): raise ValidationError("Invalid timezone.")
                try: ZoneInfo(patch["timezone"])
                except ZoneInfoNotFoundError as exc: raise ValidationError("Unknown timezone.") from exc
                values["timezone"] = patch["timezone"]
            _validate_deadline_pair(values["due_date"], values["due_at"], values["timezone"])
            deadline_changed = values["due_date"] != current["due_date"] or values["due_at"] != current["due_at"]
            reminder_updates: list[tuple[str, str, int]] = []
            if deadline_changed:
                active_reminders = connection.execute("SELECT id,rule_snapshot,generation FROM reminders WHERE task_id=? AND status IN ('scheduled','snoozed')", (task_id,)).fetchall()
                if ("due_date" in patch and values["due_date"] != current["due_date"]
                    and "due_at" not in patch and active_reminders):
                    raise ConflictError("Update due_at with due_date to safely reschedule active reminders.")
                for reminder in active_reminders:
                    try:
                        rule = json.loads(reminder["rule_snapshot"])
                        offset = rule.get("offset_minutes") if rule.get("kind") == "relative_to_due_at" else None
                        if type(offset) is not int or not 0 <= offset <= 525600 or values["due_at"] is None:
                            raise ValueError("Reminder rule is not safely reschedulable.")
                        reminder_updates.append((reminder["id"], _relative_schedule(values["due_at"], offset), reminder["generation"]))
                    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        raise ConflictError("A scheduled reminder cannot be safely rescheduled.") from exc
            connection.execute("""UPDATE tasks SET title=?,description=?,priority=?,category_id=?,due_date=?,due_at=?,timezone=?,updated_at=? WHERE id=?""",
                               (*values.values(), utc_now(), task_id))
            for reminder_id, scheduled_at, generation in reminder_updates:
                _invalidate_reminder_jobs(connection, reminder_id, generation, utc_now())
                connection.execute("UPDATE reminders SET scheduled_at=?,generation=generation+1,updated_at=? WHERE id=?",
                                   (scheduled_at, utc_now(), reminder_id))
            self._audit(connection, actor, "task.update", task_id, "allow", "succeeded")
            return self._task_row(connection, task_id)

    def transition_task(self, task_id: str, target_status: str, actor: Actor, *, evidence: str | None = None) -> dict[str, Any]:
        _validate_string(task_id, "task_id", maximum=100)
        if type(target_status) is not str or target_status not in TASK_STATUSES:
            raise ValidationError("Unknown task status.")
        with self.database.connect() as connection:
            row = connection.execute("SELECT id,room_id,status FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise NotFoundError("Task not found.")
            self._authorize(connection, actor, row["room_id"], task_id, "task.transition", hide_denial=True)
            allowed = {"inbox":{"next","in_progress","archived"}, "next":{"in_progress","waiting","archived"},
                       "in_progress":{"waiting","review","ready_to_submit","done","next"},
                       "waiting":{"next","in_progress","archived"}, "review":{"in_progress","ready_to_submit","done"},
                       "ready_to_submit":{"review","done"}, "done":{"archived","next"}, "archived":{"inbox"}}
            if target_status == row["status"] or target_status not in allowed[row["status"]]:
                raise ConflictError("Invalid task state transition.")
            if target_status == "done":
                evidence = _validate_string(evidence, "completion evidence")
            now = utc_now()
            connection.execute("UPDATE tasks SET status=?,completed_at=?,completion_evidence=?,updated_at=? WHERE id=?",
                               (target_status, now if target_status == "done" else None, evidence if target_status == "done" else None, now, task_id))
            self._audit(connection, actor, "task.transition", task_id, "allow", "succeeded")
            return self._task_row(connection, task_id)


class ReminderService(BaseService):
    def __init__(self, database: Database, policy: PolicyEngine | None = None, *, clock: Callable[[], str] | None = None):
        super().__init__(database, policy)
        self.clock = clock or utc_now

    def create_reminder(self, task_id: str, scheduled_at: str, message: str, actor: Actor,
                        *, reminder_type: str = "custom", offset_minutes: int | None = None) -> dict[str, Any]:
        _validate_string(task_id, "task_id", maximum=100)
        when = _validate_instant(scheduled_at, "scheduled_at")
        message = _validate_string(message, "message", maximum=1000)
        reminder_type = _validate_string(reminder_type, "reminder_type", maximum=100)
        reminder_id, now = str(uuid.uuid4()), self.clock()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute("SELECT id,room_id,due_at FROM tasks WHERE id=?", (task_id,)).fetchone()
            if task is None: raise NotFoundError("Task not found.")
            self._authorize(connection, actor, task["room_id"], task_id, "reminder.create", hide_denial=True)
            if reminder_type == "relative_to_due_at":
                if type(offset_minutes) is not int or not 0 <= offset_minutes <= 525600 or task["due_at"] is None:
                    raise ValidationError("A relative reminder requires a due_at value and offset from 0 to 525600 minutes.")
                expected = _relative_schedule(task["due_at"], offset_minutes)
                if when != expected:
                    raise ValidationError("scheduled_at does not match the relative deadline rule.")
                rule_snapshot = {"kind": "relative_to_due_at", "offset_minutes": offset_minutes}
            elif reminder_type == "custom" and offset_minutes is None:
                rule_snapshot = {"kind": "fixed", "scheduled_at": when}
            else:
                raise ValidationError("Unsupported reminder rule.")
            connection.execute("""INSERT INTO reminders(id,task_id,scheduled_at,reminder_type,message,status,delivery_channel,
              delivered_at,rule_snapshot,created_at,updated_at) VALUES (?,?,?,?,?,'scheduled','local',NULL,?,?,?)""",
                               (reminder_id,task_id,when,reminder_type,message,json.dumps(rule_snapshot, sort_keys=True),now,now))
            self._audit(connection, actor, "reminder.create", reminder_id, "allow", "succeeded")
            return dict(connection.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone())

    def list_reminders(self, actor: Actor, *, task_id: str | None = None) -> list[dict[str, Any]]:
        if task_id is not None: _validate_string(task_id, "task_id", maximum=100)
        with self.database.connect() as connection:
            rows = connection.execute("""SELECT reminders.*, tasks.room_id FROM reminders JOIN tasks ON tasks.id=reminders.task_id
                 WHERE (? IS NULL OR reminders.task_id=?) ORDER BY reminders.scheduled_at""", (task_id,task_id)).fetchall()
            visible = []
            for row in rows:
                try: self._authorize(connection, actor, row["room_id"], row["task_id"], "reminder.read", hide_denial=True)
                except NotFoundError: continue
                visible.append({k: row[k] for k in row.keys() if k != "room_id"})
            return visible

    def list_upcoming_reminders(self, actor: Actor, *, window_hours: int = 168, now: str | None = None) -> list[dict[str, Any]]:
        if type(window_hours) is not int or not 0 <= window_hours <= 8760:
            raise ValidationError("window_hours must be between 0 and 8760.")
        current = _validate_instant(now, "now") if now is not None else self.clock()
        end = (datetime.fromisoformat(current.replace("Z", "+00:00")) + timedelta(hours=window_hours)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self.database.connect() as connection:
            rows = connection.execute("""SELECT reminders.*,tasks.room_id,tasks.timezone FROM reminders JOIN tasks ON tasks.id=reminders.task_id
              WHERE reminders.status IN ('scheduled','snoozed','missed') AND reminders.scheduled_at<=?
              ORDER BY reminders.scheduled_at""", (end,)).fetchall()
            result = []
            for row in rows:
                try:
                    self._authorize(connection, actor, row["room_id"], row["task_id"], "reminder.read", hide_denial=True)
                except NotFoundError:
                    continue
                item = {key: row[key] for key in row.keys() if key != "room_id"}
                item["due_now"] = row["status"] == "scheduled" and row["scheduled_at"] <= current
                result.append(item)
            return result

    def snooze_reminder(self, reminder_id: str, until: str, actor: Actor) -> dict[str, Any]:
        _validate_string(reminder_id, "reminder_id", maximum=100)
        until_utc = _validate_instant(until, "until")
        now = self.clock()
        if until_utc <= now:
            raise ValidationError("Snooze time must be in the future.")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.*,t.room_id FROM reminders r JOIN tasks t ON t.id=r.task_id WHERE r.id=?", (reminder_id,)).fetchone()
            if row is None: raise NotFoundError("Reminder not found.")
            self._authorize(connection, actor, row["room_id"], row["task_id"], "reminder.create", hide_denial=True)
            if row["status"] not in ("scheduled", "missed", "snoozed"):
                raise ConflictError("Reminder cannot be snoozed from its current state.")
            _invalidate_reminder_jobs(connection, reminder_id, row["generation"], now)
            connection.execute("UPDATE reminders SET scheduled_at=?,status='snoozed',generation=generation+1,updated_at=? WHERE id=?",
                               (until_utc, now, reminder_id))
            self._audit(connection, actor, "reminder.snooze", reminder_id, "allow", "succeeded")
            return dict(connection.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone())

    def dismiss_reminder(self, reminder_id: str, actor: Actor) -> dict[str, Any]:
        return self._terminal_reminder(reminder_id, actor, "dismissed", "reminder.dismiss")

    def cancel_reminder(self, reminder_id: str, actor: Actor) -> dict[str, Any]:
        return self._terminal_reminder(reminder_id, actor, "cancelled", "reminder.cancel")

    def _terminal_reminder(self, reminder_id: str, actor: Actor, state: str, action: str) -> dict[str, Any]:
        _validate_string(reminder_id, "reminder_id", maximum=100)
        now = self.clock()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.*,t.room_id FROM reminders r JOIN tasks t ON t.id=r.task_id WHERE r.id=?", (reminder_id,)).fetchone()
            if row is None: raise NotFoundError("Reminder not found.")
            self._authorize(connection, actor, row["room_id"], row["task_id"], "reminder.create", hide_denial=True)
            if row["status"] not in ("scheduled", "missed", "snoozed"):
                raise ConflictError("Reminder is already terminal.")
            _invalidate_reminder_jobs(connection, reminder_id, row["generation"], now)
            connection.execute("UPDATE reminders SET status=?,generation=generation+1,updated_at=? WHERE id=?", (state, now, reminder_id))
            self._audit(connection, actor, action, reminder_id, "allow", "succeeded")
            return dict(connection.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone())

    def reconcile_reminders(self, task_id: str | None = None, *, now: str | None = None) -> dict[str, int]:
        from .jobs import JobQueue
        if task_id is not None:
            _validate_string(task_id, "task_id", maximum=100)
        current = _validate_instant(now, "now") if now is not None else self.clock()
        queued = 0
        queue = JobQueue(self.database, clock=lambda: datetime.fromisoformat(self.clock().replace("Z", "+00:00")))
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""SELECT r.id,r.generation FROM reminders r WHERE r.status IN ('scheduled','snoozed')
              AND r.scheduled_at<=? AND (? IS NULL OR r.task_id=?) ORDER BY r.scheduled_at""", (current, task_id, task_id)).fetchall()
            for row in rows:
                queue.enqueue_in_transaction(connection, "reminder.deliver", {"reminder_id": row["id"], "generation": row["generation"]},
                    f"reminder:{row['id']}:generation:{row['generation']}")
                queued += 1
        return {"eligible": len(rows), "enqueued": queued}

