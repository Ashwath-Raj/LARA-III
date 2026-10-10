"""Durable SQLite queue with leases, bounded retries, and registered handlers."""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from .database import Database
from .runtime import RuntimeControlService

MAX_ATTEMPTS = 5
MAX_BACKOFF_SECONDS = 3600
LEASE_SECONDS = 60


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class JobValidationError(ValueError):
    pass


class JobNotFoundError(LookupError):
    pass


class JobQueue:
    def __init__(self, database: Database, *, clock: Callable[[], datetime] | None = None):
        self.database = database
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def enqueue(self, job_type: str, payload: dict, idempotency_key: str, *, max_attempts: int = MAX_ATTEMPTS) -> dict:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self.enqueue_in_transaction(connection, job_type, payload, idempotency_key, max_attempts=max_attempts)

    def enqueue_in_transaction(self, connection: sqlite3.Connection, job_type: str, payload: dict,
                               idempotency_key: str, *, max_attempts: int = MAX_ATTEMPTS) -> dict:
        validate_payload(job_type, payload)
        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 300:
            raise JobValidationError("Invalid idempotency key.")
        if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_ATTEMPTS:
            raise JobValidationError("Retry limit must be between 1 and 5.")
        now = _iso(self.clock())
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 65536:
            raise JobValidationError("Job payload exceeds the size limit.")
        existing = connection.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            if existing["job_type"] != job_type or existing["payload_json"] != encoded:
                raise JobValidationError("Idempotency key conflicts with a different job.")
            return dict(existing)
        job_id = str(uuid.uuid4())
        connection.execute("""INSERT INTO jobs(id,job_type,payload_json,idempotency_key,status,attempts,max_attempts,
          available_at,created_at,updated_at) VALUES(?,?,?,?,'queued',0,?,?,?,?)""",
          (job_id, job_type, encoded, idempotency_key, max_attempts, now, now, now))
        return dict(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list_jobs(self) -> list[dict]:
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM jobs ORDER BY created_at")]

    def cancel(self, job_id: str) -> dict:
        now = _iso(self.clock())
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFoundError("Job not found.")
            if row["status"] in ("succeeded", "failed", "cancelled"):
                return dict(row)
            if row["job_type"] == "reminder.deliver":
                try:
                    payload = decode_payload(row["payload_json"])
                    if isinstance(payload, dict) and set(payload) == {"reminder_id", "generation"}:
                        reminder = connection.execute("SELECT status,generation FROM reminders WHERE id=?",
                                                      (payload["reminder_id"],)).fetchone()
                        if reminder is not None and reminder["generation"] == payload["generation"] and reminder["status"] == "delivered":
                            return dict(row)
                        connection.execute("""UPDATE reminders SET status='cancelled',generation=generation+1,updated_at=?
                          WHERE id=? AND generation=? AND status IN ('scheduled','snoozed','missed')""",
                          (now, payload["reminder_id"], payload["generation"]))
                except JobValidationError:
                    pass
            connection.execute("UPDATE jobs SET status='cancelled',cancelled_at=?,finished_at=?,updated_at=?,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
                               (now, now, now, job_id))
            return dict(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def release(self, job_id: str, owner: str) -> None:
        now = _iso(self.clock())
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""UPDATE jobs SET status='queued',attempts=MAX(0,attempts-1),lease_owner=NULL,
              lease_expires_at=NULL,available_at=?,updated_at=? WHERE id=? AND status='running' AND lease_owner=?""",
              (now, now, job_id, owner))

    def claim(self, owner: str, *, limit: int = 10, lease_seconds: int = LEASE_SECONDS) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(lease_seconds) is not int or not 5 <= lease_seconds <= 3600:
            raise ValueError("Invalid claim bounds.")
        now_dt = self.clock().astimezone(timezone.utc)
        now, expiry = _iso(now_dt), _iso(now_dt + timedelta(seconds=lease_seconds))
        claimed = []
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            expired = connection.execute("SELECT * FROM jobs WHERE status='running' AND lease_expires_at<=?", (now,)).fetchall()
            for row in expired:
                terminal = row["attempts"] >= row["max_attempts"]
                status = "failed" if terminal else "retry_wait"
                delay = min(30 * (2 ** max(0, row["attempts"] - 1)), MAX_BACKOFF_SECONDS)
                connection.execute("""UPDATE jobs SET status=?,available_at=?,error_class='worker_lease_expired',
                  lease_owner=NULL,lease_expires_at=NULL,finished_at=?,updated_at=? WHERE id=?""",
                  (status, now if terminal else _iso(now_dt + timedelta(seconds=delay)), now if terminal else None, now, row["id"]))
            controls = connection.execute("SELECT paused,killed FROM runtime_controls WHERE singleton=1").fetchone()
            if controls["killed"]:
                return []
            eligible = connection.execute("""SELECT * FROM jobs WHERE status IN ('queued','retry_wait') AND available_at<=?
              ORDER BY available_at,created_at LIMIT ?""", (now, limit * 2)).fetchall()
            for row in eligible:
                if controls["paused"] and row["job_type"] != "reminder.deliver":
                    continue
                try:
                    validate_payload(row["job_type"], decode_payload(row["payload_json"]))
                except JobValidationError:
                    connection.execute("UPDATE jobs SET status='failed',error_class='invalid_payload',finished_at=?,updated_at=? WHERE id=?",
                                       (now, now, row["id"]))
                    continue
                updated = connection.execute("""UPDATE jobs SET status='running',attempts=attempts+1,lease_owner=?,
                  lease_expires_at=?,started_at=COALESCE(started_at,?),updated_at=?
                  WHERE id=? AND status IN ('queued','retry_wait')""", (owner, expiry, now, now, row["id"]))
                if updated.rowcount:
                    claimed.append(dict(connection.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()))
                    if len(claimed) >= limit:
                        break
        return claimed

    def finish(self, job_id: str, owner: str, *, error_class: str | None = None,
               terminal: bool = False) -> dict:
        now_dt = self.clock().astimezone(timezone.utc)
        now = _iso(now_dt)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE id=? AND lease_owner=?", (job_id, owner)).fetchone()
            if row is None:
                raise RuntimeError("Job lease is no longer owned by this worker.")
            if row["status"] == "cancelled":
                return dict(row)
            if row["status"] != "running":
                raise RuntimeError("Job lease is no longer active.")
            if error_class is None:
                connection.execute("UPDATE jobs SET status='succeeded',finished_at=?,updated_at=?,lease_owner=NULL,lease_expires_at=NULL,error_class=NULL WHERE id=?",
                                   (now, now, job_id))
            else:
                safe_class = error_class if error_class in {"notification_unavailable", "notification_failed", "invalid_payload", "handler_unavailable", "handler_failed"} else "handler_failed"
                terminal = terminal or row["attempts"] >= row["max_attempts"]
                delay = min(30 * (2 ** max(0, row["attempts"] - 1)), MAX_BACKOFF_SECONDS)
                connection.execute("""UPDATE jobs SET status=?,available_at=?,finished_at=?,updated_at=?,error_class=?,
                  lease_owner=NULL,lease_expires_at=NULL WHERE id=?""",
                  ("failed" if terminal else "retry_wait", now if terminal else _iso(now_dt + timedelta(seconds=delay)),
                   now if terminal else None, now, safe_class, job_id))
            return dict(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def validate_payload(job_type: str, payload: object) -> None:
    if not isinstance(payload, dict):
        raise JobValidationError("Persisted job payload must be an object.")
    try:
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 65536:
            raise JobValidationError("Persisted job payload exceeds the size limit.")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise JobValidationError("Persisted job payload is malformed.") from exc
    if job_type == "reminder.deliver":
        if set(payload) != {"reminder_id", "generation"} or not isinstance(payload["reminder_id"], str) or type(payload["generation"]) is not int or payload["generation"] < 1:
            raise JobValidationError("Reminder job payload is malformed.")
        return
    if job_type == "autonomy.action":
        if (set(payload) != {"approval_id", "action_type", "arguments"}
                or not isinstance(payload["approval_id"], str) or not payload["approval_id"]
                or not isinstance(payload["action_type"], str) or not payload["action_type"]
                or not isinstance(payload["arguments"], dict)):
            raise JobValidationError("Autonomy action payload is malformed.")
        return
    raise JobValidationError("Job type is not registered.")


def decode_payload(payload_json: object) -> object:
    if not isinstance(payload_json, str) or len(payload_json) > 65536:
        raise JobValidationError("Persisted job payload is malformed.")
    try:
        return json.loads(payload_json)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise JobValidationError("Persisted job payload is malformed.") from exc


class Worker:
    def __init__(self, queue: JobQueue, handlers: dict[str, Callable[[dict], None]], *, owner: str | None = None):
        self.queue, self.handlers = queue, handlers
        self.owner = owner or str(uuid.uuid4())
        self.stop_event = threading.Event()

    def request_shutdown(self) -> None:
        self.stop_event.set()

    def run_once(self, *, batch_size: int = 10) -> int:
        jobs = self.queue.claim(self.owner, limit=batch_size)
        for index, job in enumerate(jobs):
            if self.stop_event.is_set():
                for unstarted in jobs[index:]:
                    self.queue.release(unstarted["id"], self.owner)
                break
            try:
                validate_payload(job["job_type"], decode_payload(job["payload_json"]))
                if job["job_type"] == "autonomy.action":
                    # This phase has no autonomous action dispatcher. Keep such
                    # jobs inert even if an unrelated callback is registered.
                    self.queue.finish(job["id"], self.owner, error_class="handler_unavailable", terminal=True)
                    continue
                handler = self.handlers.get(job["job_type"])
                if handler is None:
                    self.queue.finish(job["id"], self.owner, error_class="handler_unavailable", terminal=True)
                    continue
                controls = RuntimeControlService(self.queue.database).state()
                if controls["killed"] or (controls["paused"] and job["job_type"] != "reminder.deliver"):
                    self.queue.release(job["id"], self.owner)
                    continue
                handler(decode_payload(job["payload_json"]))
                self.queue.finish(job["id"], self.owner)
            except JobValidationError:
                self.queue.finish(job["id"], self.owner, error_class="invalid_payload")
            except Exception as exc:
                classification = getattr(exc, "classification", None)
                if classification not in {"notification_unavailable", "notification_failed"}:
                    classification = "handler_failed"
                result = self.queue.finish(job["id"], self.owner, error_class=classification)
                payload = decode_payload(job["payload_json"])
                now = _iso(self.queue.clock())
                with self.queue.database.connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if result["status"] == "failed" and job["job_type"] == "reminder.deliver":
                        connection.execute("""UPDATE reminders SET status='missed',updated_at=? WHERE id=?
                          AND generation=? AND status IN ('scheduled','snoozed')""",
                          (now, payload["reminder_id"], payload["generation"]))
                    target = payload.get("reminder_id", job["id"]) if isinstance(payload, dict) else job["id"]
                    metadata = json.dumps({"error_class": result["error_class"], "job_status": result["status"]}, separators=(",", ":"))
                    action = "reminder.delivery_failed" if job["job_type"] == "reminder.deliver" else "job.execution_failed"
                    connection.execute("INSERT INTO audit_events VALUES (?, ?, 'system', 'worker', ?, ?, 'allow', NULL, ?, NULL, ?)",
                                       (str(uuid.uuid4()), now, action, target, result["status"], metadata))
        return len(jobs)

    def run_forever(self, interval_seconds: float = 5.0) -> None:
        if not 0.1 <= interval_seconds <= 3600:
            raise ValueError("Polling interval must be between 0.1 and 3600 seconds.")
        while not self.stop_event.is_set():
            self.run_once()
            self.stop_event.wait(interval_seconds)

