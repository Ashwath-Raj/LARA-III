# Internal API and Service Contract

## Purpose

This document defines the initial internal interfaces between UI, application services and integrations. Python type hints and Pydantic models should be the implementation contract. If FastAPI is used, expose these contracts through OpenAPI. Do not let frontend code bypass application services and access the database directly.

## Conventions

- JSON uses `snake_case`.
- IDs are opaque strings/UUIDs, not display names.
- Timestamps are ISO 8601 UTC instants; date-only deadlines use `YYYY-MM-DD` plus the relevant timezone where required.
- Mutations accept an optional `idempotency_key` for safe retry.
- Every request requiring data access carries a server-created principal context; clients cannot self-assert a persona or room permission.
- Error responses must not expose restricted record existence, secrets, raw prompts or stack traces.

### Standard error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The due date is ambiguous.",
    "details": {"field": "due_date"},
    "request_id": "opaque-id"
  }
}
```

Use stable error codes such as `VALIDATION_ERROR`, `NOT_FOUND`, `POLICY_DENIED`, `APPROVAL_REQUIRED`, `APPROVAL_EXPIRED`, `CONFLICT`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `BUDGET_EXCEEDED`, `VERIFICATION_NEEDED` and `INTERNAL_ERROR`.

## Core service interfaces

### Task service

Required operations:

- `capture_task(input_text, context) -> TaskCaptureResult`
- `create_task(candidate, actor, idempotency_key) -> Task`
- `get_task(task_id, actor) -> Task`
- `list_tasks(filters, actor) -> TaskPage`
- `update_task(task_id, patch, actor) -> Task`
- `transition_task(task_id, target_status, actor) -> Task`
- `attach_file(task_id, file_reference, actor) -> Attachment`

`TaskCaptureResult` includes `candidate`, `missing_fields`, `clarification_questions` and `requires_confirmation`. The model may extract a due date, course, file and reminder preference, but deterministic validation must validate them before persistence.

### Deadline and reminder service

Required operations:

- `propose_reminders(task_id, rules, actor) -> ReminderPlan`
- `save_reminder_plan(task_id, plan, actor) -> Reminder[]`
- `snooze_reminder(reminder_id, until, actor) -> Reminder`
- `dismiss_reminder(reminder_id, actor) -> Reminder`
- `cancel_reminder(reminder_id, actor) -> Reminder`
- `reconcile_reminders(task_id) -> ReconciliationResult`
- `list_upcoming_reminders(window, actor) -> Reminder[]`

Reminder transitions and derived `due_now` semantics are defined in `03_DATA_AND_CHUNKING.md`. The persistent worker exposes only registered typed job handlers.

Changing a due date must safely cancel obsolete reminders and create the replacement plan in a transaction or recoverable workflow. Reminder delivery state must distinguish scheduled, delivered, missed, snoozed, dismissed and cancelled.

### Memory service

- `search_memory(query, purpose, resource_filters, limit, actor) -> MemorySearchResult[]`
- `get_node(node_id, actor) -> GraphNode`
- `get_neighbours(node_id, relation_filter, actor) -> GraphEdge[]`
- `create_bridge(bridge_candidate, actor) -> Bridge`
- `revoke_bridge(bridge_id, actor) -> Bridge`
- `ingest_document(source, actor) -> IngestionJob`

`resource_filters` narrow the query only; they never grant access. Callers cannot submit `allowed_scope` or arbitrary room IDs as proof of access. The server resolves document room and sensitivity from trusted metadata, derives the effective scope via the policy engine, and fails closed if either is missing. Ingestion checks permission before reading/extracting source content; room assignment must come from trusted configuration or an authorized explicit assignment, not untrusted document text. Search results include citations (source ID, document ID/version, and source location) and room/sensitivity labels only when the caller is authorized to see them. Citation dereference applies the same checks as content retrieval.

### Policy service

- `evaluate_access(context: AccessContext) -> PolicyDecision`

`AccessContext` includes trusted `principal_id`, `persona_id`, nullable `job_id`, `room_id`, `resource_id` or typed resource scope, `action_id`, `sensitivity_label`, `destination`, `risk_tier`, `system_mode`, and approval reference where applicable. The policy service returns `allow`, `deny` or `requires_approval`, plus policy/version, sanitized reason, decision time and any server-derived effective filter. Do not expose this as an endpoint where clients can choose trusted context fields; the application constructs them from authenticated state.

### Job/orchestrator service

- `create_job(goal, scope, budgets, actor) -> Job`
- `get_job(job_id, actor) -> Job`
- `pause_job(job_id, actor) -> Job`
- `resume_job(job_id, actor) -> Job`
- `cancel_job(job_id, actor) -> Job`
- `list_job_events(job_id, actor, cursor) -> EventPage`

The job service checks maximum duration, tool/model budgets, allowed rooms/providers, retry cap and stop conditions before starting execution.

### Approval service

- `request_approval(action_preview, actor) -> Approval`
- `get_pending_approvals(actor) -> Approval[]`
- `decide_approval(approval_id, decision, actor) -> Approval`
- `execute_approved_action(approval_id, actor) -> ActionResult`

Approval decisions are bound to the original requester principal/persona and exact action context. This single-user CLI cannot provide strong multi-user approver authentication; see `04_SECURITY_PIPELINE.md`. Approval records do not make unsupported actions executable.

The approval record binds the exact normalized tool, target and arguments hash. Execution re-evaluates policy and expiry. The decision endpoint does not itself execute the action.

## Suggested local HTTP endpoints

These are internal application routes, not Google API paths.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/tasks/capture` | Parse natural-language task candidate |
| `POST` | `/api/v1/tasks` | Create a validated task |
| `GET` | `/api/v1/tasks` | Filter/list tasks |
| `GET` | `/api/v1/tasks/{task_id}` | Retrieve task and allowed related metadata |
| `PATCH` | `/api/v1/tasks/{task_id}` | Apply a validated task patch |
| `POST` | `/api/v1/tasks/{task_id}/transitions` | Change status using allowed state transitions |
| `GET` | `/api/v1/reminders` | List reminders for the current principal |
| `POST` | `/api/v1/jobs` | Create a bounded job |
| `GET` | `/api/v1/jobs/{job_id}` | Inspect durable job state |
| `POST` | `/api/v1/jobs/{job_id}/pause` | Pause a job |
| `POST` | `/api/v1/jobs/{job_id}/resume` | Resume if policy and budgets permit |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Cancel a job |
| `GET` | `/api/v1/approvals` | List pending approvals |
| `POST` | `/api/v1/approvals/{approval_id}/decision` | Approve or reject the displayed proposal |
| `POST` | `/api/v1/memory/search` | Room-aware retrieval |
| `GET` | `/api/v1/memory/nodes/{node_id}` | Retrieve an authorized graph node |
| `GET` | `/api/v1/memory/nodes/{node_id}/neighbours` | Retrieve authorized edges and nodes |
| `GET` | `/api/v1/integrations/classroom/courses` | List authorized Classroom courses |
| `GET` | `/api/v1/integrations/classroom/coursework` | List assignments for an authorized course |

