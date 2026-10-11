"""Repeatable, explicitly synthetic workspace fixtures for LARA IV local demos."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .database import Database
from .models import Actor
from .services import ConflictError

PROJECTS = (
    ("lara", "LARA IV — Local AI Workspace", "A private local-first workspace for chat, memory, planning, and four-role review.", "active"),
    ("gopika", "GOPIKA — Agricultural AI Assistant", "An explainable crop-planning assistant with offline-friendly guidance and explicit uncertainty.", "active"),
    ("onyx", "Onyx Meridian — Enterprise AI Platform", "Tenant-scoped retrieval, governance, and local observability concepts.", "planning"),
    ("quantum", "Quantum Computing Experiments", "Small simulator exercises and reproducible circuit notes.", "active"),
    ("research", "Research and Technical Writing", "Notes on local-first retrieval, provenance, and trustworthy technical communication.", "on_hold"),
    ("study", "DSA and Semester Preparation", "A balanced study queue for algorithms, graph problems, and weekly review.", "active"),
)

CONVERSATIONS = (
    ("lara-memory", "Local chat memory and provenance", (
        ("How should LARA keep useful context without sending my whole chat history on every turn?", "Keep SQLite as the source record, retrieve a small authorized set of relevant memories, and include only a bounded recent window."),
        ("What should the UI show when local indexing is temporarily unavailable?", "Save the conversation normally, show indexing as failed or pending, and let the user retry. Do not imply that a vector was stored."),
        ("How do we make a retrieved note auditable?", "Keep its document, version, chunk, room, and source conversation references beside the answer metadata."),
    )),
    ("gopika-crop-planning", "GOPIKA crop-planning flow", (
        ("I want the sample crop planner to be helpful without pretending one weather signal is enough.", "Show the crop and season context, summarize the signals, and state what is missing before suggesting a next step."),
        ("Could rainfall and soil notes produce a confident instruction?", "They can support a cautious planning prompt, but the sample should distinguish observed inputs from assumptions and local expert advice."),
        ("What would an offline-friendly version show?", "Keep the last locally saved plan visible, label its data date, and queue a review instead of claiming a live forecast."),
    )),
    ("onyx-governance", "Onyx Meridian tenant boundaries", (
        ("Which boundary should be checked before a retrieved chunk reaches a prompt?", "Authorize the source against the current principal, room, sensitivity, deletion state, and active version."),
        ("Can a matching vector alone prove access?", "No. The vector index is a candidate generator; SQLite metadata remains authoritative for authorization."),
        ("What should a source deletion do?", "Tombstone the authoritative source, enqueue vector cleanup, and exclude it from retrieval immediately."),
    )),
    ("quantum-simulator", "Two-qubit simulator notebook", (
        ("How should I compare two short circuit decompositions?", "Start with the same input state and target operation, then compare gate count and simulator output under documented assumptions."),
        ("Should the demo include a speedup claim?", "No. Without a measured and reproducible benchmark, describe the notebook as an experiment rather than a performance result."),
        ("What makes the notebook easier to reproduce?", "Record the simulator package, version, random seed if relevant, and the exact circuit construction."),
    )),
    ("study-week", "Semester study rhythm", (
        ("I need a study plan that can survive a busy week.", "Keep one small daily practice block, reserve a longer review session, and leave a buffer for assignments with real deadlines."),
        ("How should graph practice fit beside coursework?", "Alternate a focused BFS or DFS exercise with assignment work, then capture one short reflection on complexity."),
        ("What should I do when the plan slips?", "Move unfinished work back to the board with a smaller next action; do not silently mark it complete."),
    )),
    ("research-writing", "Writing a useful local-first retrieval note", (
        ("I am outlining a short note about local-first retrieval. What order is clearest?", "Explain the source of truth first, then candidate retrieval, authorization, bounded prompt context, and deletion/reconciliation."),
        ("How do I keep the example honest?", "Label synthetic examples, keep provenance fields visible, and separate measured behavior from design intent."),
        ("What limitation belongs near the conclusion?", "Retrieval quality depends on the local embedding model, indexed content, and authorization filters; it is not a guarantee of recall."),
    )),
    ("kanban-planning", "Weekly Kanban review", (
        ("The board has too many tasks in progress. How should I triage it?", "Choose a small number of active outcomes, move blocked work to waiting, and return unstarted ideas to the inbox."),
        ("Which work should stay visible this week?", "Keep the local API origin review, the crop-planner feedback review, and one algorithms practice block near the top."),
        ("How can I tell the dashboard is trustworthy?", "Its totals should come from the same persisted tasks and status transitions shown by the board."),
    )),
    ("loop-safety", "AI Loop review boundaries", (
        ("What is the role of the reviewer after the Judge synthesizes a proposal?", "The reviewer independently checks the synthesis for unsupported claims, unresolved objections, and evidence gaps."),
        ("How should a demo-only discussion be represented?", "Store its output with an explicit synthetic marker and no model/provider execution metadata."),
        ("When should the loop remain open for revision?", "When the reviewer requests a revision or evidence is insufficient; do not present it as a completed approval."),
    )),
    ("local-ops", "Local startup and recovery", (
        ("What belongs in the local launch checklist?", "Verify the loopback API and Vite ports, database readiness, model status, and memory status before showing the URL."),
        ("Should an unavailable embedding model block task entry?", "No. Keep unrelated productivity features usable, but expose the degraded memory state and preserve conversations."),
        ("How do we avoid overwriting existing data during a demo reset?", "Use a dedicated demo database and an idempotent seed command; never delete the user's normal database."),
    )),
)

EVENTS = (
    ("Research review", "LARA IV local memory design", -12, 10),
    ("Study session", "Algorithms assignment planning", -9, 15),
    ("Project checkpoint", "GOPIKA sample crop-planning flow", -7, 11),
    ("Writing block", "Local-first retrieval note", -5, 14),
    ("Review meeting", "Onyx Meridian tenant boundaries", -3, 16),
    ("Study session", "Graph traversal practice", -1, 17),
    ("Development block", "LARA IV conversation history", 1, 9),
    ("Research review", "Embedding and provenance notes", 2, 13),
    ("Project milestone", "GOPIKA offline advisory review", 4, 10),
    ("Development block", "Local API and Vite integration", 6, 14),
    ("Study session", "Dynamic programming revision", 8, 16),
    ("Project checkpoint", "Onyx Meridian access review", 10, 11),
    ("Notebook session", "Quantum simulator reproduction", 12, 15),
    ("Weekly planning", "Next study and project focus", 14, 9),
)

KNOWLEDGE = (
    ("local-memory-boundaries", "Local Memory Boundaries", "SQLite stores authoritative content and authorization metadata; vectors are only searchable candidates.", "lara", ("memory", "security", "sqlite")),
    ("conversation-context-window", "Conversation Context Window", "Use an ordered recent message window plus a small relevant memory set rather than sending the full transcript.", "lara", ("chat", "context", "rag")),
    ("retrieval-deletion", "Deletion and Vector Reconciliation", "Tombstone the source first, exclude it from answers, then reconcile stale local vectors idempotently.", "lara", ("memory", "deletion", "operations")),
    ("local-api-origins", "Local API Origin Rules", "The local demo accepts one configured loopback frontend origin and the backend binds only to a loopback IP.", "lara", ("api", "security", "local")),
    ("gopika-season-signals", "GOPIKA Season Signals", "A crop planning example should keep the season, rainfall context, missing inputs, and uncertainty explicit.", "gopika", ("agriculture", "planning", "uncertainty")),
    ("gopika-offline-flow", "GOPIKA Offline Flow", "Offline advisory examples show the age of saved inputs and never claim a current network forecast.", "gopika", ("offline", "agriculture", "ux")),
    ("onyx-tenant-authorization", "Onyx Tenant Authorization Notes", "Reauthorize each memory candidate using principal, workspace room, sensitivity, version, and deletion state.", "onyx", ("authorization", "tenant", "memory")),
    ("onyx-observability", "Onyx Local Observability Signals", "Report database readiness, provider availability, embedding readiness, and indexing recovery independently.", "onyx", ("operations", "health", "local")),
    ("quantum-reproducibility", "Quantum Notebook Reproducibility", "Record package version, circuit definition, simulator settings, and seeds before comparing example outputs.", "quantum", ("quantum", "notebook", "reproducibility")),
    ("quantum-claim-boundary", "Simulator Claim Boundary", "An illustrative simulator notebook is not a hardware result or a speedup benchmark.", "quantum", ("quantum", "evidence", "research")),
    ("technical-writing-provenance", "Technical Writing Provenance Checklist", "Separate source-supported statements, synthetic examples, assumptions, and open limitations.", "research", ("writing", "provenance", "citations")),
    ("study-weekly-review", "Weekly Study Review Pattern", "Use short practice blocks, an honest waiting lane, and a buffer for assignment deadlines.", "study", ("study", "planning", "kanban")),
    ("ai-loop-review-contract", "AI Loop Reviewer Contract", "The reviewer independently audits Judge synthesis; revise and insufficient-evidence verdicts remain unresolved.", "lara", ("ai-loop", "review", "evidence")),
    ("demo-data-policy", "Synthetic Demo Data Policy", "Seeded conversations and AI Loop outputs are explicitly synthetic and must not claim live model execution.", "lara", ("demo", "integrity", "local")),
)


def _stable_id(name: str) -> str:
    # Share the seeder namespace so tasks, projects, loops, and graph links agree.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ubuntu-agent:lara-iv:demo:{name}:v1"))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _audit(connection, key: str, timestamp: str, action: str, target_id: str, details: dict) -> None:
    from .demo_seed import _record_demo_activity
    _record_demo_activity(connection, f"workspace:{key}", timestamp, action, target_id, details)


def ensure_projects(database: Database, now: datetime) -> tuple[dict[str, str], int]:
    ids = {key: _stable_id(f"project:{key}") for key, *_ in PROJECTS}
    created = 0
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for index, (key, name, summary, status) in enumerate(PROJECTS):
            old = connection.execute("SELECT name,description FROM projects WHERE id=?", (ids[key],)).fetchone()
            if old:
                if old["name"] != name or not old["description"].startswith("Synthetic demo project"):
                    raise ConflictError("Stable synthetic project ID conflicts with non-demo data.")
                continue
            milestones = [{"id": _stable_id(f"project:{key}:m{n}"), "title": title,
                           "dueDate": (now.date() + timedelta(days=offset)).isoformat(), "completed": done}
                          for n, title, offset, done in ((1, "Scope and acceptance notes", 0, True),
                                                         (2, "Working local workflow", 6 + index, index % 3 == 0),
                                                         (3, "Review and handoff", 14 + index, False))]
            created_at = _iso(now - timedelta(days=25 - index * 2))
            updated_at = _iso(now - timedelta(days=max(0, 9 - index)))
            connection.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)",
                               (ids[key], "local-user", "operations", name,
                                f"Synthetic demo project · {summary}", status,
                                json.dumps(milestones, ensure_ascii=False), created_at, updated_at))
            _audit(connection, f"project:{key}", updated_at, "project.created", ids[key], {"name": name})
            created += 1
    return ids, created


def seed_conversations(database: Database, now: datetime) -> int:
    created = 0
    for index, (slug, title, turns) in enumerate(CONVERSATIONS):
        conversation_id = _stable_id(f"conversation:{slug}")
        age_days = 22 - index * 2
        start = now - timedelta(days=max(0, age_days), hours=(index % 4) * 2)
        display_title = f"[Synthetic demo] {title}"
        with database.connect() as connection:
            old = connection.execute("SELECT title FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if old and not old["title"].startswith("[Synthetic demo]"):
                raise ConflictError("Stable synthetic conversation ID conflicts with non-demo data.")
            connection.execute("INSERT OR IGNORE INTO conversations(id,principal_id,room_id,title,memory_enabled,created_at,updated_at) VALUES(?,?, 'operations',?,0,?,?)",
                               (conversation_id, "local-user", display_title, _iso(start), _iso(start)))
            message_count = 0
            for turn_index, (user_text, assistant_text) in enumerate(turns):
                for sender, content in (("user", user_text), ("assistant", f"Synthetic demo response: {assistant_text}")):
                    message_id = _stable_id(f"conversation:{slug}:turn:{turn_index}:{sender}")
                    created_at = _iso(start + timedelta(minutes=turn_index * 8 + (4 if sender == "assistant" else 0)))
                    connection.execute("""INSERT OR IGNORE INTO conversation_messages
                        (id,conversation_id,sender,content,status,provider_id,model_id,retrieved_memory_json,created_at,memory_status)
                        VALUES(?,?,?,?,'complete',?,?, '[]',?,'disabled')""",
                        (message_id, conversation_id, sender, content,
                         "demo_seed" if sender == "assistant" else None,
                         "synthetic" if sender == "assistant" else None, created_at))
                    message_count += 1
            end = _iso(start + timedelta(minutes=(len(turns) - 1) * 8 + 4))
            connection.execute("UPDATE conversations SET created_at=COALESCE(created_at,?),updated_at=? WHERE id=?",
                               (_iso(start), end, conversation_id))
            _audit(connection, f"conversation:{slug}", end, "conversation.demo_seeded", conversation_id,
                   {"title": title, "messages": message_count})
        created += int(old is None)
    return created


def seed_events(database: Database, now: datetime) -> int:
    created = 0
    for index, (kind, title, day_offset, hour) in enumerate(EVENTS):
        event_id = _stable_id(f"calendar:event:{index}")
        start = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        end = start + timedelta(minutes=60 if index % 3 else 90)
        description = f"Synthetic demo event · {kind} for the local workspace. No external meeting or calendar sync occurred."
        with database.connect() as connection:
            old = connection.execute("SELECT title,description FROM calendar_events WHERE id=?", (event_id,)).fetchone()
            if old:
                if old["title"] != title or "Synthetic demo event" not in old["description"]:
                    raise ConflictError("Stable synthetic event ID conflicts with non-demo data.")
                continue
            created_at = _iso(now - timedelta(days=max(0, 18 - index)))
            connection.execute("INSERT INTO calendar_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                               (event_id, "local-user", "operations", title, description, _iso(start), _iso(end),
                                "UTC", "scheduled", created_at, created_at))
            _audit(connection, f"event:{index}", _iso(start), "calendar_event.demo_seeded", event_id,
                   {"title": title, "scheduled_at": _iso(start)})
            created += 1
    return created


def seed_loops(database: Database, now: datetime) -> dict[str, int]:
    from .loop.orchestrator import LoopOrchestrator
    from .demo_seed import DEMO_COMPLETE_LOOP_ID, DEMO_DRAFT_LOOP_ID

    actor = Actor("local-user", "desktop_operator")
    orchestrator = LoopOrchestrator(database)
    specs = (
        ("complete", DEMO_COMPLETE_LOOP_ID, "Should conversational memory be enabled by default in a local workspace?", -8),
        ("draft", DEMO_DRAFT_LOOP_ID, "How should GOPIKA communicate uncertainty in an offline crop-planning session?", -1),
    )
    created = {"ai_loops": 0, "loop_rounds": 0, "loop_roles": 0, "loop_nodes": 0, "loop_edges": 0}
    for kind, loop_id, goal_text, age in specs:
        goal = f"Synthetic demo discussion · {goal_text}"
        constraints = ["Synthetic role text only; no provider was called.", "Do not represent illustrative output as verified evidence."]
        with database.connect() as connection:
            existing = connection.execute("SELECT id,goal FROM ai_loops WHERE id=?", (loop_id,)).fetchone()
        if existing and existing["goal"] != goal:
            raise ConflictError("Stable synthetic AI Loop ID conflicts with non-demo data.")
        if not existing:
            orchestrator.create_loop(actor, goal=goal, constraints=constraints, provider_mode="ollama_api",
                                     max_rounds=4, loop_id=loop_id)
            created["ai_loops"] += 1
            created["loop_roles"] += 4
            created["loop_nodes"] += 1 + len(constraints)
        created_at = now + timedelta(days=age)
        if kind == "draft":
            if not existing:
                with database.connect() as connection:
                    connection.execute("UPDATE ai_loops SET provider_mode='demo_seed',created_at=?,updated_at=? WHERE id=?",
                                       (_iso(created_at), _iso(created_at), loop_id))
                    _audit(connection, "loop:draft", _iso(created_at), "loop.demo_seeded", loop_id,
                           {"status": "draft", "execution": "not_run"})
            continue

        proposal = {"proposal": "Enable memory for new local conversations, while making opt-out and deletion immediately available.",
                    "rationale": "A local-first assistant becomes more useful when users can retrieve relevant notes across conversations.",
                    "assumptions": ["The user controls the local workspace."], "evidence_references": []}
        critique = {"critique": "Default indexing can surprise users, and a local vector store can still expose sensitive text to another authorized room if scope checks are weak.",
                    "risks": ["Unexpected retention", "Stale vectors after deletion"], "evidence_references": []}
        synthesis = {"final_recommendation": "Enable conversational memory by default in this local demo, disclose it clearly, honor room boundaries, and provide reliable exclusion and deletion controls.",
                     "rationale": "The utility is meaningful when SQLite remains authoritative and every candidate is reauthorized before retrieval.",
                     "accepted_arguments": ["Relevant cross-conversation context reduces repeated setup."],
                     "rejected_arguments": [], "unresolved_objections": ["A local-only location does not make sensitive data harmless."],
                     "evidence_gaps": ["This synthetic discussion contains no retrieved or externally verified evidence."],
                     "confidence_limitations": ["Illustrative discussion; no live model run."], "evidence_references": [],
                     "review_verdict": "pass", "provenance": {"demo": True, "synthetic": True, "model_generated_reasoning": False}}
        reviewer = {"verdict": "pass", "reasons": ["The recommendation preserves opt-out, deletion, and authorization as conditions."],
                    "unsupported_claims": [], "unanswered_questions": ["How should retention duration be configured?"],
                    "potential_bias": ["The discussion favors local utility over a no-retention default."], "evidence_references": []}
        synthesis["reviewer"] = reviewer
        outputs = [proposal, critique, synthesis, reviewer]
        roles = ["blue_team", "red_team", "judge", "unbiased_reviewer"]
        stages = ["propose", "challenge", "synthesize", "audit"]
        inputs = [{"goal": goal, "constraints": constraints},
                  {"goal": goal, "proposal": proposal},
                  {"goal": goal, "proposal": proposal, "critique": critique},
                  {"goal": goal, "judge_synthesis": synthesis}]
        start = created_at
        with database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_fixture_rounds = connection.execute(
                "SELECT COUNT(*) FROM loop_rounds WHERE loop_id=? AND provider_id='demo_seed'", (loop_id,)
            ).fetchone()[0]
            fixture_already_populated = existing_fixture_rounds >= 4
            if not fixture_already_populated:
                connection.execute("UPDATE ai_loops SET provider_mode='demo_seed',status='synthesized',created_at=?,updated_at=? WHERE id=?",
                                   (_iso(start), _iso(start + timedelta(minutes=15)), loop_id))
                connection.execute("UPDATE loop_execution_state SET status='succeeded',pending_json='[]',invocation_count=0,review_verdict='pass',final_synthesis=?,error_class=NULL,created_at=?,updated_at=? WHERE loop_id=?",
                                   (json.dumps(synthesis, ensure_ascii=False), _iso(start), _iso(start + timedelta(minutes=15)), loop_id))
                connection.execute("UPDATE loop_roles SET status='succeeded',created_at=?,updated_at=? WHERE loop_id=?",
                                   (_iso(start), _iso(start + timedelta(minutes=15)), loop_id))
            for index, (role, stage, output, input_payload) in enumerate(zip(roles, stages, outputs, inputs), 1):
                round_id = _stable_id(f"loop:complete:round:{role}")
                round_at = _iso(start + timedelta(minutes=index * 3))
                cursor = connection.execute("""INSERT OR IGNORE INTO loop_rounds
                    (id,loop_id,round_index,stage,status,summary,output_json,job_id,created_at,updated_at,role_name,input_json,provider_id,model_id,attempt_count,error_class)
                    VALUES(?,?,?,?,'succeeded',?,?,NULL,?,?,?,?, 'demo_seed','synthetic',0,NULL)""",
                    (round_id, loop_id, index, stage, f"Synthetic {role.replace('_',' ')} contribution · not generated by a model.",
                     json.dumps(output, ensure_ascii=False), round_at, round_at, role,
                     json.dumps(input_payload, ensure_ascii=False)))
                created["loop_rounds"] += cursor.rowcount
            _audit(connection, "loop:complete", _iso(start + timedelta(minutes=15)), "loop.demo_seeded", loop_id,
                   {"roles": roles, "execution": "synthetic_not_run", "review_verdict": "pass"})
        # A fresh loop gets its four role rows from create_loop; do not count twice.

        graph = orchestrator.graph
        nodes = [
            ("proposal", "Blue Team proposal", proposal["proposal"]),
            ("counterargument", "Red Team critique", critique["critique"]),
            ("decision", "Judge synthesis", synthesis["final_recommendation"]),
            ("conclusion", "Reviewer audit", reviewer["reasons"][0]),
        ]
        node_ids = []
        for node_type, label, content in nodes:
            node_id = _stable_id(f"loop:complete:node:{node_type}")
            with database.connect() as connection:
                existed = connection.execute("SELECT 1 FROM loop_nodes WHERE id=?", (node_id,)).fetchone()
            graph.add_node(loop_id, node_type, f"Synthetic demo · {label}", content, room_id="operations",
                           sensitivity="internal", provenance={"demo": True, "synthetic": True,
                           "execution": "not_run", "role": node_type}, node_id=node_id)
            node_ids.append(node_id)
            created["loop_nodes"] += int(existed is None)
        for index, (source, relation, target) in enumerate(((0,"supports",2),(1,"contradicts",0),(2,"refines",3))):
            edge_id = _stable_id(f"loop:complete:edge:{index}")
            with database.connect() as connection:
                cursor = connection.execute("INSERT OR IGNORE INTO loop_edges VALUES(?,?,?,?,?,?,?,?)",
                    (edge_id, loop_id, node_ids[source], relation, node_ids[target], "operations", "internal", _iso(start)))
                created["loop_edges"] += cursor.rowcount
    return created


def seed_knowledge(database: Database, now: datetime, *, index_knowledge: bool) -> dict[str, int | str]:
    from .demo_seed import DEMO_COMPLETE_LOOP_ID
    root = database.path.parent / "lara-demo-knowledge"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    created = 0
    files = []
    for key, title, summary, project_key, tags in KNOWLEDGE:
        path = root / f"{key}.md"
        body = (f"# {title}\n\nSynthetic local demo knowledge item.\n\n{summary}\n\n"
                f"Tags: {', '.join(tags)}\nProject: {project_key}\n\n"
                "This note is illustrative sample content. It is not evidence from an external source or a real user's activity.\n")
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if "Synthetic local demo knowledge item." not in existing:
                raise ConflictError(f"Demo knowledge path already contains non-demo data: {path.name}.")
        else:
            path.write_text(body, encoding="utf-8")
            os.chmod(path, 0o600)
            created += 1
        files.append((key, title, summary, project_key, tags, path))
    indexed = 0
    failed = 0
    document_ids = {}
    index_status = {}
    failure_codes: dict[str, int] = {}
    if index_knowledge:
        from .memory import MemoryService
        try:
            service = MemoryService(database, data_dir=database.path.parent)
        except Exception as exc:
            service = None
            failed = len(files)
            failure_codes[getattr(exc, "code", "INDEX_UNAVAILABLE")] = len(files)
        if service is not None:
            for key, title, summary, project_key, tags, path in files:
                try:
                    outcome = service.ingest_document(path, Actor("local-user", "task_deadline_manager"), "operations")
                    document_ids[key] = outcome.get("document_id")
                    indexed += int(outcome.get("status") == "ready")
                    failed += int(outcome.get("status") != "ready")
                    index_status[key] = "indexed" if outcome.get("status") == "ready" else "failed"
                except Exception as exc:
                    failed += 1
                    index_status[key] = "failed"
                    code = getattr(exc, "code", "INDEX_FAILED")
                    failure_codes[code] = failure_codes.get(code, 0) + 1

    # Give the actual loop graph inspectable references to these source files and current index state.
    from .loop.graph import LoopGraph
    graph = LoopGraph(database)
    for key, title, summary, project_key, tags, path in files:
        document_id = document_ids.get(key)
        node_id = _stable_id(f"knowledge:node:{key}")
        with database.connect() as connection:
            existed = connection.execute("SELECT 1 FROM loop_nodes WHERE id=?", (node_id,)).fetchone()
        graph.add_node(DEMO_COMPLETE_LOOP_ID, "source_summary", f"Synthetic demo · {title}", summary,
                       room_id="operations", sensitivity="internal",
                       provenance={"demo": True, "synthetic": True, "file": path.name,
                                   "document_id": document_id, "project_key": project_key,
                                   "tags": list(tags), "index_status": index_status.get(key, "not_indexed")},
                       node_id=node_id)
        goal_node_id = _stable_id("loop:complete:node:decision")
        with database.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO loop_edges VALUES(?,?,?,?,?,?,?,?)",
                (_stable_id(f"knowledge:edge:{key}"), DEMO_COMPLETE_LOOP_ID, goal_node_id,
                 "derived_from", node_id, "operations", "internal", _iso(now)))
    return {"knowledge_items": len(files), "knowledge_files_created": created,
            "knowledge_indexed": indexed, "knowledge_index_failed": failed,
            "knowledge_index_failure_codes": failure_codes,
            "knowledge_index_status": "indexed" if index_knowledge and not failed else "degraded" if failed else "not_requested"}
