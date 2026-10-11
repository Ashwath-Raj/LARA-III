# System Architecture

## Scope

This document owns component boundaries, dependency direction and runtime flows. It does not replace the data schema (`03_DATA_AND_CHUNKING.md`), security enforcement details (`04_SECURITY_PIPELINE.md`), action permission defaults (`09_AUTONOMY_POLICY_MATRIX.md`) or public API shapes (`06_API_CONTRACT.md`).

## Logical architecture

```text
CLI / Local Dashboard
        |
Task Capture + Input Validation
        |
Task Store + Reminder Store + Durable Job Store
        |
Orchestrator / Job State Machine
        |
Policy Engine + Approval Service
        |
Model Router ---- Ollama / Approved Hosted Providers
        |
Typed Tool Registry
   |          |            |             |
Filesystem  Browser     Google APIs    Memory
   |          |            |             |
Verification + Audit + Checkpoints + Reports + Notifications
        |
SQLite structured state + Qdrant local semantic index
```

Dependency direction is from interfaces toward domain services: task/reminder domain and persistence do not import Ollama, Qdrant, FastAPI, or frontend code. Model parsing is an optional adapter; manual typed task operations remain available without it. The memory service depends on storage and embedding interfaces, and the policy interface is injected at every protected read/disclosure boundary.

## Components and responsibilities

### CLI and local dashboard

- The CLI and authenticated loopback FastAPI adapter call the same application services. The API binds to `127.0.0.1`; it does not provide a separate business-logic path.
- UI code must call application services, not edit SQLite tables directly.
- The dashboard displays proposals, task state, approval requests and execution evidence. It is not itself a security boundary.

### Task and deadline services

- Parse natural-language input into a typed candidate object using a model when useful.
- Validate date semantics, status transitions, categories and attachment references deterministically.
- Persist the task and related reminder-rule changes transactionally.
- Remain functional if model inference is unavailable; manual task capture must still work.

### Durable orchestrator

The orchestrator is a state machine rather than an unbounded agent loop. A job has a goal, permitted scope, budget, current step, checkpoint, retry count and terminal result. It dispatches one bounded step at a time, saves the result, then advances the state.

Suggested lifecycle:

`queued → planning → running → awaiting_approval → running → verifying → completed`

Alternative states: `paused`, `blocked`, `failed`, `cancelled`, `needs_attention`.

The lifecycle can revisit `running` after approval. Use explicit transitions; do not infer state from free-form model text. Each side-effecting step must have an idempotency strategy or a recovery procedure for uncertain outcomes.

The Phase 4 SQLite job queue provides idempotent enqueue, typed payload revalidation, leases, capped retries, cancellation, pause/kill checks and a bounded foreground worker. Its implemented handler set is deliberately limited to local reminder delivery. The queue and handler registry are not a generic shell or browser execution interface.

The AI Loop runs synchronously in the invoking CLI/API process and uses its own per-loop SQLite lease because no loop job handler exists. It persists an invocation record before each local model call and commits the result plus next pending step before releasing the lease. The total invocation budget is strict. A restart between calls resumes from the next pending role without replaying completed invocations; a stale in-flight call is treated as uncertain and requires review. The HTTP run/resume calls wait for their bounded invocation request; they are not background jobs.

### Policy and approvals

The policy engine authorizes every tool call before execution. Approval creation and consumption are separate operations. The executor must re-check policy and approval immediately before an action. See `04_SECURITY_PIPELINE.md`.

### Model router

Selects a provider based on task capability, privacy class, context budget, latency, configured provider availability and cost/runtime budget. It must not send more context than the task requires. Local Ollama is the default route for permitted routine/private work. Hosted reasoning is used only when configured and allowed by policy.

The router returns normalized metadata: provider/model ID, route, latency, request ID if available, and safe usage/cost metadata. It must not claim all providers expose identical capabilities.

### Typed tool registry

Each tool definition includes:

- stable tool ID and version
- JSON/Pydantic argument schema
- output schema
- permission/risk metadata
- timeout and resource limits
- idempotency/retry behaviour
- validation and verification hooks
- audit metadata policy

The model may only request tools exposed in its current context. Tool implementations call downstream systems through adapters and return structured results.

### Memory service

Owns source/document ingestion, local embedding, chunk/version lifecycle, Qdrant candidate search, SQLite-authoritative content/provenance lookup, graph traversal and citation assembly. It calls the deterministic policy service before reads and disclosures. SQLite stores authoritative room, sensitivity, source, document/chunk and graph records; Qdrant stores candidate vectors and filter metadata. Neither store grants access or may widen policy scope. Update/deletion behavior follows `03_DATA_AND_CHUNKING.md`; incomplete indexing/deletion makes affected records unavailable until reconciliation.

