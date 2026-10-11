"""Idempotent reminder delivery handler for the durable worker."""

import sqlite3
from typing import Callable

from .database import Database
from .jobs import JobValidationError
from .models import utc_now
from .notifications import NotificationAdapter


class ReminderDeliveryHandler:
    def __init__(self, database: Database, adapter: NotificationAdapter, *, clock: Callable[[], str] = utc_now):
        self.database, self.adapter, self.clock = database, adapter, clock

    def __call__(self, payload: dict) -> None:
        if set(payload) != {"reminder_id", "generation"} or not isinstance(payload.get("reminder_id"), str) or type(payload.get("generation")) is not int:
            raise JobValidationError("Reminder delivery payload is malformed.")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("""SELECT r.*,t.title AS task_title,c.killed FROM reminders r
              JOIN tasks t ON t.id=r.task_id CROSS JOIN runtime_controls c
              WHERE r.id=? AND c.singleton=1""", (payload["reminder_id"],)).fetchone()
            if row is None:
                raise JobValidationError("Reminder no longer exists.")
            if row["killed"]:
                raise RuntimeError("notification_unavailable")
            if row["generation"] != payload["generation"] or row["status"] not in ("scheduled", "snoozed"):
                return
            if row["scheduled_at"] > self.clock():
                return
            # Holding the SQLite write transaction prevents snooze/dismiss/reschedule
            # from making this occurrence stale between validation and dispatch.
            self.adapter.notify(row["task_title"][:100], row["message"][:500])
            now = self.clock()
            connection.execute("UPDATE reminders SET status='delivered',delivered_at=?,updated_at=? WHERE id=? AND generation=?",
                               (now, now, row["id"], row["generation"]))
            connection.execute("INSERT INTO audit_events VALUES (?, ?, 'system', 'reminder_worker', 'reminder.deliver', ?, 'allow', NULL, 'succeeded', NULL, '{}')",
                               (__import__('uuid').uuid4().hex, now, row["id"]))

