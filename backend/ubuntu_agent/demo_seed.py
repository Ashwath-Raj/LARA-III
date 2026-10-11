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
DEMO_DRAFT_LOOP_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "ubuntu-agent:lara-iv:demo:loop:draft:v1"))
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


DEMO_COMPLETE_LOOP_ID = _stable_id("loop:complete")

PROJECT_FIXTURES = (
    ("lara", "LARA IV — Local AI Workspace", "Synthetic demo project · A private local-first workspace for chat, memory, planning, and four-role review.", "active"),
    ("gopika", "GOPIKA — Agricultural AI Assistant", "Synthetic demo project · An explainable crop-planning assistant with offline-friendly guidance and explicit uncertainty.", "active"),
    ("onyx", "Onyx Meridian — Enterprise AI Platform", "Synthetic demo project · Tenant-scoped retrieval, governance, and local observability concepts.", "planning"),
    ("quantum", "Quantum Computing Experiments", "Synthetic demo project · Small simulator exercises and reproducible circuit notes.", "active"),
    ("research", "Research and Technical Writing", "Synthetic demo project · Notes on local-first retrieval, provenance, and trustworthy technical communication.", "on_hold"),
    ("study", "DSA and Semester Preparation", "Synthetic demo project · A balanced study queue for algorithms, graph problems, and weekly review.", "active"),
)


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

    fixtures = [
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
    # Additional work streams make all existing Kanban lanes and project links useful.
    extra = [
        ("lara-proxy-audit", "Review local API proxy origin checks", "Verify safe GET origin stamping and mutation origin enforcement.", "task", "high", "Projects", 2, "in_progress", "lara"),
        ("lara-chat-history", "Polish conversation history selection", "Check ordering, previews, and rename/delete behavior against persistent records.", "task", "normal", "Projects", 5, "next", "lara"),
        ("lara-memory-retry", "Exercise recoverable memory indexing states", "Use a disposable local index and record honest pending and failed states.", "research_job", "normal", "AI/ML Research", 7, "review", "lara"),
        ("lara-launch-docs", "Write the local workspace launch notes", "Document the isolated demo database and one-command localhost workflow.", "task", "low", "Projects", 1, "done", "lara"),
        ("gopika-weather", "Compare rainfall signals for the crop planner", "Synthetic project task; use public example data only and label assumptions.", "research_job", "normal", "AI/ML Research", 6, "in_progress", "gopika"),
        ("gopika-crop-card", "Draft a crop-season recommendation card", "Keep advice explainable and identify the conditions that change the recommendation.", "task", "high", "Robotics", 4, "next", "gopika"),
        ("gopika-feedback", "Review farmer feedback capture fields", "Check that the sample form distinguishes observed conditions from suggested actions.", "task", "normal", "Projects", -2, "waiting", "gopika"),
        ("gopika-offline", "Test the offline advisory flow", "Map the expected local fallback when the network is unavailable.", "task", "normal", "Robotics", 9, "in_progress", "gopika"),
        ("gopika-data-note", "Summarize the sample soil-data limits", "Synthetic note: describe coverage gaps before presenting any recommendation.", "research_job", "low", "AI/ML Research", -4, "done", "gopika"),
        ("onyx-policy", "Review tenant-scoped retrieval policy", "Trace workspace and room authorization through every retrieved source.", "task", "urgent", "AI/ML Research", -1, "in_progress", "onyx"),
        ("onyx-import", "Draft the document import review checklist", "Validate file type, provenance, sensitivity, and deletion behavior.", "task", "high", "Projects", 3, "review", "onyx"),
        ("onyx-metrics", "Choose useful local observability signals", "Separate provider availability, indexing readiness, and user-visible failures.", "task", "normal", "AI/ML Research", 10, "next", "onyx"),
        ("onyx-retention", "Map source deletion through vector cleanup", "Ensure SQLite remains authoritative while stale vectors are reconciled.", "task", "normal", "Projects", 12, "inbox", "onyx"),
        ("quantum-notebook", "Reproduce the two-qubit notebook setup", "Capture the package versions and assumptions for a small simulator exercise.", "assignment", "normal", "Quantum Computing", 8, "in_progress", "quantum"),
        ("quantum-circuit", "Compare two circuit decompositions", "Keep the comparison qualitative until a reproducible benchmark exists.", "research_job", "low", "Quantum Computing", 15, "next", "quantum"),
        ("quantum-readme", "Clarify the simulator README", "Explain the difference between an illustrative circuit and measured output.", "task", "low", "Quantum Computing", -5, "done", "quantum"),
        ("writing-outline", "Outline the local-first memory note", "Structure the note around source of truth, retrieval, and removal semantics.", "task", "normal", "AI/ML Research", 5, "in_progress", "research"),
        ("writing-citations", "Review citation and provenance examples", "Use only cited sample sources; mark all synthetic examples as synthetic.", "task", "high", "Academics", 7, "next", "research"),
        ("writing-review", "Incorporate reviewer comments into the draft", "Resolve unclear terminology and preserve a short limitations section.", "task", "normal", "Academics", 2, "waiting", "research"),
        ("dsa-graphs", "Practice graph traversal problems", "Complete a small set of BFS and DFS exercises and note complexity.", "assignment", "normal", "Academics", 3, "inbox", "study"),
        ("dsa-revision", "Review dynamic programming recurrence patterns", "Use one easy and one medium example to compare state definitions.", "assignment", "high", "Academics", 6, "next", "study"),
    ]
    for key, title, description, item_type, priority, category, days, status, project in extra:
        fixtures.append({"key": key, "title": title, "description": f"Synthetic demo · {description}",
                         "item_type": item_type, "priority": priority, "category": category,
                         "due_date": due(days) if days != 99 else None, "due_at": None, "status": status,
                         "project_key": project})
    project_for_existing = {
        "algorithms-assignment":"study", "research-reading":"research", "hackathon-prototype":"lara",
        "robotics-plan":"gopika", "study-review":"study", "planning-block":"lara",
        "draft-review":"lara", "ready-example":"research", "archived-example":"quantum",
    }
    for fixture in fixtures:
        fixture.setdefault("project_key", project_for_existing.get(str(fixture["key"]), "lara"))
        if not str(fixture["title"]).startswith(DEMO_MARKER):
            fixture["description"] = f"Synthetic demo · {fixture['description']}"
    return fixtures


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


def _ensure_demo_projects(database: Database, now: datetime) -> tuple[dict[str, str], int]:
    project_ids = {key: _stable_id(f"project:{key}") for key, *_ in PROJECT_FIXTURES}
    created = 0
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for index, (key, name, description, status) in enumerate(PROJECT_FIXTURES):
            project_id = project_ids[key]
            existing = connection.execute("SELECT name,description FROM projects WHERE id=?", (project_id,)).fetchone()
            if existing:
                if existing["name"] != name or not existing["description"].startswith("Synthetic demo project"):
                    raise ConflictError("A stable demo project ID is already used by non-demo data.")
                continue
            milestones = [
                {"id": _stable_id(f"project:{key}:milestone:{n}"), "title": title,
                 "dueDate": (now.date() + timedelta(days=offset)).isoformat(), "completed": done}
                for n, title, offset, done in (
                    (1, "Scope and acceptance notes", 0, True),
                    (2, "Working local workflow", 5 + index, index % 3 == 0),
                    (3, "Review and handoff", 13 + index, False),
                )
            ]
            created_at = _iso(now - timedelta(days=24 - index * 2))
            updated_at = _iso(now - timedelta(days=max(0, 8 - index)))
            connection.execute(
                "INSERT INTO projects(id,principal_id,room_id,name,description,status,milestones_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (project_id, "local-user", "operations", name, description, status,
                 json.dumps(milestones, ensure_ascii=False), created_at, updated_at),
            )
            _record_demo_activity(connection, f"project:{key}", updated_at, "project.created", project_id,
                                  {"name": name, "synthetic": True})
            created += 1
    return project_ids, created


