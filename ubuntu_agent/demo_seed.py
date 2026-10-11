"""Idempotent, clearly marked demo records for the local SQLite core."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from .database import Database
from .loop.orchestrator import LoopOrchestrator
from .models import Actor
from .services import AgentError, ConflictError, ReminderService, TaskService

DEMO_MARKER = "[DEMO LARA IV v1]"
DEMO_WORKSPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ubuntu-agent:lara-iv:demo-workspace:v1"))
DEMO_LOOP_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ubuntu-agent:lara-iv:demo-loop:v1"))
DEMO_LOOP_GOAL = (
    f"{DEMO_MARKER} Review a hypothetical study plan. "
    "Synthetic preview only; no model inference or external activity occurred."
)
DEVELOPMENT_ENVIRONMENTS = {"development", "dev", "test"}
SUPPORTED_ENVIRONMENTS = DEVELOPMENT_ENVIRONMENTS | {"staging", "production"}


class DemoSeedError(AgentError):
    code = "DEMO_SEED_ERROR"


def _stable_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ubuntu-agent:lara-iv:demo:{name}:v1"))


def _validate_environment(environment: str, *, allow_non_development: bool,
                          allow_production: bool) -> None:
    if not isinstance(environment, str) or environment not in SUPPORTED_ENVIRONMENTS:
        raise DemoSeedError("Environment must be development, dev, test, staging, or production.")
    if environment not in DEVELOPMENT_ENVIRONMENTS and not allow_non_development:
        raise DemoSeedError("Non-development seeding requires --allow-non-development.")
    if environment == "production" and not allow_production:
        raise DemoSeedError("Production seeding also requires --allow-production.")

    requested_environment = (
        "development" if environment in DEVELOPMENT_ENVIRONMENTS else environment
    )
    for name in ("UBUNTU_AGENT_ENV", "APP_ENV", "ENVIRONMENT"):
        runtime_environment = os.environ.get(name, "").strip().lower()
        if not runtime_environment:
            continue
        if runtime_environment not in SUPPORTED_ENVIRONMENTS:
            raise DemoSeedError(f"{name} contains an unsupported environment value.")
        normalized_runtime_environment = (
            "development" if runtime_environment in DEVELOPMENT_ENVIRONMENTS else runtime_environment
        )
        if normalized_runtime_environment != requested_environment:
            raise DemoSeedError(f"{name} does not match the requested seeding environment.")
        if runtime_environment == "production" and not allow_production:
            raise DemoSeedError("Production seeding also requires --allow-production.")
        if runtime_environment not in DEVELOPMENT_ENVIRONMENTS and not allow_non_development:
            raise DemoSeedError(f"{name} identifies a non-development environment; explicit opt-in is required.")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _task_fixtures(today: date) -> list[dict[str, object]]:
    def due(days: int) -> str:
        return (today + timedelta(days=days)).isoformat()

    return [
        {
            "key": "algorithms-assignment",
            "title": f"{DEMO_MARKER} Algorithms assignment 3",
            "description": "Synthetic coursework example for the demo workspace.",
            "item_type": "assignment",
            "priority": "high",
            "category": "Academics",
            "due_date": due(4),
            "due_at": f"{due(4)}T11:59:00Z",
            "status": "next",
        },
        {
            "key": "research-reading",
            "title": f"{DEMO_MARKER} Compare local-first retrieval approaches",
            "description": "Synthetic research task; references are illustrative, not retrieved evidence.",
            "item_type": "research_job",
            "priority": "normal",
            "category": "AI/ML Research",
            "due_date": due(8),
            "due_at": None,
            "status": "in_progress",
        },
        {
            "key": "hackathon-prototype",
            "title": f"{DEMO_MARKER} Review hackathon prototype checklist",
            "description": "Synthetic overdue example; no submission or repository action occurred.",
            "item_type": "task",
            "priority": "urgent",
            "category": "Hackathons & Competitions",
            "due_date": due(-1),
            "due_at": None,
            "status": "waiting",
        },
        {
            "key": "robotics-plan",
            "title": f"{DEMO_MARKER} Draft a robotics sensor test plan",
            "description": "Synthetic planned task for demonstrating status and deadline filters.",
            "item_type": "task",
            "priority": "normal",
            "category": "Robotics",
            "due_date": due(3),
            "due_at": None,
            "status": "next",
        },
        {
            "key": "study-review",
            "title": f"{DEMO_MARKER} Review weekly study notes",
            "description": "Synthetic completed example; this is not evidence of a real user's work.",
            "item_type": "task",
            "priority": "low",
            "category": "Academics",
            "due_date": due(-3),
            "due_at": None,
            "status": "done",
        },
        {
            "key": "planning-block",
            "title": f"{DEMO_MARKER} Plan next week's focus blocks",
            "description": "Synthetic inbox item awaiting triage.",
            "item_type": "event",
            "priority": "normal",
            "category": "Personal / Admin",
            "due_date": due(6),
            "due_at": f"{due(6)}T15:00:00Z",
            "status": "inbox",
        },
        {
            "key": "draft-review",
            "title": f"{DEMO_MARKER} Review a synthetic retrieval summary",
            "description": "Synthetic draft awaiting review; no source claims have been verified.",
            "item_type": "research_job",
            "priority": "normal",
            "category": "AI/ML Research",
            "due_date": due(2),
            "due_at": None,
            "status": "review",
        },
        {
            "key": "ready-example",
            "title": f"{DEMO_MARKER} Prepare a lab report checklist",
            "description": "Synthetic ready-to-submit example; no file was attached or submitted.",
            "item_type": "assignment",
            "priority": "high",
            "category": "Academics",
            "due_date": due(5),
            "due_at": None,
            "status": "ready_to_submit",
        },
        {
            "key": "archived-example",
            "title": f"{DEMO_MARKER} Archived planning example",
            "description": "Synthetic archived record retained to demonstrate the terminal board lane.",
            "item_type": "idea",
            "priority": "low",
            "category": "Personal / Admin",
            "due_date": None,
            "due_at": None,
            "status": "archived",
        },
    ]


def _existing_task(database: Database, actor: Actor, key: str) -> dict | None:
    with database.connect() as connection:
        row = connection.execute(
            """SELECT t.*, c.name AS category, k.request_fingerprint
               FROM task_idempotency_keys k
               JOIN tasks t ON t.id=k.task_id
               JOIN categories c ON c.id=t.category_id
               WHERE k.principal_id=? AND k.persona_id=? AND k.idempotency_key=?""",
            (actor.principal_id, actor.persona_id, key),
        ).fetchone()
    if row is None:
        return None
    if not row["source_text"].startswith(DEMO_MARKER):
        raise ConflictError("A demo task idempotency key is already used by non-demo data.")
    return dict(row)


def _create_demo_tasks(database: Database, now: datetime, actor: Actor) -> tuple[dict[str, dict], int]:
    service = TaskService(database)
    tasks: dict[str, dict] = {}
    created = 0
    for fixture in _task_fixtures(now.date()):
        slug = str(fixture["key"])
        key = f"lara-iv-demo:v1:{slug}"
        existing = _existing_task(database, actor, key)
        if existing is not None:
            tasks[slug] = existing
            continue
        candidate = {
            "title": fixture["title"],
            "description": fixture["description"],
            "item_type": fixture["item_type"],
            "priority": fixture["priority"],
            "category": fixture["category"],
            "room_id": "operations",
            "due_date": fixture["due_date"],
            "due_at": fixture["due_at"],
            "timezone": "UTC",
            "source_text": f"{DEMO_MARKER} Synthetic sample record; not user supplied.",
        }
        task = service.create_task(candidate, actor, key)
        created += 1
        desired_status = str(fixture["status"])
        transitions = {
            "next": ["next"],
            "in_progress": ["in_progress"],
            "waiting": ["next", "waiting"],
            "done": ["in_progress", "done"],
            "inbox": [],
            "review": ["in_progress", "review"],
            "ready_to_submit": ["in_progress", "ready_to_submit"],
            "archived": ["archived"],
        }
        for target in transitions[desired_status]:
            evidence = f"{DEMO_MARKER} Synthetic completion example only." if target == "done" else None
            task = service.transition_task(task["id"], target, actor, evidence=evidence)
        tasks[slug] = task
    return tasks, created


def _create_demo_reminders(database: Database, now: datetime, actor: Actor,
                           tasks: dict[str, dict]) -> int:
    reminders = ReminderService(database)
    reminders_to_create = [
        (
            "algorithms-early",
            "algorithms-assignment",
            datetime.fromisoformat(tasks["algorithms-assignment"]["due_at"].replace("Z", "+00:00"))
            - timedelta(days=1),
            "relative_to_due_at",
            1440,
            "One day before the synthetic algorithms deadline.",
        ),
        (
            "robotics-check-in",
            "robotics-plan",
            now + timedelta(days=2, hours=4),
            "custom",
            None,
            "Check progress on the synthetic robotics plan.",
        ),
        (
            "planning-reminder",
            "planning-block",
            now + timedelta(days=5, hours=2),
            "custom",
            None,
            "Review the synthetic planning block.",
        ),
    ]
    created = 0
    for slug, task_slug, scheduled, reminder_type, offset, text in reminders_to_create:
        task_id = tasks[task_slug]["id"]
        message = f"{DEMO_MARKER} {slug}: {text}"
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT id,message,rule_snapshot FROM reminders WHERE task_id=?",
                (task_id,),
            ).fetchall()
        existing = None
        for row in rows:
            if row["message"] == message:
                existing = row
                break
            try:
                provenance = json.loads(row["rule_snapshot"])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(provenance, dict) and provenance.get("demo_seed_key") == slug:
                existing = row
                break
        if existing is not None:
            continue
        kwargs = {"reminder_type": reminder_type}
        if offset is not None:
            kwargs["offset_minutes"] = offset
        reminder = reminders.create_reminder(task_id, _iso(scheduled), message, actor, **kwargs)
        with database.connect() as connection:
            snapshot = json.loads(reminder["rule_snapshot"])
            snapshot.update({"demo": True, "demo_seed_key": slug})
            connection.execute(
                "UPDATE reminders SET rule_snapshot=? WHERE id=?",
                (json.dumps(snapshot, sort_keys=True, separators=(",", ":")), reminder["id"]),
            )
        created += 1
    return created


def _ensure_demo_loop(database: Database, now: datetime, actor: Actor) -> dict[str, int]:
    created = {"ai_loops": 0, "loop_rounds": 0, "loop_sources": 0, "loop_artifacts": 0, "loop_nodes": 0}
    with database.connect() as connection:
        row = connection.execute("SELECT id,goal,status FROM ai_loops WHERE id=?", (DEMO_LOOP_ID,)).fetchone()
    orchestrator = LoopOrchestrator(database)
    if row is None:
        orchestrator.create_loop(
            actor,
            goal=DEMO_LOOP_GOAL,
            constraints=["Synthetic sample only; do not infer that work was executed."],
            provider_mode="ollama_api",
            max_rounds=4,
            loop_id=DEMO_LOOP_ID,
        )
        created["ai_loops"] = 1
    elif row["goal"] != DEMO_LOOP_GOAL:
        raise ConflictError("The stable demo loop ID is already used by non-demo data.")

    source_id = _stable_id("loop-source:synthetic-evidence")
    round_id = _stable_id("loop-round:preview")
    artifact_id = _stable_id("loop-artifact:preview")
    node_id = _stable_id("loop-node:synthetic-evidence")
    now_text = _iso(now)
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        source_exists = connection.execute("SELECT id FROM loop_sources WHERE id=?", (source_id,)).fetchone()
        if source_exists is None:
            connection.execute(
                """INSERT INTO loop_sources
                   (id,loop_id,display_name,trust_label,content,ingested,created_at)
                   VALUES (?,?,?,?,?,0,?)""",
                (source_id, DEMO_LOOP_ID, f"{DEMO_MARKER} synthetic evidence (not retrieved)",
                 "demo_synthetic", "Illustrative evidence placeholder; no source was fetched or verified.", now_text),
            )
            created["loop_sources"] = 1
        round_exists = connection.execute("SELECT id FROM loop_rounds WHERE id=?", (round_id,)).fetchone()
        if round_exists is None:
            connection.execute(
                """INSERT INTO loop_rounds
                   (id,loop_id,round_index,stage,status,summary,output_json,job_id,created_at,updated_at)
                   VALUES (?,?,1,'demo_preview','cancelled',?,?,NULL,?,?)""",
                (round_id, DEMO_LOOP_ID, f"{DEMO_MARKER} Preview was not run; no model was called.",
                 json.dumps({"demo": True, "execution": "not_run", "synthetic": True},
                            separators=(",", ":")), now_text, now_text),
            )
            created["loop_rounds"] = 1
        artifact_exists = connection.execute("SELECT id FROM loop_artifacts WHERE id=?", (artifact_id,)).fetchone()
        if artifact_exists is None:
            connection.execute(
                "INSERT INTO loop_artifacts (id,loop_id,artifact_type,content,created_at) VALUES (?,?,?,?,?)",
                (artifact_id, DEMO_LOOP_ID, "demo_preview",
                 f"{DEMO_MARKER} Synthetic preview only. No synthesis or provider request occurred.", now_text),
            )
            created["loop_artifacts"] = 1
        if row is None or row["status"] == "created":
            connection.execute(
                "UPDATE ai_loops SET status='cancelled',cancelled_at=?,updated_at=? WHERE id=?",
                (now_text, now_text, DEMO_LOOP_ID),
            )
            connection.execute(
                """UPDATE loop_execution_state SET status='cancelled',pending_json='[]',
                   error_class='demo_seed_not_executed',updated_at=? WHERE loop_id=?""",
                (now_text, DEMO_LOOP_ID),
            )
            connection.execute(
                "UPDATE loop_roles SET status='cancelled',updated_at=? WHERE loop_id=? AND status='pending'",
                (now_text, DEMO_LOOP_ID),
            )

    with database.connect() as connection:
        node_exists = connection.execute("SELECT id FROM loop_nodes WHERE id=?", (node_id,)).fetchone()
    if node_exists is None:
        orchestrator.graph.add_node(
            DEMO_LOOP_ID,
            "evidence",
            f"{DEMO_MARKER} synthetic evidence",
            "Illustrative placeholder only; this is not retrieved, verified, or ingested evidence.",
            room_id="operations",
            sensitivity="internal",
            provenance={"demo": True, "source_id": source_id, "trust": "demo_synthetic"},
            node_id=node_id,
        )
        created["loop_nodes"] = 1
    return created


def _ensure_demo_workspace(database: Database, now: datetime) -> dict[str, int]:
    created = {"desktop_workspaces": 0, "desktop_slots": 0}
    timestamp = _iso(now)
    bounds = {
        "nw": {"x": 0, "y": 0, "width": 960, "height": 540},
        "ne": {"x": 960, "y": 0, "width": 960, "height": 540},
        "sw": {"x": 0, "y": 540, "width": 960, "height": 540},
        "se": {"x": 960, "y": 540, "width": 960, "height": 540},
    }
    purpose = f"{DEMO_MARKER} simulated workspace metadata; no desktop was accessed."
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT purpose FROM desktop_workspaces WHERE id=?",
                                 (DEMO_WORKSPACE_ID,)).fetchone()
        if row is None:
            connection.execute(
                """INSERT INTO desktop_workspaces
                   (id,purpose,room_id,status,layout_json,previous_layout_json,created_at,updated_at)
                   VALUES (?,?,?,'unavailable',?,NULL,?,?)""",
                (DEMO_WORKSPACE_ID, purpose, "operations",
                 json.dumps({"simulated": True, "bounds": bounds}, separators=(",", ":")),
                 timestamp, timestamp),
            )
            created["desktop_workspaces"] = 1
        elif not row["purpose"].startswith(DEMO_MARKER):
            raise ConflictError("The stable demo workspace ID is already used by non-demo data.")
        for slot, slot_bounds in bounds.items():
            slot_id = _stable_id(f"workspace-slot:{slot}")
            existing = connection.execute(
                "SELECT id FROM desktop_slots WHERE id=? OR (workspace_id=? AND slot_name=?)",
                (slot_id, DEMO_WORKSPACE_ID, slot),
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                """INSERT INTO desktop_slots
                   (id,workspace_id,slot_name,purpose,app_identity,requested_url,current_location,bounds_json,
                    focused,ready,status,last_screenshot_id)
                   VALUES (?,?,?,?,NULL,NULL,NULL,?,0,0,'unavailable',NULL)""",
                (slot_id, DEMO_WORKSPACE_ID, slot,
                 f"{DEMO_MARKER} placeholder only; no browser was launched.",
                 json.dumps(slot_bounds, separators=(",", ":"))),
            )
            created["desktop_slots"] += 1
    return created


def seed_demo(database: Database, *, environment: str = "development",
              allow_non_development: bool = False, allow_production: bool = False,
              clock: Callable[[], datetime] | None = None) -> dict:
    """Initialize and seed supported entities; never clears or replaces user records."""
    _validate_environment(environment, allow_non_development=allow_non_development,
                          allow_production=allow_production)
    if not isinstance(database, Database) or str(database.path) == ":memory:":
        raise DemoSeedError("Demo seeding requires an explicit file-backed database path.")
    database.initialize()
    now = (clock or _now)().astimezone(timezone.utc).replace(microsecond=0)
    actor = Actor("local-user", "task_deadline_manager")

    for fixture in _task_fixtures(now.date()):
        _existing_task(database, actor, f"lara-iv-demo:v1:{fixture['key']}")
    with database.connect() as connection:
        loop = connection.execute("SELECT goal FROM ai_loops WHERE id=?", (DEMO_LOOP_ID,)).fetchone()
        workspace = connection.execute(
            "SELECT purpose FROM desktop_workspaces WHERE id=?", (DEMO_WORKSPACE_ID,)
        ).fetchone()
    if loop is not None and loop["goal"] != DEMO_LOOP_GOAL:
        raise ConflictError("The stable demo loop ID is already used by non-demo data.")
    if workspace is not None and not workspace["purpose"].startswith(DEMO_MARKER):
        raise ConflictError("The stable demo workspace ID is already used by non-demo data.")

    tasks, tasks_created = _create_demo_tasks(database, now, actor)
    reminders_created = _create_demo_reminders(database, now, actor, tasks)
    loop_created = _ensure_demo_loop(database, now, Actor("local-user", "desktop_operator"))
    workspace_created = _ensure_demo_workspace(database, now)
    counts = inspect_demo(database, now=now)
    return {
        "status": "seeded",
        "environment": environment,
        "database": str(database.path),
        "created": {
            "tasks": tasks_created,
            "reminders": reminders_created,
            **loop_created,
            **workspace_created,
        },
        "counts": counts,
        "external_actions": 0,
        "provider_calls": 0,
        "desktop_actions": 0,
    }


def inspect_demo(database: Database, *, now: datetime | None = None) -> dict:
    """Return aggregate counts for demo-tagged records without returning content."""
    if not isinstance(database, Database) or not database.path.is_file():
        raise DemoSeedError("The explicit database file does not exist.")
    today = (now or _now()).astimezone(timezone.utc).date()
    marker_pattern = f"{DEMO_MARKER}%"
    with database.connect() as connection:
        migrations = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if migrations is None:
            raise DemoSeedError("The selected database is not initialized.")
        task_rows = connection.execute(
            "SELECT id,status,due_date FROM tasks WHERE source_text LIKE ?",
            (marker_pattern,),
        ).fetchall()
        task_ids = [row["id"] for row in task_rows]
        status_counts = {row["status"]: row["count"] for row in connection.execute(
            "SELECT status,COUNT(*) AS count FROM tasks WHERE source_text LIKE ? GROUP BY status",
            (marker_pattern,),
        )}
        overdue = sum(1 for row in task_rows
                      if row["due_date"] is not None and row["due_date"] < today.isoformat()
                      and row["status"] not in {"done", "archived"})
        upcoming = sum(1 for row in task_rows
                       if row["due_date"] is not None and today.isoformat() <= row["due_date"]
                       <= (today + timedelta(days=7)).isoformat()
                       and row["status"] not in {"done", "archived"})
        reminder_counts = {row["status"]: row["count"] for row in connection.execute(
            """SELECT r.status,COUNT(*) AS count FROM reminders r
               JOIN tasks t ON t.id=r.task_id WHERE t.source_text LIKE ? GROUP BY r.status""",
            (marker_pattern,),
        )}
        loops = connection.execute("SELECT id FROM ai_loops WHERE id=?", (DEMO_LOOP_ID,)).fetchall()
        loop_ids = [row["id"] for row in loops]
        loop_count = len(loop_ids)
        loop_roles = connection.execute(
            "SELECT COUNT(*) FROM loop_roles WHERE loop_id=?", (DEMO_LOOP_ID,)
        ).fetchone()[0]
        loop_rounds = connection.execute(
            "SELECT COUNT(*) FROM loop_rounds WHERE loop_id=?", (DEMO_LOOP_ID,)
        ).fetchone()[0]
        loop_sources = connection.execute(
            "SELECT COUNT(*) FROM loop_sources WHERE loop_id=? AND trust_label='demo_synthetic'",
            (DEMO_LOOP_ID,),
        ).fetchone()[0]
        loop_artifacts = connection.execute(
            "SELECT COUNT(*) FROM loop_artifacts WHERE loop_id=? AND artifact_type='demo_preview'",
            (DEMO_LOOP_ID,),
        ).fetchone()[0]
        workspace = connection.execute(
            "SELECT 1 FROM desktop_workspaces WHERE id=?", (DEMO_WORKSPACE_ID,)
        ).fetchone()
        workspace_count = int(workspace is not None)
        slots = connection.execute(
            "SELECT COUNT(*) FROM desktop_slots WHERE workspace_id=?", (DEMO_WORKSPACE_ID,)
        ).fetchone()[0]
        runs = connection.execute(
            "SELECT COUNT(*) FROM desktop_runs WHERE workspace_id=?", (DEMO_WORKSPACE_ID,)
        ).fetchone()[0]
        events = connection.execute(
            """SELECT COUNT(*) FROM desktop_events e JOIN desktop_runs r ON r.id=e.run_id
               WHERE r.workspace_id=?""", (DEMO_WORKSPACE_ID,),
        ).fetchone()[0]
        screenshots = connection.execute(
            """SELECT COUNT(*) FROM desktop_screenshots s JOIN desktop_runs r ON r.id=s.run_id
               WHERE r.workspace_id=?""", (DEMO_WORKSPACE_ID,),
        ).fetchone()[0]
        return {
            "tasks": len(task_ids),
            "tasks_by_status": status_counts,
            "overdue_active_tasks": overdue,
            "due_within_7_days": upcoming,
            "reminders": sum(reminder_counts.values()),
            "reminders_by_status": reminder_counts,
            "ai_loops": loop_count,
            "loop_roles": loop_roles,
            "loop_rounds": loop_rounds,
            "loop_sources": loop_sources,
            "loop_artifacts": loop_artifacts,
            "desktop_workspaces": workspace_count,
            "desktop_slots": slots,
            "desktop_runs": runs,
            "desktop_events": events,
            "desktop_screenshots": screenshots,
        }