### Policy service

Implements the deterministic `AccessContext -> PolicyDecision` interface in `04_SECURITY_PIPELINE.md` using the canonical defaults in `09_AUTONOMY_POLICY_MATRIX.md`. It returns policy-derived resource filters for memory queries; user interfaces, model output and provider adapters cannot supply or expand those filters.

### Integration adapters

Adapters hide provider-specific details behind small interfaces. They must expose capability availability and failure reasons. Provider failure must degrade gracefully; for example, failed hosted inference must not trigger silent cloud routing through an unapproved provider.

### Verification service

Defines postconditions for operations. Examples: a file exists with expected properties; a task row is persisted; an API response confirms an upload; a browser page displays a verifiable submitted state. Verification is independent from the model's assertion that it succeeded.

### Audit, reports and notifications

Audit stores safe action evidence; reports summarize a job's outputs and uncertainties; notifications point to the local task/run. Notifications are not the sole record of a job's state.

## Dependency rules

- Domain services must not depend on CLI or UI modules.
- Policy checks must not depend on model judgement.
- Tool adapters must not directly query application database tables; they return typed data to application services.
- UI actions must go through the same services and policy pipeline as autonomous actions.
- Memory retrieval must check access before returning content.
- Task and reminder domain services must run without Ollama, Qdrant or provider credentials. They may depend on SQLite and deterministic validation only. Task records still carry a valid room reference so authorization is not bolted on later.
- Embedding is behind an adapter and defaults to local execution. The memory service and task service must not import a specific embedding runtime or Qdrant SDK directly; provider/index adapters implement replaceable interfaces.
- Any graph/vector result used to construct a model prompt is authorized by the memory service and checked again by model routing against the destination provider.
- Integrations must be replaceable without changing task and job domain models.
- The application must support a local-only configuration with hosted providers disabled.

## Core runtime flows

### Natural-language assignment capture

1. UI receives user text.
2. Task parser returns structured candidate fields and unresolved questions.
3. Validator resolves or requests clarification for ambiguous dates/course.
4. Task service persists task and reminder rules transactionally.
5. Reminder scheduler reconciles due events.
6. UI confirms the exact saved task and reminder schedule.

### Tool execution

1. Orchestrator asks the model for a next step or selects a deterministic step.
2. Tool registry validates tool name and argument schema.
3. Policy pipeline evaluates permissions and approval requirements.
4. Executor runs an approved registered adapter.
5. Verification checks the postcondition.
6. The step result, audit event and checkpoint are persisted before advancing.

### Overnight job recovery

On startup, find non-terminal jobs, reconcile their step states and check whether an in-flight external action has an uncertain outcome. Resume only idempotent or verified-safe work. Pause jobs if approval expired, session state is unknown, budgets are exhausted or policy configuration changed materially.

## Initial deployment shape

Use a single-user local process first:

- Python application package
- SQLite database with migrations
- Qdrant local storage
- Ollama local endpoint
- Optional local FastAPI dashboard
- One dedicated Playwright browser context
- Desktop notification adapter
- Local report/artifact directory

Split into separate processes only when reliability, permissions or resource isolation justify it. Keep secrets and runtime data outside the source tree.

## Delivery phases and Phase 1 security floor

**Phase 1 (task core):** implement SQLite `rooms` and `personas` records (or equivalent versioned bootstrap records), stable IDs, validated sensitivity labels, trusted actor/persona context, room ownership on every personal/task record, action and risk enums, and the deterministic policy interface with deny-by-default behavior. Encode the default persona/room/action rules from `09_AUTONOMY_POLICY_MATRIX.md`; do not add user-configurable grants until their persistence and revocation semantics are specified. Make policy checks part of task, file-attachment and reminder service entry points. Local-only is the only available model destination until provider disclosure checks exist. Manual task CRUD must work when Ollama and Qdrant are absent.

**Phase 2 (guarded tools and providers):** route every registered tool and provider request through policy and approval enforcement, including exact-action approvals and destination checks.

**Phase 3 (RAG):** add sources, documents, versioned chunks, local embedding adapter, Qdrant index, graph access, citations/provenance, deletion reconciliation and cross-room bridge projection per `03_DATA_AND_CHUNKING.md` and `04_SECURITY_PIPELINE.md`. RAG must not be a prerequisite for the task service.
