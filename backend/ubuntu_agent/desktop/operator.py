"""Desktop operator run state, workspace slots, approvals, and cancellable dispatch."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from ubuntu_agent.approvals import ApprovalService
from ubuntu_agent.bootstrap import PRINCIPAL_ID
from ubuntu_agent.database import Database
from ubuntu_agent.models import AccessContext, Actor, DecisionKind, utc_now
from ubuntu_agent.policy import ACTION_RISK, PolicyEngine
from ubuntu_agent.runtime import RuntimeControlService
from ubuntu_agent.services import (
    ApprovalRequiredError, ConflictError, NotFoundError, PolicyDeniedError, ValidationError,
)

from .actions import CONSEQUENTIAL_INTENTS, SLOT_NAMES, is_consequential, validate_action, validate_url
from .bridge import DesktopBridge, LinuxDesktopBridge
from .capabilities import detect_desktop_capabilities
from .grounding import parse_grounding_payload

DEFAULT_BOUNDS = {
    "nw": {"x": 0, "y": 0, "width": 960, "height": 540},
    "ne": {"x": 960, "y": 0, "width": 960, "height": 540},
    "sw": {"x": 0, "y": 540, "width": 960, "height": 540},
    "se": {"x": 960, "y": 540, "width": 960, "height": 540},
}


def automation_profile_dir() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "ubuntu-agent"
    path = root / "automation-browser"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


class DesktopOperatorService:
    def __init__(self, database: Database, policy: PolicyEngine | None = None, *,
                 bridge: DesktopBridge | None = None, approvals: ApprovalService | None = None,
                 runtime: RuntimeControlService | None = None, clock: Callable[[], datetime] | None = None,
                 screenshot_dir: Path | None = None, profile_dir: Path | None = None):
        self.database = database
        self.policy = policy or PolicyEngine()
        self.bridge = bridge or LinuxDesktopBridge()
        self.approvals = approvals or ApprovalService(database, self.policy)
        self.runtime = runtime or RuntimeControlService(database)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        root = screenshot_dir or (database.path.parent / "screenshots")
        self.screenshot_dir = Path(root)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.profile_dir = Path(profile_dir) if profile_dir else automation_profile_dir()

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _authorize(self, actor: Actor, action_id: str, resource_id: str, *, job_id: str | None = None,
                   approval_id: str | None = None) -> None:
        if not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID:
            raise PolicyDeniedError("Local user identity is required.")
        risk = ACTION_RISK[action_id]
        decision = self.policy.evaluate_access(AccessContext(
            actor.principal_id, actor.persona_id, job_id, "operations", resource_id, action_id,
            "internal", "local", risk.value, "normal", approval_id))
        if decision.decision == DecisionKind.REQUIRES_APPROVAL:
            raise ApprovalRequiredError("This desktop action requires explicit approval.")
        if decision.decision != DecisionKind.ALLOW:
            raise PolicyDeniedError("Current policy denies this action.")

    def _controls_block(self) -> None:
        state = self.runtime.state()
        if state["killed"]:
            raise PolicyDeniedError("Emergency stop is active.")
        if state["paused"]:
            raise PolicyDeniedError("Autonomy is paused.")

    def _append_event(self, connection, run_id: str, event_type: str, payload: dict) -> None:
        sequence = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM desktop_events WHERE run_id=?",
                                      (run_id,)).fetchone()[0]
        connection.execute("INSERT INTO desktop_events VALUES (?,?,?,?,?,?)",
                           (str(uuid.uuid4()), run_id, sequence, event_type, self._now(),
                            json.dumps(payload, separators=(",", ":"))))

    def preflight(self, actor: Actor) -> dict:
        self._authorize(actor, "desktop.preflight", "desktop-session")
        caps = self.bridge.capabilities()
        payload = caps.as_dict()
        payload["profile_dir"] = str(self.profile_dir)
        payload["supported"] = caps.session_type in {"x11", "wayland"}
        return payload

    def create_workspace(self, actor: Actor, *, purpose: str, urls: dict[str, str] | None = None) -> dict:
        self._authorize(actor, "desktop.workspace", "desktop-workspace")
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 200:
            raise ValidationError("Workspace purpose is invalid.")
        caps = self.bridge.capabilities()
        urls = urls or {}
        if not isinstance(urls, dict) or len(urls) > 4:
            raise ValidationError("Workspace URLs must map at most four slots.")
        assigned = {}
        for slot, url in urls.items():
            if slot not in SLOT_NAMES:
                raise ValidationError("Unknown workspace slot.")
            assigned[slot] = validate_url(url)
        workspace_id = str(uuid.uuid4())
        now = self._now()
        status = "unavailable"
        tile_ok = False
        if caps.tiling:
            result = self.bridge.tile(DEFAULT_BOUNDS)
            tile_ok = result.ok
        if not caps.browser:
            slot_status = "unavailable"
        elif not tile_ok and not caps.tiling:
            slot_status = "awaiting_user"
        else:
            slot_status = "active"
            status = "active"
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO desktop_workspaces VALUES (?,?,?,?,?,?,?,?)",
                               (workspace_id, purpose.strip(), "operations", status,
                                json.dumps(DEFAULT_BOUNDS), None, now, now))
            for slot in SLOT_NAMES:
                url = assigned.get(slot)
                location = None
                app_identity = None
                ready = 0
                current_status = slot_status if url or caps.browser else "unavailable"
                if url and caps.browser:
                    opened = self.bridge.open_url(url, profile_dir=self.profile_dir, slot=slot)
                    if opened.ok:
                        location = opened.location
                        app_identity = f"automation-browser:{slot}"
                        ready = 1
                    else:
                        current_status = "unavailable"
                elif not caps.browser:
                    current_status = "unavailable"
                connection.execute("INSERT INTO desktop_slots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (str(uuid.uuid4()), workspace_id, slot, purpose.strip(), app_identity,
                                    url, location, json.dumps(DEFAULT_BOUNDS[slot]), 0, ready,
                                    current_status, None))
            if not caps.browser:
                connection.execute("UPDATE desktop_workspaces SET status='unavailable',updated_at=? WHERE id=?",
                                   (now, workspace_id))
            return self._workspace_snapshot(connection, workspace_id)

    def workspace_status(self, workspace_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.preflight", workspace_id)
        with self.database.connect() as connection:
            return self._workspace_snapshot(connection, workspace_id)

    def cleanup_workspace(self, workspace_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.workspace", workspace_id)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM desktop_workspaces WHERE id=?", (workspace_id,)).fetchone()
            if row is None:
                raise NotFoundError("Workspace not found.")
            connection.execute("UPDATE desktop_workspaces SET status='cleaned',updated_at=? WHERE id=?",
                               (self._now(), workspace_id))
            connection.execute("UPDATE desktop_slots SET status='unavailable',ready=0 WHERE workspace_id=?",
                               (workspace_id,))
            return self._workspace_snapshot(connection, workspace_id)

    def restore_layout(self, workspace_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.workspace", workspace_id)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM desktop_workspaces WHERE id=?", (workspace_id,)).fetchone()
            if row is None:
                raise NotFoundError("Workspace not found.")
            previous = json.loads(row["previous_layout_json"] or row["layout_json"])
        result = self.bridge.restore_layout(previous)
        if not result.ok:
            raise ValidationError(result.detail)
        return {"workspace_id": workspace_id, "restored": True}

    def _workspace_snapshot(self, connection, workspace_id: str) -> dict:
        row = connection.execute("SELECT * FROM desktop_workspaces WHERE id=?", (workspace_id,)).fetchone()
        if row is None:
            raise NotFoundError("Workspace not found.")
        slots = [dict(item) for item in connection.execute(
            "SELECT * FROM desktop_slots WHERE workspace_id=? ORDER BY slot_name", (workspace_id,))]
        return {**dict(row), "slots": slots, "capabilities": self.bridge.capabilities().as_dict()}

    def create_run(self, actor: Actor, *, workspace_id: str | None, actions: list, domain_scope: list[str],
                   deadline_minutes: int = 30, permissions: list[str] | None = None) -> dict:
        self._authorize(actor, "desktop.run", workspace_id or "desktop-run")
        if type(deadline_minutes) is not int or not 1 <= deadline_minutes <= 240:
            raise ValidationError("Run deadline must be between 1 and 240 minutes.")
        if not isinstance(domain_scope, list) or not domain_scope or len(domain_scope) > 32:
            raise ValidationError("Domain scope is required.")
        hosts = []
        for host in domain_scope:
            if not isinstance(host, str) or not host or len(host) > 253 or "/" in host or host.startswith("."):
                raise ValidationError("Domain scope entries must be hostnames.")
            hosts.append(host.lower())
        plan = [validate_action(item) for item in actions]
        if len(plan) > 50:
            raise ValidationError("Action plan exceeds the length limit.")
        allowed = set(permissions or ALLOWED_DEFAULT_PERMISSIONS)
        unknown = allowed - set(ALLOWED_DEFAULT_PERMISSIONS)
        if unknown:
            raise ValidationError("Unknown desktop permission.")
        deadline = (self.clock().astimezone(timezone.utc) + timedelta(minutes=deadline_minutes)).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        run_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if workspace_id:
                if connection.execute("SELECT id FROM desktop_workspaces WHERE id=?", (workspace_id,)).fetchone() is None:
                    raise NotFoundError("Workspace not found.")
            connection.execute("""INSERT INTO desktop_runs VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?)""",
                               (run_id, workspace_id, None, session_id, actor.persona_id, "operations", "queued",
                                json.dumps(sorted(allowed)), json.dumps(hosts), deadline, now, now))
            self._append_event(connection, run_id, "run.created", {"action_count": len(plan), "stop": True})
            connection.execute("INSERT INTO desktop_run_plans VALUES (?,?)",
                               (run_id, json.dumps(plan, separators=(",", ":"))))
            return dict(connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone()) | {
                "plan": redact_plan(plan), "stop_available": True,
            }

    def preview_plan(self, run_id: str, actor: Actor) -> dict:
        run = self._load_run(run_id, actor)
        return {"run_id": run_id, "status": run["status"], "plan": redact_plan(self._plan(run_id)), "stop_available": True}

    def _plan(self, run_id: str) -> list:
        with self.database.connect() as connection:
            row = connection.execute("SELECT plan_json FROM desktop_run_plans WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFoundError("Run plan not found.")
        return json.loads(row["plan_json"])

    def _load_run(self, run_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.preflight", run_id)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFoundError("Run not found.")
        return dict(row)

    def events(self, run_id: str, actor: Actor, *, after: int = 0) -> list[dict]:
        self._load_run(run_id, actor)
        if type(after) is not int or after < 0:
            raise ValidationError("Event cursor is invalid.")
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM desktop_events WHERE run_id=? AND sequence>? ORDER BY sequence",
                                      (run_id, after)).fetchall()
        return [dict(row) for row in rows]

    def pause(self, run_id: str, actor: Actor) -> dict:
        return self._set_status(run_id, actor, "paused", {"queued", "running"})

    def resume(self, run_id: str, actor: Actor) -> dict:
        self._controls_block()
        return self._set_status(run_id, actor, "queued", {"paused"})

    def cancel(self, run_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.run", run_id)
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise NotFoundError("Run not found.")
            if row["status"] in {"cancelled", "succeeded", "failed"}:
                return dict(row)
            connection.execute("UPDATE desktop_runs SET status='cancelled',cancel_requested=1,updated_at=? WHERE id=?",
                               (now, run_id))
            self._append_event(connection, run_id, "run.cancelled", {"stop": True})
            return dict(connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone())

    def _set_status(self, run_id: str, actor: Actor, status: str, eligible: set[str]) -> dict:
        self._authorize(actor, "desktop.run", run_id)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise NotFoundError("Run not found.")
            if row["status"] not in eligible:
                raise ConflictError("Run cannot change from its current state.")
            connection.execute("UPDATE desktop_runs SET status=?,updated_at=? WHERE id=?", (status, self._now(), run_id))
            self._append_event(connection, run_id, f"run.{status}", {"stop": True})
            return dict(connection.execute("SELECT * FROM desktop_runs WHERE id=?", (run_id,)).fetchone())

    def dispatch(self, run_id: str, actor: Actor, *, approval_id: str | None = None) -> dict:
        self._controls_block()
        run = self._load_run(run_id, actor)
        if run["cancel_requested"] or run["status"] in {"cancelled", "failed", "succeeded"}:
            raise ConflictError("Run is no longer dispatchable.")
        if run["deadline_at"] <= self._now():
            self._fail(run_id, "deadline_exceeded")
            raise ConflictError("Run deadline has passed.")
        plan = self._plan(run_id)
        hosts = json.loads(run["domain_scope_json"])
        permissions = set(json.loads(run["permissions_json"]))
        with self.database.connect() as connection:
            connection.execute("UPDATE desktop_runs SET status='running',updated_at=? WHERE id=?", (self._now(), run_id))
        for action in plan:
            self._controls_block()
            with self.database.connect() as connection:
                current = connection.execute("SELECT cancel_requested,status FROM desktop_runs WHERE id=?", (run_id,)).fetchone()
            if current["cancel_requested"] or current["status"] == "cancelled":
                return self._load_run(run_id, actor)
            try:
                self._dispatch_one(run, action, actor, hosts, permissions, approval_id)
            except ApprovalRequiredError:
                with self.database.connect() as connection:
                    connection.execute("UPDATE desktop_runs SET status='awaiting_approval',updated_at=? WHERE id=?",
                                       (self._now(), run_id))
                    self._append_event(connection, run_id, "run.awaiting_approval", {"type": action["type"], "stop": True})
                raise
            except Exception as exc:
                self._fail(run_id, getattr(exc, "code", "handler_failed"))
                raise
        with self.database.connect() as connection:
            connection.execute("UPDATE desktop_runs SET status='succeeded',updated_at=? WHERE id=?", (self._now(), run_id))
            self._append_event(connection, run_id, "run.succeeded", {"stop": True})
        return self._load_run(run_id, actor)

    def _fail(self, run_id: str, code: str) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE desktop_runs SET status='failed',updated_at=? WHERE id=?", (self._now(), run_id))
            self._append_event(connection, run_id, "run.failed", {"code": code, "stop": True})

    def _dispatch_one(self, run: dict, action: dict, actor: Actor, hosts: list[str],
                      permissions: set[str], approval_id: str | None) -> None:
        action_id = "desktop.consequential" if is_consequential(action) else "desktop.action"
        if action["type"] not in permissions and action["type"] != "request_user_confirmation":
            raise PolicyDeniedError("Action is outside the registered capability set.")
        if action.get("type") == "open_url":
            host = (urlparse(action["url"]).hostname or "").lower()
            if host not in hosts and not any(host.endswith("." + item) for item in hosts):
                raise PolicyDeniedError("URL host is outside the run domain scope.")
        if action_id == "desktop.consequential":
            self._authorize(actor, action_id, run["id"], job_id=run["id"], approval_id=approval_id)
        else:
            self._authorize(actor, action_id, run["id"], job_id=run["id"])
        result = self._invoke(run, action)
        with self.database.connect() as connection:
            self._append_event(connection, run["id"], "action.completed" if result.ok else "action.failed",
                               {"type": action["type"], "ok": result.ok, "detail": result.detail, "stop": True})
        if not result.ok:
            raise ValidationError(result.detail)

    def _invoke(self, run: dict, action: dict):
        kind = action["type"]
        slot = action.get("slot")
        if kind == "focus_window":
            return self.bridge.focus_slot(slot, None)
        if kind == "open_url":
            return self.bridge.open_url(action["url"], profile_dir=self.profile_dir, slot=slot or "nw")
        if kind == "move_pointer":
            return self.bridge.move_pointer(int(action["x"]), int(action["y"]))
        if kind == "click_target":
            if action.get("confidence", 1) < 0.72:
                raise ValidationError("Target confidence is too low to click; ask the user to identify it.")
            return self.bridge.click(int(action["x"]), int(action["y"]))
        if kind == "type_text":
            focused = self.bridge.focus_slot(slot or "nw", None)
            if not focused.ok:
                return focused
            return self.bridge.type_text(action["text"])
        if kind == "paste_text":
            focused = self.bridge.focus_slot(slot or "nw", None)
            if not focused.ok:
                return focused
            return self.bridge.paste_text(action["text"])
        if kind == "scroll_window":
            return self.bridge.scroll(action["delta"])
        if kind == "capture_screenshot":
            return self.capture_screenshot_record(run["id"], slot=slot, region=action.get("region", "window"))
        if kind == "wait_for_state":
            waited = self.bridge.wait_for_state(action["expected"], action["timeout_seconds"])
            if waited.ok:
                self.capture_screenshot_record(run["id"], slot=slot, region="window")
            return waited
        if kind == "tile_windows":
            return self.bridge.tile(DEFAULT_BOUNDS)
        if kind == "request_user_confirmation":
            from .bridge import BridgeResult
            return BridgeResult(True, "awaiting_user")
        raise ValidationError("Desktop action is not in the allowlist.")

    def capture_screenshot_record(self, run_id: str, *, slot: str | None, region: str):
        path = self.screenshot_dir / f"{run_id}-{uuid.uuid4().hex}.png"
        result = self.bridge.screenshot(path, region=region)
        if result.ok and result.screenshot_path:
            expires = (self.clock().astimezone(timezone.utc) + timedelta(minutes=15)).isoformat(
                timespec="seconds").replace("+00:00", "Z")
            with self.database.connect() as connection:
                connection.execute("INSERT INTO desktop_screenshots VALUES (?,?,?,?,?,?,?,?,?)",
                                   (str(uuid.uuid4()), run_id, slot, result.screenshot_path,
                                    result.width or 1, result.height or 1, 1.0, self._now(), expires))
                self._retain_screenshots(connection)
        return result

    def _retain_screenshots(self, connection) -> None:
        rows = connection.execute("SELECT id,path FROM desktop_screenshots ORDER BY captured_at DESC").fetchall()
        for extra in rows[20:]:
            connection.execute("DELETE FROM desktop_screenshots WHERE id=?", (extra["id"],))
            try:
                os.remove(extra["path"])
            except OSError:
                pass

    def get_screenshot(self, screenshot_id: str, actor: Actor) -> dict:
        self._authorize(actor, "desktop.preflight", screenshot_id)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM desktop_screenshots WHERE id=?", (screenshot_id,)).fetchone()
        if row is None or row["expires_at"] <= self._now():
            raise NotFoundError("Screenshot not found.")
        return dict(row)

    def ground_and_click(self, run_id: str, actor: Actor, payload: object, *, width: int, height: int,
                         scale: float = 1.0, age_seconds: float = 0.0, window_id: str | None = None) -> dict:
        self._controls_block()
        run = self._load_run(run_id, actor)
        target = parse_grounding_payload(payload, screenshot_width=width, screenshot_height=height,
                                         scale=scale, observation_age_seconds=age_seconds,
                                         window_id=window_id, expected_window_id=window_id)
        action = validate_action({"type": "click_target", "x": target.screen_x, "y": target.screen_y,
                                  "label": target.label, "confidence": target.confidence})
        result = self.bridge.click(target.screen_x, target.screen_y)
        with self.database.connect() as connection:
            self._append_event(connection, run["id"], "grounding.selected",
                               {"label": target.label, "confidence": target.confidence,
                                "x": target.screen_x, "y": target.screen_y, "ok": result.ok, "stop": True})
        if not result.ok:
            raise ValidationError(result.detail)
        return {"label": target.label, "x": target.screen_x, "y": target.screen_y, "confidence": target.confidence}


ALLOWED_DEFAULT_PERMISSIONS = (
    "focus_window", "open_url", "move_pointer", "click_target", "type_text", "paste_text",
    "scroll_window", "capture_screenshot", "wait_for_state", "tile_windows", "request_user_confirmation",
)


def redact_plan(plan: list[dict]) -> list[dict]:
    redacted = []
    for item in plan:
        copy = dict(item)
        if "text" in copy:
            copy["text"] = f"<{copy.get('text_length', 0)} chars>"
        redacted.append(copy)
    return redacted
