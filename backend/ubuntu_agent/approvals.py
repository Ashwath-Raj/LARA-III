"""Durable exact-action approvals; approvals never register or grant handlers."""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from .bootstrap import PRINCIPAL_ID
from .database import Database
from .models import AccessContext, Actor, DecisionKind, utc_now
from .policy import ACTION_RISK, PolicyEngine
from .services import PolicyDeniedError, ValidationError, ConflictError, NotFoundError, ROOM_SENSITIVITY


def _canonical(value: dict) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise ValidationError("Action arguments must be an object.")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError("Action arguments are not valid JSON values.") from exc
    if len(encoded.encode("utf-8")) > 32768:
        raise ValidationError("Action arguments exceed the size limit.")
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ApprovalService:
    def __init__(self, database: Database, policy: PolicyEngine | None = None, *, clock: Callable[[], datetime] | None = None,
                 handlers: dict[str, Callable[[dict], object]] | None = None):
        self.database, self.policy = database, policy or PolicyEngine()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.handlers = handlers or {}

    def request_approval(self, *, action_type: str, resource_id: str, room_id: str, destination: str | None,
                         arguments: dict, actor: Actor, persona_id: str | None = None, lifetime_minutes: int = 15) -> dict:
        if type(lifetime_minutes) is not int or not 1 <= lifetime_minutes <= 1440:
            raise ValidationError("Approval lifetime must be between 1 and 1440 minutes.")
        if not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID:
            raise PolicyDeniedError("Local user identity is required.")
        if persona_id is not None and persona_id != actor.persona_id:
            raise PolicyDeniedError("Requesting persona must match the active persona.")
        persona = actor.persona_id
        risk = ACTION_RISK.get(action_type)
        if risk is None:
            raise ValidationError("Unknown action type.")
        with self.database.connect() as connection:
            room = connection.execute("SELECT sensitivity_default FROM rooms WHERE id=?", (room_id,)).fetchone()
        if room is None or ROOM_SENSITIVITY.get(room_id) != room["sensitivity_default"]:
            raise PolicyDeniedError("Current policy denies this action.")
        args_json, digest = _canonical(arguments)
        context = AccessContext(actor.principal_id, persona, None, room_id, resource_id, action_type,
                                room["sensitivity_default"], destination or "local", risk.value, "normal")
        decision = self.policy.evaluate_access(context)
        if decision.decision == DecisionKind.DENY:
            self._audit(actor, "approval.request", resource_id, "deny", "policy_denied", None)
            raise PolicyDeniedError("Current policy denies this action; approval cannot override it.")
        if decision.decision != DecisionKind.REQUIRES_APPROVAL:
            raise ValidationError("This action does not require an approval under current policy.")
        approval_id = str(uuid.uuid4())
        now = self.clock().astimezone(timezone.utc)
        created, expires = now.isoformat(timespec="seconds").replace("+00:00", "Z"), (now + timedelta(minutes=lifetime_minutes)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""INSERT INTO approvals(id,principal_id,persona_id,action_type,risk_tier,resource_id,room_id,destination,
              arguments_json,arguments_hash,policy_id,status,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)""",
              (approval_id, actor.principal_id, persona, action_type, risk.value, resource_id, room_id, destination,
               args_json, digest, decision.policy_id, created, expires))
            self._audit_conn(connection, actor, "approval.request", approval_id, "allow", "pending")
            return dict(connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())

    def list_approvals(self, actor: Actor, *, include_terminal: bool = False) -> list[dict]:
        self._check_actor(actor)
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            expired = connection.execute("SELECT id FROM approvals WHERE status='pending' AND expires_at<=?", (now,)).fetchall()
            for row in expired:
                connection.execute("UPDATE approvals SET status='expired' WHERE id=?", (row["id"],))
                self._audit_conn(connection, actor, "approval.expire", row["id"], "allow", "expired")
            sql = "SELECT * FROM approvals" if include_terminal else "SELECT * FROM approvals WHERE status='pending'"
            return [dict(row) for row in connection.execute(sql + " ORDER BY created_at DESC")]

    def decide(self, approval_id: str, decision: str, actor: Actor, *, reason: str = "") -> dict:
        self._check_actor(actor)
        if decision not in ("approve", "reject"):
            raise ValidationError("Decision must be approve or reject.")
        if reason not in ("", "scope_changed", "no_longer_needed", "other"):
            raise ValidationError("Use a safe decision reason code; free-form prompt content is not accepted.")
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None: raise NotFoundError("Approval not found.")
            if row["status"] == "pending" and row["expires_at"] <= now:
                connection.execute("UPDATE approvals SET status='expired' WHERE id=?", (approval_id,))
                self._audit_conn(connection, actor, "approval.expire", approval_id, "allow", "expired")
                connection.commit()
                raise ConflictError("Approval has expired.")
            if row["status"] != "pending": raise ConflictError("Approval is no longer pending.")
            status = "approved" if decision == "approve" else "rejected"
            connection.execute("UPDATE approvals SET status=?,decided_at=?,decided_by=?,decision_reason=? WHERE id=? AND status='pending'",
                               (status, now, actor.principal_id, reason[:300], approval_id))
            self._audit_conn(connection, actor, f"approval.{decision}", approval_id, "allow", status)
            return dict(connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())

    def revoke(self, approval_id: str, actor: Actor) -> dict:
        return self._change(approval_id, actor, "revoked", {"pending", "approved"}, "approval.revoke")

    def invalidate(self, approval_id: str, actor: Actor) -> dict:
        return self._change(approval_id, actor, "invalidated", {"pending", "approved"}, "approval.invalidate")

    def consume(self, approval_id: str, *, action_type: str, resource_id: str, room_id: str,
                destination: str | None, arguments: dict, actor: Actor) -> object:
        self._check_actor(actor)
        args_json, digest = _canonical(arguments)
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None: raise NotFoundError("Approval not found.")
            if row["status"] == "pending" and row["expires_at"] <= now:
                connection.execute("UPDATE approvals SET status='expired' WHERE id=?", (approval_id,))
                self._audit_conn(connection, actor, "approval.expire", approval_id, "allow", "expired")
                connection.commit()
                raise ConflictError("Approval has expired.")
            exact = (row["principal_id"] == actor.principal_id and row["persona_id"] == actor.persona_id
                     and row["action_type"] == action_type and row["resource_id"] == resource_id
                     and row["room_id"] == room_id and row["destination"] == destination
                     and row["arguments_hash"] == digest and row["arguments_json"] == args_json)
            if not exact:
                if row["status"] in ("pending", "approved"):
                    connection.execute("UPDATE approvals SET status='invalidated' WHERE id=?", (approval_id,))
                    self._audit_conn(connection, actor, "approval.invalidate", approval_id, "deny", "arguments_changed")
                    connection.commit()
                raise PolicyDeniedError("Approval does not match this exact action.")
            if row["status"] != "approved": raise ConflictError("Approval is expired, revoked, rejected or already consumed.")
            controls = connection.execute("SELECT paused,killed FROM runtime_controls WHERE singleton=1").fetchone()
            if controls["killed"] or controls["paused"]:
                self._audit_conn(connection, actor, "approval.consume", approval_id, "deny", "runtime_stopped")
                connection.commit()
                raise PolicyDeniedError("Runtime controls block action execution.")
            # Re-evaluate current policy and require allow. Approval is not an override.
            room = connection.execute("SELECT sensitivity_default FROM rooms WHERE id=?", (room_id,)).fetchone()
            if room is None or ROOM_SENSITIVITY.get(room_id) != room["sensitivity_default"]:
                self._audit_conn(connection, actor, "approval.consume", approval_id, "deny", "room_unavailable")
                connection.commit()
                raise PolicyDeniedError("Current policy does not allow execution.")
            decision = self.policy.evaluate_access(AccessContext(actor.principal_id, actor.persona_id, None,
                room_id, resource_id, action_type, room["sensitivity_default"], destination or "local", row["risk_tier"], "normal", approval_id))
            if decision.decision != DecisionKind.ALLOW:
                self._audit_conn(connection, actor, "approval.consume", approval_id, "deny", "current_policy_denied")
                connection.commit()
                raise PolicyDeniedError("Current policy does not allow execution.")
            handler = self.handlers.get(action_type)
            if handler is None:
                self._audit_conn(connection, actor, "approval.consume", approval_id, "deny", "unsupported_action")
                connection.commit()
                raise PolicyDeniedError("No executable handler is registered for this action.")
            connection.execute("UPDATE approvals SET status='consumed',consumed_at=? WHERE id=? AND status='approved'", (now, approval_id))
            self._audit_conn(connection, actor, "approval.consume", approval_id, "allow", "consumed")
        # Consumption commits before execution, so a crash cannot replay a side effect.
        with self.database.connect() as connection:
            mode = connection.execute("SELECT paused,killed FROM runtime_controls WHERE singleton=1").fetchone()
        if mode["killed"] or mode["paused"]:
            self._audit(actor, "approval.dispatch", approval_id, "deny", "runtime_stopped", approval_id)
            raise PolicyDeniedError("Runtime controls block action execution.")
        return handler(arguments)

    def _change(self, approval_id: str, actor: Actor, status: str, eligible: set[str], action: str) -> dict:
        self._check_actor(actor)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None: raise NotFoundError("Approval not found.")
            if row["status"] not in eligible: raise ConflictError("Approval cannot change from its current state.")
            connection.execute("UPDATE approvals SET status=? WHERE id=?", (status, approval_id))
            self._audit_conn(connection, actor, action, approval_id, "allow", status)
            return dict(connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())

    def _audit(self, actor: Actor, action: str, target: str, decision: str, result: str, approval_id: str | None) -> None:
        with self.database.connect() as connection:
            self._audit_conn(connection, actor, action, target, decision, result, approval_id)

    @staticmethod
    def _audit_conn(connection: sqlite3.Connection, actor: Actor, action: str, target: str,
                    decision: str, result: str, approval_id: str | None = None) -> None:
        connection.execute("INSERT INTO audit_events VALUES (?,?, 'user', ?, ?, ?, ?, ?, ?, NULL, '{}')",
                           (str(uuid.uuid4()), utc_now(), actor.principal_id, action, target, decision, approval_id, result))

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _check_actor(actor: Actor) -> None:
        if not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID:
            raise PolicyDeniedError("Local user identity is required.")

