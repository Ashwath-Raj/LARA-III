"""Small terminal interface over the same protected application services."""

import argparse
import json
import os
import sys
from pathlib import Path

from .bootstrap import PERSONAS, PRINCIPAL_ID
from .database import Database
from .models import Actor
from .provider_config import ProviderConfig
from .providers import ProviderError, ProviderRouter
from .services import AgentError, ReminderService, TaskService
from .task_capture import TaskCaptureService
from .memory import MemoryService, MemoryError, QdrantLocalStore
from .jobs import JobQueue, JobNotFoundError, Worker
from .approvals import ApprovalService
from .notifications import UbuntuNotificationAdapter
from .reminder_delivery import ReminderDeliveryHandler
from .runtime import RuntimeControlService


def default_database_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "ubuntu-agent" / "ubuntu-agent.sqlite3"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="ubuntu-agent", description="Local task and reminder core")
    result.add_argument("--db", type=Path, default=default_database_path(), help="SQLite path (default: XDG data directory)")
    result.add_argument("--persona", choices=tuple(PERSONAS), default="task_deadline_manager")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Initialize local SQLite database")
    create = commands.add_parser("task-create", help="Create a typed task from JSON fields")
    create.add_argument("title")
    create.add_argument("--description", default="")
    create.add_argument("--category", default="Personal / Admin")
    create.add_argument("--room", default="operations")
    create.add_argument("--due-date")
    create.add_argument("--due-at", help="ISO 8601 deadline instant with timezone")
    create.add_argument("--priority", default="normal")
    create.add_argument("--item-type", default="task")
    create.add_argument("--idempotency-key")
    listing = commands.add_parser("tasks", help="List accessible tasks")
    listing.add_argument("--status")
    update = commands.add_parser("task-update", help="Update task fields")
    update.add_argument("task_id")
    update.add_argument("--title")
    update.add_argument("--description")
    update.add_argument("--category")
    update.add_argument("--due-date")
    update.add_argument("--due-at", help="ISO 8601 deadline instant with timezone")
    update.add_argument("--priority")
    complete = commands.add_parser("task-complete", help="Complete a task with evidence")
    complete.add_argument("task_id")
    complete.add_argument("evidence")
    remind = commands.add_parser("reminder-create", help="Schedule a local reminder")
    remind.add_argument("task_id")
    remind.add_argument("scheduled_at", help="ISO 8601 timestamp with timezone")
    remind.add_argument("message")
    remind.add_argument("--reminder-type", choices=("custom", "relative_to_due_at"), default="custom")
    remind.add_argument("--offset-minutes", type=int)
    reminders = commands.add_parser("reminders", help="List accessible reminders")
    reminders.add_argument("--task-id")
    snooze = commands.add_parser("reminder-snooze", help="Snooze one reminder until a UTC instant")
    snooze.add_argument("reminder_id")
    snooze.add_argument("until")
    dismiss = commands.add_parser("reminder-dismiss", help="Dismiss one reminder")
    dismiss.add_argument("reminder_id")
    cancel_reminder = commands.add_parser("reminder-cancel", help="Cancel one reminder")
    cancel_reminder.add_argument("reminder_id")
    commands.add_parser("reminders-reconcile", help="Enqueue due reminder deliveries")
    worker = commands.add_parser("worker", help="Run bounded persistent background jobs")
    mode = worker.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one eligible batch and exit")
    mode.add_argument("--interval-seconds", type=float, help="Run continuously with this polling interval")
    commands.add_parser("jobs", help="List durable job state")
    job_cancel = commands.add_parser("job-cancel", help="Cancel a queued or leased job")
    job_cancel.add_argument("job_id")
    approvals = commands.add_parser("approvals", help="List pending approvals")
    approvals.add_argument("--all", action="store_true")
    approval_request = commands.add_parser("approval-request", help="Request approval for a policy-gated registered action")
    approval_request.add_argument("action_type")
    approval_request.add_argument("resource_id")
    approval_request.add_argument("--room", required=True)
    approval_request.add_argument("--destination", default="local")
    approval_request.add_argument("--arguments-json", required=True)
    commands.add_parser("approval-approve", help="Approve a pending exact action")
    commands.add_parser("approval-reject", help="Reject a pending exact action")
    # IDs are positional for decision commands; attach them after parser creation.
    commands.choices["approval-approve"].add_argument("approval_id")
    commands.choices["approval-reject"].add_argument("approval_id")
    commands.add_parser("approval-revoke", help="Revoke a pending or approved action")
    commands.choices["approval-revoke"].add_argument("approval_id")
    commands.add_parser("autonomy-pause", help="Pause autonomy job dispatch")
    commands.add_parser("autonomy-resume", help="Resume autonomy after a recoverable pause")
    commands.add_parser("autonomy-kill", help="Persist emergency stop")
    commands.add_parser("autonomy-recover", help="Clear emergency stop as the local user")
    commands.add_parser("autonomy-status", help="Show persisted pause and emergency-stop state")
    status = commands.add_parser("provider-status", help="Show provider configuration without credentials")
    status.set_defaults(command="provider-status")
    test = commands.add_parser("provider-test", help="Run a generic health check; defaults to local Ollama")
    test.add_argument("--provider", choices=("ollama", "gemini"), default=None,
                      help="Provider to test (default: local Ollama; Gemini is an explicit hosted call)")
    preview = commands.add_parser("task-preview", help="Extract and display a task candidate without saving it")
    preview.add_argument("text")
    preview.add_argument("--provider", choices=("ollama", "gemini"), default=None,
                         help="Provider (default: local Ollama; no automatic fallback)")
    preview.add_argument("--cloud-opt-in", action="store_true",
                         help="Explicitly opt in to hosted inference (policy may still deny disclosure)")
    memory_init = commands.add_parser("memory-init", help="Initialize the local semantic memory index")
    memory_init.add_argument("--dimensions", type=int, default=int(os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768")))
    memory_ingest = commands.add_parser("memory-ingest", help="Index one explicitly selected Markdown/text file")
    memory_ingest.add_argument("path", type=Path)
    memory_ingest.add_argument("--room", required=True, choices=("operations", "academic", "projects", "public_research", "opportunities"))
    memory_search = commands.add_parser("memory-search", help="Search authorized local memory")
    memory_search.add_argument("query")
    memory_search.add_argument("--purpose", required=True)
    memory_search.add_argument("--limit", type=int, default=5)
    memory_reindex = commands.add_parser("memory-reindex", help="Rebuild all local vectors with the configured embedding model")
    memory_reindex.add_argument("--confirm", action="store_true", help="Confirm replacing the local vector index")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provider_command = args.command in {"provider-status", "provider-test", "task-preview"}
    config = None
    if provider_command:
        try:
            config = ProviderConfig.from_environment()
        except ValueError as exc:
            print(json.dumps({"error": {"code": "PROVIDER_CONFIGURATION_ERROR", "message": str(exc)}}), file=sys.stderr)
            return 2
    if args.command == "provider-status":
        print(json.dumps({"default_provider": config.default_provider,
                          "providers": config.provider_status()}, indent=2))
        return 0
    db = Database(args.db)
    db.initialize()
    if args.command == "init":
        print(json.dumps({"status": "ready", "database": str(args.db)}))
        return 0
    actor = Actor(PRINCIPAL_ID, args.persona)
    tasks, reminders = TaskService(db), ReminderService(db)
    provider_router = ProviderRouter(config=config) if config is not None else None
    try:
        if args.command == "memory-init":
            QdrantLocalStore(args.db.parent / "qdrant", args.dimensions)
            result = {"status": "ready", "vector_store": str(args.db.parent / "qdrant"),
                      "embedding_model": os.getenv("UBUNTU_AGENT_EMBEDDING_MODEL", "embeddinggemma"),
                      "dimensions": args.dimensions}
        elif args.command == "memory-ingest":
            result = MemoryService(db).ingest_document(args.path, actor, args.room)
        elif args.command == "memory-search":
            result = MemoryService(db).search_memory(args.query, args.purpose, actor, limit=args.limit)
        elif args.command == "memory-reindex":
            result = MemoryService(db).reindex_memory_index(confirmed=args.confirm)
        elif args.command == "task-create":
            result = tasks.create_task({"title": args.title, "description": args.description, "category": args.category,
                                        "room_id": args.room, "due_date": args.due_date, "priority": args.priority,
                                        "due_at": args.due_at, "item_type": args.item_type}, actor, args.idempotency_key)
        elif args.command == "tasks":
            result = tasks.list_tasks(actor, status=args.status)
        elif args.command == "task-update":
            patch = {key: value for key, value in {"title": args.title, "description": args.description,
                     "category": args.category, "due_date": args.due_date, "priority": args.priority}.items() if value is not None}
            if args.due_at is not None:
                patch["due_at"] = args.due_at
            result = tasks.update_task(args.task_id, patch, actor)
        elif args.command == "task-complete":
            result = tasks.transition_task(args.task_id, "done", actor, evidence=args.evidence)
        elif args.command == "reminder-create":
            result = reminders.create_reminder(args.task_id, args.scheduled_at, args.message, actor,
                                               reminder_type=args.reminder_type, offset_minutes=args.offset_minutes)
        elif args.command == "reminders":
            result = reminders.list_upcoming_reminders(actor) if args.task_id is None else reminders.list_reminders(actor, task_id=args.task_id)
        elif args.command == "reminder-snooze":
            result = reminders.snooze_reminder(args.reminder_id, args.until, actor)
        elif args.command == "reminder-dismiss":
            result = reminders.dismiss_reminder(args.reminder_id, actor)
        elif args.command == "reminder-cancel":
            result = reminders.cancel_reminder(args.reminder_id, actor)
        elif args.command == "reminders-reconcile":
            result = reminders.reconcile_reminders()
        elif args.command == "worker":
            queue = JobQueue(db)
            dispatcher = Worker(queue, {"reminder.deliver": ReminderDeliveryHandler(db, UbuntuNotificationAdapter())})
            if args.once:
                result = {"claimed": dispatcher.run_once()}
            else:
                if not 0.1 <= args.interval_seconds <= 3600:
                    raise ValidationError("Polling interval must be between 0.1 and 3600 seconds.")
                try:
                    dispatcher.run_forever(args.interval_seconds)
                except KeyboardInterrupt:
                    dispatcher.request_shutdown()
                result = {"status": "stopped"}
        elif args.command == "jobs":
            result = JobQueue(db).list_jobs()
        elif args.command == "job-cancel":
            result = JobQueue(db).cancel(args.job_id)
        elif args.command == "approvals":
            result = ApprovalService(db).list_approvals(actor, include_terminal=args.all)
        elif args.command == "approval-request":
            try:
                arguments = json.loads(args.arguments_json)
            except json.JSONDecodeError as exc:
                raise AgentError("arguments-json must be valid JSON.") from exc
            result = ApprovalService(db).request_approval(action_type=args.action_type, resource_id=args.resource_id,
                room_id=args.room, destination=args.destination, arguments=arguments, actor=actor)
        elif args.command in {"approval-approve", "approval-reject"}:
            result = ApprovalService(db).decide(args.approval_id, "approve" if args.command.endswith("approve") else "reject", actor)
        elif args.command == "approval-revoke":
            result = ApprovalService(db).revoke(args.approval_id, actor)
        elif args.command == "autonomy-pause":
            result = RuntimeControlService(db).pause(actor)
        elif args.command == "autonomy-resume":
            result = RuntimeControlService(db).resume(actor)
        elif args.command == "autonomy-kill":
            result = RuntimeControlService(db).kill(actor)
        elif args.command == "autonomy-recover":
            result = RuntimeControlService(db).recover(actor)
        elif args.command == "autonomy-status":
            result = RuntimeControlService(db).state()
        elif args.command == "provider-test":
            assert provider_router is not None
            generated = provider_router.health_check(args.provider, actor)
            result = {"provider": generated.provider_id, "model": generated.model_id, "response": generated.text}
        elif args.command == "task-preview":
            assert provider_router is not None
            preview = TaskCaptureService(db, provider_router, tasks.policy, tasks).capture_task(
                args.text, actor, provider=args.provider, cloud_opt_in=args.cloud_opt_in)
            result = {"provider": preview.provider_id, "model": preview.model_id,
                      "candidate": preview.candidate.as_dict(), "missing_fields": list(preview.missing_fields),
                      "clarification_questions": list(preview.clarification_questions),
                      "requires_confirmation": preview.requires_confirmation, "persisted": False}
        else:
            result = reminders.list_reminders(actor, task_id=args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except AgentError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        return 2
    except ProviderError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        return 2
    except MemoryError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        return 2
    except JobNotFoundError as exc:
        print(json.dumps({"error": {"code": "NOT_FOUND", "message": str(exc)}}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
