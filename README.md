# Ubuntu Agent — local core

The local core provides versioned SQLite persistence, deterministic room/persona policy checks, and task/reminder services. Optional inference and RAG adapters do not become task-core dependencies.

## Initialize and run

From the repository root, Python 3.11+ is sufficient:

```sh
python -m ubuntu_agent init
python -m ubuntu_agent task-create "Algorithms assignment" --category Academics --due-date 2027-11-07
python -m ubuntu_agent tasks
python -m ubuntu_agent reminder-create TASK_ID 2027-11-04T09:00:00Z "Start the assignment"
python -m ubuntu_agent reminders
```

For a reminder that should move with a timed deadline, create the task with `--due-at` and create the reminder with `--reminder-type relative_to_due_at --offset-minutes 60` (the supplied `scheduled_at` must equal the deadline minus that offset). Deadline changes reschedule those rule-based reminders in the same transaction. A fixed-time reminder has no safe deadline rule, so a deadline change is rejected until that reminder is handled.

The default database is `${XDG_DATA_HOME:-~/.local/share}/ubuntu-agent/ubuntu-agent.sqlite3`. Use `--db PATH` before the command to select another path. A persona may be selected with `--persona`; available IDs are `task_deadline_manager`, `exam_study_coach`, `ai_ml_researcher`, and `desktop_operator`. Operations that require a persona or room grant are checked in the service layer. Task completion requires evidence.

The CLI can persist, inspect, approve, reject, revoke through the service layer, and consume approvals only for explicitly registered handlers. The current policy has no executable Classroom submit, external message, arbitrary shell, file deletion, browser, or privileged system handler; approvals cannot enable these actions. A local single-user process is the identity boundary, not strong multi-user authentication. Do not expose the service to untrusted callers.

## Durable reminders and worker

The SQLite queue stores reminder deliveries with a stable idempotency key, payload validation, leases and bounded retries. Reconcile after startup, then run the worker in the foreground:

```sh
python -m ubuntu_agent reminders-reconcile
python -m ubuntu_agent worker --once
python -m ubuntu_agent worker --interval-seconds 5
python -m ubuntu_agent reminders
python -m ubuntu_agent reminder-snooze REMINDER_ID 2027-11-05T09:00:00Z
python -m ubuntu_agent reminder-dismiss REMINDER_ID
```

The continuous command runs only while its terminal process is alive; `Ctrl-C` requests orderly shutdown. No service or startup configuration is installed. Local delivery uses `/usr/bin/notify-send`; a missing desktop session or executable retries up to five times and leaves the reminder `missed`. A crash between showing a notification and saving success can result in a duplicate.

`autonomy-pause` holds autonomy jobs but allows safe local reminder notifications. `autonomy-kill` blocks all worker dispatch until `autonomy-recover`. Approval decisions are tied to this local application identity, and do not authorize unsupported actions.

## Provider integration and task previews

Inference is optional. Ollama is selected by default and uses `http://127.0.0.1:11434` with model `gemma4:e2b-it-q4_K_M`. Set `OLLAMA_MODEL` and `OLLAMA_TIMEOUT_SECONDS` to override those values. Requests time out after 30 seconds by default; no cloud fallback occurs.

Gemini uses the optional `google-genai` dependency. Install it with `python -m pip install -e '.[gemini]'`, then set `GEMINI_API_KEY` in the environment or place it in the project `.env` (never commit that file). Its default model is `gemma-4-26b-a4b-it`; set `GEMINI_MODEL` or `GEMINI_TIMEOUT_SECONDS` to override it. `provider-status` reports only provider/model configuration state, never credential values.

```sh
python -m ubuntu_agent provider-status
python -m ubuntu_agent provider-test                 # generic local Ollama health check
python -m ubuntu_agent provider-test --provider gemini  # deliberate hosted generic health check
python -m ubuntu_agent task-preview "Algorithms assignment due 2027-11-07" --provider ollama
```

Task preview is non-persisting and always requires separate confirmation through `TaskCaptureService.confirm_and_create`, which delegates to the protected `TaskService`. It sends only the supplied text and a fixed extraction instruction, not task history or database contents. Hosted task extraction is currently denied even with `--cloud-opt-in`: the provider sensitivity thresholds are unresolved in the autonomy specification, so the policy cannot authorize disclosure from the Operations room. The generic health check uses a fixed non-sensitive prompt and is the only hosted request presently permitted.

The provider adapter interface and local core support Python 3.11+. The optional `google-genai==2.25.0` manifest pin is compatible with Python 3.14 according to the SDK's published package metadata ([official SDK metadata](https://github.com/googleapis/python-genai/blob/main/pyproject.toml)).

## Local memory (Phase 3)

Install the optional Qdrant client and pull the local embedding model explicitly; application startup and tests never download models:

```sh
python -m pip install -e '.[rag]'
ollama pull embeddinggemma
python -m ubuntu_agent memory-init
python -m ubuntu_agent memory-ingest ./notes.md --room operations
python -m ubuntu_agent memory-search "exam dates" --purpose "prepare my study plan"
python -m ubuntu_agent memory-reindex --confirm
```

The first ingestion command requires an explicit Markdown or UTF-8 plain-text file and a trusted room assignment. It reads at most 1 MB and uses the room's stored sensitivity default. The default persona can write the Operations room; choose a persona with a corresponding trusted grant for other rooms. Search policy derives its room scope from the persona, and citations are reauthorized when resolved through `MemoryService.get_authorized_source`.

Embedding settings: `UBUNTU_AGENT_OLLAMA_URL` (default `http://127.0.0.1:11434`), `UBUNTU_AGENT_EMBEDDING_MODEL` (default `embeddinggemma`), and `UBUNTU_AGENT_EMBEDDING_TIMEOUT` (default 30 seconds). `UBUNTU_AGENT_EMBEDDING_DIMENSIONS` defaults to 768 for local Qdrant initialization. A model/dimension mismatch fails closed. `memory-reindex --confirm` explicitly replaces the local Qdrant collection and rebuilds vectors; documents remain unavailable if the rebuild fails.

SQLite stays authoritative at `${XDG_DATA_HOME:-~/.local/share}/ubuntu-agent/ubuntu-agent.sqlite3`; embedded Qdrant is stored beside it in `qdrant/`, with user-only permissions and a single-process lock. SQLite migrations track versions, activation state, tombstones, and pending index cleanup. `MemoryService.reconcile_memory_index(limit=20)` retries pending work idempotently; deleted records remain unavailable even if vector deletion fails. Back up the database and Qdrant together, or rebuild vectors from source documents after restore. Do not copy live Qdrant files while open.

This slice supports Markdown and plain text only. Graph traversal, cross-room bridges, cloud memory prompt assembly, web/PDF/OCR ingestion, and a CLI reconciliation command are not implemented. Local Qdrant unavailability returns a controlled error; there is no cloud fallback.

## Tests

```sh
python -m unittest discover -s tests -v
git diff --check
```

The SQLite schema is advanced through `schema_migrations`. Runtime state belongs outside the repository; `.gitignore` excludes local databases and generated data.