The first prototype may expose only the endpoints needed for its workflow. Do not create generic `/execute-shell` or unrestricted `/tool-call` endpoints.

Memory endpoints must not reveal denied resources through result counts, titles, labels, citations, or distinct error messages. Vector candidate selection and graph traversal are policy-filtered server-side; frontend filtering is never an authorization boundary. Before external model calls, the router authorizes every cited/context item and the assembled disclosure packet against the destination.

### Implemented local HTTP API slice

The backend exposes these routes through FastAPI and the existing services. Every data route requires a one-time CLI pairing exchange followed by an HttpOnly, SameSite=Strict cookie. Requests must carry an exact allowlisted `Origin`; CORS never uses a wildcard. The server-created actors are fixed by route group (`task_deadline_manager` for tasks/reminders and `desktop_operator` for loops). Clients cannot supply principal, persona, room grants, or policy filters.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Data-free liveness and implemented-capability status |
| `GET` | `/api/v1/ready` | SQLite check, local Ollama probe, and honest vector-store availability state |
| `POST` | `/api/v1/auth/session` | Consume one-time CLI token and set local browser session cookie |
| `GET` | `/api/v1/auth/session` | Inspect the authenticated local session |
| `DELETE` | `/api/v1/auth/session` | Revoke session and clear cookie |
| `POST` | `/api/v1/loops` | Create persistent local-only AI Loop |
| `GET` | `/api/v1/loops` | Paginated loop listing |
| `GET` | `/api/v1/loops/{loop_id}` | Inspect persisted lifecycle, roles and rounds |
| `POST` | `/api/v1/loops/{loop_id}/run` | Synchronously run from a new loop; accepts an invocation limit |
| `POST` | `/api/v1/loops/{loop_id}/resume` | Resume a safely checkpointed loop |
| `POST` | `/api/v1/loops/{loop_id}/cancel` | Persist cancellation |
| `GET` | `/api/v1/loops/{loop_id}/roles` | Retrieve role status and persisted invocations |
| `GET` | `/api/v1/loops/{loop_id}/rounds` | Paginated persisted model invocation history |
| `GET` | `/api/v1/loops/{loop_id}/graph` | Retrieve loop-scoped graph nodes/edges |
| `GET` | `/api/v1/loops/{loop_id}/artifacts` | Paginated persisted artifact list |
| `POST` | `/api/v1/tasks` | Create a validated task; honors `Idempotency-Key` |
| `GET` | `/api/v1/tasks` | Paginated authorized task list |
| `GET` | `/api/v1/tasks/{task_id}` | Retrieve an authorized task |
| `PATCH` | `/api/v1/tasks/{task_id}` | Update supported task fields |
| `POST` | `/api/v1/tasks/{task_id}/transitions` | Apply validated task status transition |
| `DELETE` | `/api/v1/tasks/{task_id}` | Delete an authorized task and cascade its reminders |
| `GET` | `/api/v1/reminders` | Paginated authorized reminder list |
| `POST` | `/api/v1/reminders` | Create a validated reminder |
| `POST` | `/api/v1/reminders/{reminder_id}/snooze` | Snooze reminder |
| `POST` | `/api/v1/reminders/{reminder_id}/dismiss` | Dismiss reminder |
| `POST` | `/api/v1/reminders/{reminder_id}/cancel` | Cancel reminder |
| `GET` | `/api/v1/conversations` | List persistent local conversations |
| `POST` | `/api/v1/conversations` | Create a conversation |
| `PATCH` | `/api/v1/conversations/{conversation_id}` | Rename or enable/disable memory for a conversation |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | Delete a conversation and invalidate its memory sources |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Read persisted ordered messages |
| `POST` | `/api/v1/conversations/{conversation_id}/messages` | Idempotently persist a user turn, retrieve authorized memory, invoke local Ollama and persist its response |
| `POST` | `/api/v1/conversations/{conversation_id}/memory/{message_id}/exclude` | Exclude an indexed exchange and invalidate its vector source |
| `POST` | `/api/v1/conversations/{conversation_id}/memory/{message_id}/retry` | Retry a failed local index write |
| `GET` | `/api/v1/projects` | List authorized persisted projects and linked task IDs |
| `POST` | `/api/v1/projects` | Create a project in an authorized writable room |
| `GET` | `/api/v1/projects/{project_id}` | Inspect one authorized project |
| `PATCH` | `/api/v1/projects/{project_id}` | Update project metadata or milestone state |
| `DELETE` | `/api/v1/projects/{project_id}` | Delete a project and detach, but retain, its tasks |
| `GET` | `/api/v1/calendar/events` | List authorized persisted events |
| `POST` | `/api/v1/calendar/events` | Create a timezone-aware calendar event |
| `POST` | `/api/v1/calendar/events/{event_id}/cancel` | Cancel a scheduled event |
| `GET` | `/api/v1/audit-events` | Read bounded safe audit summaries for the local principal |

