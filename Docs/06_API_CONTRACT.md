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
- `reconcile_reminders(task_id) -> ReconciliationResult`
- `list_upcoming_reminders(window, actor) -> Reminder[]`

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