def _record_demo_activity(connection, key: str, timestamp: str, action: str, target_id: str,
                          details: dict[str, object]) -> None:
    connection.execute(
        """INSERT OR IGNORE INTO audit_events
           (id,timestamp,actor_type,actor_id,action,target_ref,policy_decision,approval_id,result_status,evidence_ref,safe_metadata_json)
           VALUES(?,?,'demo_seed','local-user',?,?,'allow',NULL,'seeded',NULL,?)""",
        (_stable_id(f"activity:{key}"), timestamp, action, target_id,
         json.dumps({"demo": True, "synthetic": True, **details}, ensure_ascii=False)),
    )


def _create_demo_tasks(database: Database, now: datetime, actor: Actor,
                       project_ids: dict[str, str]) -> tuple[dict[str, dict], int]:
    service = TaskService(database)
    tasks: dict[str, dict] = {}
    created = 0
    for fixture_index, fixture in enumerate(_task_fixtures(now.date())):
        slug = str(fixture["key"])
        key = f"lara-iv-demo:v1:{slug}"
        existing = _existing_task(database, actor, key)
        if existing is not None:
            desired_project = project_ids[str(fixture.get("project_key", "lara"))]
            if existing.get("project_id") is None:
                with database.connect() as connection:
                    connection.execute("UPDATE tasks SET project_id=? WHERE id=? AND project_id IS NULL",
                                       (desired_project, existing["id"]))
                existing["project_id"] = desired_project
            tasks[slug] = existing
            continue
        candidate = {
            "title": fixture["title"],
            "description": fixture["description"],
            "item_type": fixture["item_type"],
            "priority": fixture["priority"],
            "category": fixture["category"],
            "room_id": "operations",
            "project_id": project_ids[str(fixture.get("project_key", "lara"))],
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
        history_time = now - timedelta(days=(fixture_index * 19) // 29, hours=(fixture_index % 5) * 2)
        with database.connect() as connection:
            connection.execute("UPDATE tasks SET created_at=?,updated_at=? WHERE id=?",
                               (_iso(history_time), _iso(min(now, history_time + timedelta(hours=2))), task["id"]))
            _record_demo_activity(connection, f"task:{slug}", _iso(history_time), "task.demo_seeded", task["id"],
                                  {"title": task["title"], "status": desired_status})
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
        ("gopika-weather-review", "gopika-weather", now + timedelta(days=3, hours=2), "custom", None,
         "Compare the sample rainfall notes before the crop-planning review."),
        ("onyx-policy-review", "onyx-policy", now + timedelta(days=1, hours=5), "custom", None,
         "Recheck room-scoped access assumptions for the synthetic platform plan."),
        ("quantum-notebook-check", "quantum-notebook", now + timedelta(days=7, hours=1), "custom", None,
         "Capture simulator setup details before the notebook review."),
        ("writing-outline-review", "writing-outline", now + timedelta(days=4, hours=3), "custom", None,
         "Review the local-first memory note outline."),
        ("dsa-practice-block", "dsa-graphs", now + timedelta(days=2), "custom", None,
         "Start the graph traversal practice block."),
        ("lara-demo-review", "lara-chat-history", now + timedelta(days=10), "custom", None,
         "Walk through conversation selection and persistence in the demo."),
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
              clock: Callable[[], datetime] | None = None,
              index_knowledge: bool = False) -> dict:
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

    from .demo_workspace import (ensure_projects, seed_conversations, seed_events,
                                 seed_knowledge, seed_loops)
    project_ids, projects_created = ensure_projects(database, now)
    tasks, tasks_created = _create_demo_tasks(database, now, actor, project_ids)
    reminders_created = _create_demo_reminders(database, now, actor, tasks)
    loop_created = _ensure_demo_loop(database, now, Actor("local-user", "desktop_operator"))
    workspace_loop_created = seed_loops(database, now)
    conversations_created = seed_conversations(database, now)
    events_created = seed_events(database, now)
    knowledge = seed_knowledge(database, now, index_knowledge=index_knowledge)
    workspace_created = _ensure_demo_workspace(database, now)
    counts = inspect_demo(database, now=now)
    return {
        "status": "seeded",
        "environment": environment,
        "database": str(database.path),
        "created": {
            "tasks": tasks_created,
            "reminders": reminders_created,
            "projects": projects_created,
            "conversations": conversations_created,
            "calendar_events": events_created,
            "ai_loops": loop_created["ai_loops"] + workspace_loop_created["ai_loops"],
            "loop_rounds": loop_created["loop_rounds"] + workspace_loop_created["loop_rounds"],
            "loop_roles": workspace_loop_created["loop_roles"],
            "loop_nodes": loop_created["loop_nodes"] + workspace_loop_created["loop_nodes"],
            "loop_edges": workspace_loop_created["loop_edges"],
            "loop_sources": loop_created["loop_sources"],
            "loop_artifacts": loop_created["loop_artifacts"],
            **workspace_created,
            "knowledge_files": int(knowledge["knowledge_files_created"]),
        },
        "knowledge": knowledge,
        "counts": counts,
        "external_actions": 0,
        "model_generation_calls": 0,
        "local_embedding_documents_indexed": knowledge["knowledge_indexed"],
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
        from .demo_workspace import _stable_id
        loop_ids_expected = (DEMO_LOOP_ID, _stable_id("loop:complete"), _stable_id("loop:draft"))
        placeholders = ",".join("?" for _ in loop_ids_expected)
        loops = connection.execute(f"SELECT id FROM ai_loops WHERE id IN ({placeholders})", loop_ids_expected).fetchall()
        loop_ids = [row["id"] for row in loops]
        loop_count = len(loop_ids)
        loop_roles = connection.execute(f"SELECT COUNT(*) FROM loop_roles WHERE loop_id IN ({placeholders})", loop_ids_expected).fetchone()[0]
        loop_rounds = connection.execute(f"SELECT COUNT(*) FROM loop_rounds WHERE loop_id IN ({placeholders})", loop_ids_expected).fetchone()[0]
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
        loop_nodes = connection.execute(f"SELECT COUNT(*) FROM loop_nodes WHERE loop_id IN ({placeholders})", loop_ids_expected).fetchone()[0]
        loop_edges = connection.execute(f"SELECT COUNT(*) FROM loop_edges WHERE loop_id IN ({placeholders})", loop_ids_expected).fetchone()[0]
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
        from .demo_workspace import KNOWLEDGE, PROJECTS, _stable_id
        knowledge_dir = database.path.parent / "lara-demo-knowledge"
        knowledge_items = sum((knowledge_dir / f"{item[0]}.md").is_file() for item in KNOWLEDGE)
        indexed_items = connection.execute(
            "SELECT COUNT(*) FROM documents WHERE source_uri LIKE ? AND deleted_at IS NULL AND ingestion_status='ready'",
            (str(knowledge_dir.resolve()) + "/%",),
        ).fetchone()[0]
        failed_items = connection.execute(
            "SELECT COUNT(*) FROM documents WHERE source_uri LIKE ? AND deleted_at IS NULL AND ingestion_status='failed'",
            (str(knowledge_dir.resolve()) + "/%",),
        ).fetchone()[0]
        result = {
            "tasks": len(task_ids),
            "tasks_by_status": status_counts,
            "overdue_active_tasks": overdue,
            "due_within_7_days": upcoming,
            "reminders": sum(reminder_counts.values()),
            "reminders_by_status": reminder_counts,
            "ai_loops": loop_count,
            "loop_roles": loop_roles,
            "loop_rounds": loop_rounds,
            "loop_nodes": loop_nodes,
            "loop_edges": loop_edges,
            "loop_sources": loop_sources,
            "loop_artifacts": loop_artifacts,
            "desktop_workspaces": workspace_count,
            "desktop_slots": slots,
            "desktop_runs": runs,
            "desktop_events": events,
            "desktop_screenshots": screenshots,
            "projects": connection.execute("SELECT COUNT(*) FROM projects WHERE id IN (" + ",".join("?" for _ in PROJECTS) + ")", tuple(_stable_id(f"project:{key}") for key, *_ in PROJECTS)).fetchone()[0],
            "conversations": connection.execute("SELECT COUNT(*) FROM conversations WHERE title LIKE '[Synthetic demo] %'").fetchone()[0],
            "conversation_messages": connection.execute("SELECT COUNT(*) FROM conversation_messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.title LIKE '[Synthetic demo] %'").fetchone()[0],
            "calendar_events": connection.execute("SELECT COUNT(*) FROM calendar_events WHERE description LIKE 'Synthetic demo event%'").fetchone()[0],
            "knowledge_items": knowledge_items,
            "knowledge_indexed": indexed_items,
            "knowledge_index_failed": failed_items,
        }
        return result