The API binds to `127.0.0.1` by default through the CLI. Pairing tokens are random, short-lived, consumed once, and stored only as SHA-256 hashes. Sessions expire after 1-24 hours (8 by default); exact localhost origins are configured by `UBUNTU_AGENT_API_ORIGINS`. The browser session cookie is HttpOnly, SameSite=Strict, path-scoped to `/api/v1`, and not marked Secure because this development server is HTTP on loopback. The auth exchange is rate-limited. Health/readiness never invokes model inference or contacts hosted providers. Error responses use the standard envelope and omit exception traces and request contents.

### Remaining frontend/backend boundary

The frontend uses a same-origin Vite proxy and authenticated HTTP adapter. Its camelCase domain types are mapped at the adapter boundary. The following requested capabilities remain unavailable:

- HTTP endpoints for general memory search, approvals, and jobs. Approval/job screens are explicitly labelled unavailable; no sample records are returned.
- General cross-source Knowledge Graph inspection. AI Loop graph records and persisted provenance are available through the loop graph endpoint.
- A dedicated dashboard aggregate endpoint. The frontend computes dashboard counts from persisted tasks, reminders, and loops.
- A background worker for AI Loop execution; run/resume requests are synchronous.

The UI reports those capabilities as unavailable or shows empty states; it does not seed mock records into these views.

