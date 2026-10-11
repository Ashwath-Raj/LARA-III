# Ubuntu Agent — local core

The local core provides versioned SQLite persistence, deterministic room/persona policy checks, and task/reminder services. The HTTP adapter is local-only; optional inference and RAG adapters remain replaceable.

## Initialize and run

Install the package on Python 3.11+ from the repository root:

```sh
python -m pip install -e .
python -m ubuntu_agent init
python -m ubuntu_agent task-create "Algorithms assignment" --category Academics --due-date 2027-11-07
python -m ubuntu_agent tasks
python -m ubuntu_agent reminder-create TASK_ID 2027-11-04T09:00:00Z "Start the assignment"
python -m ubuntu_agent reminders
```

## Disposable LARA IV demo data

Demo seeding requires an explicit SQLite path. It initializes the normal schema, then adds deterministic, visibly tagged sample tasks, reminders, a cancelled synthetic AI-loop preview, and unavailable desktop-workspace metadata. It does not clear existing records, run inference, access the browser/desktop, dispatch notifications, or insert vectors into Qdrant.

```sh
mkdir -p /tmp/lara-iv-demo
python -m ubuntu_agent --db /tmp/lara-iv-demo/ubuntu-agent.sqlite3 seed-demo --environment development
python -m ubuntu_agent --db /tmp/lara-iv-demo/ubuntu-agent.sqlite3 demo-status
```

`demo-status` reports aggregate counts without printing record contents. Re-running `seed-demo` is idempotent and leaves already-seeded records, including later user edits to them, unchanged. To start over, choose a new disposable path (preferably from `mktemp -d`) rather than deleting or reusing a user's normal database. Staging requires `--allow-non-development`; production requires both `--allow-non-development` and `--allow-production`. A production environment reported through `APP_ENV`, `UBUNTU_AGENT_ENV`, or `ENVIRONMENT` cannot be seeded as development.

The application schema includes persistent tasks, reminders, projects, calendar events, conversations, AI Loops, and the existing document-memory index. The demo seeder adds only its explicitly tagged sample records; it does not seed synthetic conversational memories because memory writes use the local ingestion pipeline.

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

## Four-role local AI Loop

The AI Loop executes Blue Team proposal, Red Team challenge, Judge synthesis, and Unbiased Reviewer audit as separate calls to the same local Ollama model. `--max-rounds` is the strict total inference-call budget (4-12), including revision calls. One bounded revision consists of Blue Team and Judge calls; the Reviewer re-audits only if a further invocation remains. `review_required` is terminal when the reviewer does not pass or the budget cannot complete the revision cycle.

```sh
python -m ubuntu_agent --db /tmp/lara-loop.sqlite3 loop-create "Assess a local recovery design" --max-rounds 7
python -m ubuntu_agent --db /tmp/lara-loop.sqlite3 loop-run LOOP_ID --invocation-limit 2
python -m ubuntu_agent --db /tmp/lara-loop.sqlite3 loop-show LOOP_ID
python -m ubuntu_agent --db /tmp/lara-loop.sqlite3 loop-resume LOOP_ID
python -m ubuntu_agent --db /tmp/lara-loop.sqlite3 loop-cancel LOOP_ID
```

`--invocation-limit` checkpoints after that many calls in the current process; it does not change the persisted total budget. A later `loop-resume` skips completed role invocations. Each call records its structured input/output and local provider/model. A stale active call is treated as having an unknown result and requires review; it is not repeated. Malformed output and provider errors fail the loop without a success-shaped fallback. The runner does not enqueue a `loop.round` job because the general worker has no loop handler. AI Loop task data is Operations-room content, so this path rejects hosted inference even if a cloud adapter is configured. No grounded sources are claimed when none were supplied.

## Local REST API

The versioned FastAPI adapter exposes health/readiness, AI Loop, task, reminder, project, calendar-event, conversation, memory-indexing, and audit operations through the existing services and SQLite tables. It binds to `127.0.0.1` only. A random one-time pairing token is stored as a hash, expires in five minutes, and exchanges for an HttpOnly, SameSite=Strict browser cookie. The cookie is Secure for HTTPS origins, and logout revokes it. State-changing requests require the exact paired `Origin`; originless requests are limited to safe reads. By default only `http://localhost:5173` and `http://127.0.0.1:5173` are trusted. Explicit HTTPS origins may be set with `UBUNTU_AGENT_API_ORIGINS`; public origins are never derived from a request Host header.

```sh
python -m ubuntu_agent --db /tmp/lara-api.sqlite3 api-session-create --origin http://localhost:5173
python -m ubuntu_agent --db /tmp/lara-api.sqlite3 api-serve --port 8765
```

For local development, pair from `http://localhost:5173`. For a temporary HTTPS tunnel, obtain its URL from ngrok, then set `LARA_PUBLIC_ORIGIN` to that exact origin when starting the application. Vite accepts only the configured tunnel hostname, proxies `/api` to `127.0.0.1:8765` with a loopback upstream Host header, and preserves the browser Origin for backend validation. Forward only port 5173 through ngrok; do not tunnel port 8765 or Ollama. The HTTPS pairing response sets a Secure cookie. `/api/v1/health` is a data-free liveness endpoint; `/api/v1/ready` reports SQLite, local Ollama, and memory status without inference. OpenAPI is available at `/api/v1/openapi.json`.

The companion `FossxHacktober-ui/frontend` now uses the authenticated local API through a Vite same-origin proxy. Tasks, reminders, AI Loop sessions, and conversations persist in SQLite. Chat calls the configured local Ollama model and persists the user turn before inference, so provider failures do not discard it. Loop runs are synchronous and the interface waits for the returned persisted state.

Chats persist user and assistant turns. Eligible exchanges are automatically indexed through the existing local document memory service (EmbeddingGemma plus Qdrant), and later conversations can retrieve authorized excerpts with SQLite provenance. Index failures do not lose chat history and can be retried when the local index is available. Credentials are excluded from long-term indexing. Projects, task links, calendar events, and audit history persist locally. Approval execution, general agent jobs, and non-loop graph inspection remain unavailable and are labelled as such; loop graphs are backed by persisted loop records.

### Run the integrated local application

In one terminal, from the backend repository:

```sh
./scripts/start-lara-dev.sh
```

The script initializes the selected database without resetting it, checks backend/model/memory readiness, issues a five-minute pairing token for the configured origin, starts the backend on loopback, then starts Vite. Paste the token into the LARA IV connection form. For local use, run `./scripts/start-lara-dev.sh`. For ngrok, first start your tunnel forwarding to `127.0.0.1:5173`, then run `LARA_PUBLIC_ORIGIN=https://YOUR-ACTUAL-NGROK-HOST ./scripts/start-lara-dev.sh`; use the same exact URL in the browser. The script configures Vite's explicit allowed-host entry and backend origin for that process only. Ollama must be running with the configured `OLLAMA_MODEL` for chat and AI Loop inference. For conversational memory, install `.[rag]` and pull `embeddinggemma`; without these, chat remains available and reports memory indexing as unavailable. Set `LARA_DB_PATH` to select a disposable database for development. Normal migrations create or upgrade its schema; no demo records are seeded.

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