AI Loop routes keep the current local-only provider policy. Requests must use the server-created principal context; clients cannot supply trusted persona, room, or authorization fields. Responses keep invocation outputs distinct from role assignments: a `loop_roles` row alone is not proof that a specialist ran. A role result is completed only when a persisted `loop_rounds` invocation records its role, structured input/output, provider/model, status, and error state. A stale in-flight call has an unknown outcome and becomes `review_required`, not an automatic retry. Cancellation and provider failure are persisted.

## Event contract

Emit application events for meaningful state changes. Minimum envelope:

```json
{
  "event_id": "opaque-id",
  "event_type": "job.step.completed",
  "occurred_at": "2026-10-10T12:00:00Z",
  "aggregate_type": "job",
  "aggregate_id": "opaque-id",
  "sequence": 4,
  "safe_payload": {}
}
```

Initial event types include `task.created`, `task.updated`, `reminder.scheduled`, `reminder.delivered`, `approval.requested`, `approval.decided`, `job.started`, `job.step.completed`, `job.blocked`, `job.completed`, `job.failed`, and `submission.verification_needed`. Events must not include credentials or unnecessary private content.

## Google OAuth contract

- Start with minimum read-only scopes needed to list courses and assignments. Request additional scopes only when an enabled feature requires them.
- Keep OAuth callback handling and token exchange in the backend/local service, not frontend JavaScript.
- Store refresh tokens using the OS keyring or a secret store. SQLite may store a connection ID and granted-scope metadata, not token values.
- On missing or revoked consent, transition the integration to `reauthorization_required`; do not retry forever or ask the model to work around the denial.
- The initial Classroom path is read-only lookup and submission preparation. Write/submission capabilities require a separate scope review, explicit approval, and verifiable postconditions.
- Never claim Classroom submission succeeded based only on a successful HTTP request or button click; verify the resulting submission state.

## Contract tests

Write tests for invalid date candidates, unauthorized room search, stale approval, changed arguments, idempotent task creation, reminder rescheduling, expired OAuth consent, unavailable provider, and unverified submission.

Memory/security contract tests must also prove:

- A room-A caller cannot retrieve room-B chunk content, citation, source metadata, result count, graph node, edge, neighbor, or descriptive denial detail; include direct ID lookups as well as search/traversal.
- A forged Qdrant payload or stale vector for a deleted, superseded, unlabelled or moved document is rejected by the authoritative SQLite re-check.
- A missing room/sensitivity label and a policy-evaluator exception deny access without invoking an embedder, vector result serializer or model provider.
- Revoked, expired, wrong-purpose, wrong-destination and field-expanded bridges expose no projected fields; bridge metadata itself is hidden from unauthorized callers.
- A cloud prompt spy receives no unauthorized chunk, graph-derived field, citation excerpt or metadata, including when an allowed and denied result are returned together. Assert on the complete serialized prompt and provider-call count, not only on UI output.
- Authorized citations resolve to the expected source, document version and page/section/offset; after update/deletion, old citation content is not returned.

Use temporary SQLite databases, fake embedders, fake Qdrant candidate results, a deterministic policy engine and a provider spy. These tests require no Ollama, Google OAuth, Qdrant service or external API.
