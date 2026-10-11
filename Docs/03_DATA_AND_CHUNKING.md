# Data Model, Knowledge Graph and Chunking

## Scope and ownership

This document owns persistent data shapes and retrieval/ingestion rules. Authorization enforcement belongs to `04_SECURITY_PIPELINE.md`; the default allowed-access matrix belongs to `09_AUTONOMY_POLICY_MATRIX.md`; external provider details belong to `10_INTEGRATION_MATRIX.md`.

SQLite is the initial source of truth for structured application state. A local Qdrant store is used for semantic retrieval. Do not treat vector search as an authorization system.

## Storage boundaries

- Store the database, Qdrant files, screenshots, reports and browser state under an application-data directory with user-only filesystem permissions.
- Keep secrets and OAuth refresh tokens in the OS keyring or an appropriate secret store, not in SQLite records, graph metadata, vector payloads or logs.
- Every record that can contain personal content must have a room and sensitivity label or an explicitly documented reason why it does not.
- Use stable opaque IDs. Display names are not keys.
- Apply database migrations for every schema change. Do not rely on `CREATE TABLE IF NOT EXISTS` as the only migration strategy.

## Initial SQLite entities

Use these tables as the first contract. Add fields only when a real workflow needs them; maintain migrations and tests.

| Table | Required content |
|---|---|
| `tasks` | `id`, `title`, `description`, `item_type`, `status`, `priority`, `category_id`, nullable `project_id`, `room_id`, nullable `persona_owner`, `due_date`, nullable `due_at`, `timezone`, nullable `personal_target_at`, nullable `estimated_minutes`, `source_text`, `created_at`, `updated_at`, nullable `completed_at`, nullable `completion_evidence` |
| `reminders` | `id`, `task_id`, `scheduled_at`, `reminder_type`, `message`, `status`, `delivery_channel`, nullable `delivered_at`, `rule_snapshot`, `created_at`, `updated_at`; migration-managed `generation` invalidates queued delivery for an obsolete occurrence |
| `attachments` | `id`, `task_id`, `path_or_uri`, `display_name`, `mime_type`, `size_bytes`, nullable `checksum`, `provenance`, `room_id`, `sensitivity_label`, `created_at` |
| `submissions` | `id`, `task_id`, `platform`, `course_id`, `course_name`, `assignment_id`, `assignment_name`, `file_attachment_id`, `state`, nullable `approval_id`, nullable `submission_timestamp`, nullable `verification_evidence`, `created_at`, `updated_at` |
| `projects` | `id`, `name`, `description`, `room_id`, `status`, `created_at`, `updated_at` |
| `categories` | `id`, `name`, `sort_order`, `is_active`, `created_at`, `updated_at` |
| `rooms` | `id`, `name`, `sensitivity_default`, `storage_policy`, `retention_policy`, `created_at`, `updated_at` |
| `personas` | `id`, `name`, `purpose`, `policy_profile_id`, `is_enabled`, `created_at`, `updated_at` |
| `sources` | `id`, `source_type`, `canonical_ref`, `display_name`, `trust_label`, nullable `retrieved_at`, `metadata_json`, `created_at` |
| `graph_nodes` | `id`, `node_type`, `display_name`, `room_id`, `sensitivity_label`, nullable `source_id`, `confidence`, `metadata_json`, `created_at`, `updated_at` |
| `graph_edges` | `id`, `source_node_id`, `relation_type`, `target_node_id`, `room_id`, `sensitivity_label`, nullable `source_id`, `policy_ref`, `created_at` |
| `documents` | `id`, `source_id`, `source_uri`, `display_name`, `mime_type`, `content_hash`, `room_id`, `sensitivity_label`, `active_version`, `ingestion_status`, `created_at`, `updated_at` |
| `document_chunks` | `id`, `document_id`, `version`, `chunk_index`, `text_ref_or_text`, `source_location`, `token_estimate`, `content_hash`, `room_id`, `sensitivity_label`, `created_at` |
| `cross_room_bridges` | `id`, `source_room_id`, `source_entity_id`, `destination_room_id`, `recipient_scope_json`, `field_allowlist_json`, `purpose`, `created_by`, `created_at`, nullable `expires_at`, nullable `revoked_at`, `policy_ref`, `cloud_destinations_json` |
| `jobs` | Stable `id`, `job_type`, validated `payload_json`, unique `idempotency_key`, queue status, attempts, eligibility time, lease owner/expiry, retry limit/backoff, safe error class, cancellation and timestamps. See Phase 4 queue migration. |
| `job_steps` | `id`, `job_id`, `sequence_no`, `step_type`, `status`, `input_ref`, `output_ref`, `attempt_count`, `started_at`, nullable `finished_at`, nullable `error_code` |
| `approvals` | `id`, requester principal/persona, action/risk, resource/room/destination, canonical arguments and SHA-256 fingerprint, policy reference, status, creation/expiry/decision/consumption metadata. SQLite migration 4 creates the approval lifecycle table. |
| `audit_events` | `id`, `timestamp`, `actor_type`, `actor_id`, `action`, `target_ref`, `policy_decision`, nullable `approval_id`, `result_status`, nullable `evidence_ref`, `safe_metadata_json` |

Recommended additional tables as needed: `reminder_rules`, `provider_connections` (without secret material), `notification_events`, `schema_migrations`, `task_events`, and `source_citations`.

### AI Loop execution records (SQLite migration 7)

- `loop_execution_state` is the authoritative lifecycle row for a loop. It stores `waiting`, `running`, `succeeded`, `failed`, `cancelled`, or `review_required`, the current role/invocation, pending role steps, total invocation count, reviewer verdict, final synthesis, sanitized failure class, and the worker lease.
- Each `loop_rounds` row is one model invocation, not a debate-cycle summary. It records the role, stage, exact structured input JSON, structured output JSON, provider/model provenance, attempt count, status, and sanitized error class. Invocation IDs are stable UUIDv5 values derived from the parent loop ID and invocation sequence.
- `loop_roles` summarizes the most recent state for each of the four roles. Its related invocation history and outputs remain in `loop_rounds`; the role row alone is never execution evidence.
- `ai_loops.max_rounds` is a strict **total model-invocation budget**, including failed calls. A normal completed loop uses four invocations: Blue Team proposal, Red Team challenge, Judge synthesis, and Unbiased Reviewer audit. The current runner does not retry a failed model call.
- If the Reviewer says `revise`, one bounded revision may add a Blue Team revision and a Judge re-synthesis. The Reviewer re-audits only if at least one further invocation remains. If the budget cannot complete and re-review that cycle, the final state is `review_required`, never `succeeded`.
- A role result and the next pending plan are committed atomically. The runner releases its SQLite lease between role invocations, so a process restart resumes from completed records without repeating them. A stale lease with an active role is ambiguous: that invocation is marked failed with `interrupted_unknown_result`, and the loop becomes `review_required` instead of repeating a possibly completed call.
- Loop prompts are operations-room data and this milestone routes them only to local Ollama. Evidence is included only from loop-scoped records explicitly marked ingested; with no such records, the Judge and final artifact expose that no grounded evidence was available. Model-generated reasoning is not a source citation.
- The general `jobs` queue does not have a loop handler. Loop recovery is provided by the per-loop lease and persisted invocation state; no unconsumed queued job is created.

### Integrity and indexing

- Add foreign keys and enable SQLite foreign-key enforcement.
- `document_chunks.document_id` references `documents`; graph/source references use stable IDs. Every document, chunk, graph node and graph edge has exactly one owning room and a sensitivity label. An edge is readable only when both endpoint nodes and the edge itself are authorized. Cross-room relationships are represented as an explicit bridge projection, not as an edge that grants access to either source room.
- Define sensitivity labels as the centrally validated vocabulary owned by `09_AUTONOMY_POLICY_MATRIX.md`. A room's `sensitivity_default` supplies a label only at trusted ingestion/creation time; missing or invalid labels are errors, never treated as public. Derived chunks and graph facts inherit the most restrictive input label.
- Store source identity/provenance separately from retrieved content. A source citation resolves to a `sources` record plus a document/chunk and source location; citations do not by themselves grant read access.
- Index tasks by `(status, due_date)`, reminders by `(status, scheduled_at)`, graph edges by source/target IDs, document chunks by document ID, and job steps by `(job_id, sequence_no)`.
- Use transactions for task+reminder creation, submission-state changes, and approval consumption.
- Use idempotency keys for retriable create/submit preparation operations. A retry must not duplicate tasks or reminders.
- Treat `audit_events` as append-only from the application API. Do not expose ordinary edit/delete operations for audit records.
- Queue jobs use unique idempotency keys, typed payload validation on insertion and again on claim/dispatch, attempt-bounded capped exponential retry, and expiring worker leases. Only registered job types and explicitly installed handlers can dispatch.
- Store UTC timestamps for instants; retain the relevant IANA timezone for display and schedule calculations. Date-only academic deadlines remain date-only rather than being forced into midnight timestamps.

## Task and submission states

### Reminder state transitions

Persist only `scheduled`, `delivered`, `missed`, `snoozed`, `dismissed` and `cancelled`. `due_now` is a derived view: a scheduled reminder whose UTC `scheduled_at` is at or before the view clock. Legal transitions are `scheduled → delivered | missed | snoozed | dismissed | cancelled`, `missed → snoozed | dismissed | cancelled`, and `snoozed → delivered | missed | dismissed | cancelled`. Delivered, dismissed and cancelled are terminal. Snooze and schedule replacement increment `generation`; every delivery job carries the generation it was created for and must match it at dispatch and commit. When a deadline-relative reminder is recomputed, preserve its existing ID, update its schedule and increment generation in the same transaction. A successful notification may mark delivered only if that generation remains current.

Task status and submission status are separate state machines.

Suggested task states: `inbox`, `next`, `in_progress`, `waiting`, `review`, `ready_to_submit`, `done`, `archived`.

Suggested submission states: `not_ready`, `prepared`, `awaiting_approval`, `submitting`, `submitted`, `verification_needed`, `failed`.

Only mark a task done when its completion rule is satisfied. A submission being uploaded is not evidence that the final turn-in action succeeded. A successful click is not evidence of a verified submission.

## Knowledge graph

The graph stores explicit entities and typed relationships. Nodes should include, where relevant, courses, assignments, tasks, projects, files, people, providers, research claims, sources, deadlines and jobs.

Example edges:

- `ASSIGNMENT —BELONGS_TO→ COURSE`
- `TASK —BLOCKED_BY→ TASK`
- `TASK —REQUIRES_FILE→ ATTACHMENT`
- `TASK —HAS_DEADLINE→ DEADLINE`
- `PROJECT —USES_MODEL→ MODEL`
- `CLAIM —SUPPORTED_BY→ SOURCE`
- `PERSONA —ALLOWED_BRIDGE→ BRIDGE` (configuration reference only; not the sole enforcement mechanism)

Every fact/edge that supports a consequential claim should retain provenance: source URI or local reference, extraction time, optional excerpt/hash, confidence where meaningful, and room/sensitivity labels. Do not convert an LLM inference into a source fact without marking it as inferred.

### Cross-room bridges

A bridge is an explicit, typed projection of selected fields from one source entity/room to an allowed destination and recipient scope. It is not unrestricted graph traversal. Persist source room/entity, destination room, recipient scope, field allowlist, purpose, creating principal, creation time, expiry/revocation state, policy reference and explicitly allowed cloud destinations. Access checks must occur before any node or edge metadata is returned. See `09_AUTONOMY_POLICY_MATRIX.md`.

Bridge projections are materialized or resolved only for the named destination and fields. They do not change the source entity's room, authorize general graph traversal, or implicitly permit cloud disclosure. Enforce expiry/revocation on every read; revoke derived projections and invalidate affected caches/indexes. Preserve only the minimum bridge audit metadata after revocation.

## Document ingestion and chunking

Ingestion is a pipeline with observable states:

`discovered → access_checked → parsed → normalized → chunked → embedded → indexed`

Terminal states include `skipped`, `failed` and `deleted`. Store the failure code and permit safe retry. Re-ingestion with the same content hash should be idempotent.

1. Resolve the source, owning room and sensitivity label from trusted configuration/metadata before reading content; reject missing or conflicting metadata.
2. Check permission before extraction and before any remote processing. The initial embedding path is local-only; a cloud embedding is a separate disclosure action evaluated against the destination provider.
3. Extract text using a parser appropriate to the source type. Preserve source offsets or page/section identifiers when available.
4. Normalize whitespace and boilerplate without removing headings, code blocks, tables or meaningful list structure.
5. Chunk by structural boundary first (heading/section/paragraph), then cap by the embedding model's supported input length. Avoid splitting a code block or table when a smaller structural unit is feasible.
6. Store chunk index, document/version reference, source location, content hash, owning room and sensitivity label. Preserve source ID and page/section/offset data needed to create citations.
7. Generate embeddings locally by default. A cloud embedding provider requires the same disclosure policy as a cloud generation model.
8. Upsert vectors idempotently using stable chunk IDs scoped to document version; verify the indexed IDs/count before marking that version active. On update, activate the new version only after indexing succeeds, then retire old vectors/chunks. If indexing or cleanup is incomplete, mark the document unavailable to retrieval until reconciliation finishes.
9. On deletion, first tombstone the document so retrieval rejects it, then remove document text, chunks, graph references and vectors according to retention policy; record a safe audit event without preserving the deleted content. Do not report deletion complete while searchable copies remain.

Use configurable chunk size/overlap based on the selected embedding model and document type; do not bake an arbitrary universal token size into the database contract. Start with a moderate chunk target and test retrieval quality against representative academic notes, PDFs, code and web pages.

## Qdrant payload and retrieval

Each Qdrant point should store a stable chunk/document-version ID and only the metadata required for candidate filtering and provenance, such as `room_id`, `sensitivity_label`, `document_id`, `document_version`, `chunk_index`, `source_id`, `source_location_ref`, and content hash. Avoid copying secrets or unnecessary full private text into payloads. SQLite remains authoritative for room, label, document version, active/deleted state, and chunk text.

Retrieval sequence:

1. Resolve trusted principal, persona, job, purpose, destination and requested resource scope.
2. Ask the policy engine for an effective room/resource filter; callers cannot supply an authoritative `allowed_scope`.
3. Search Qdrant using that restrictive filter. Treat returned IDs and payloads as untrusted candidates, not authorization evidence.
4. Fetch each candidate's active SQLite record and text, re-check its room, sensitivity, document version, deletion state and current authorization. Drop denied candidates before ranking, snippets, counts or citations are constructed.
5. Deduplicate adjacent chunks and rank authorized results by relevance plus source quality/freshness where appropriate.
6. Return only authorized excerpts with source/document references, source locations and confidence/score metadata. Citations resolve through the same authorization path.
7. Log the query and safe source IDs, not unrestricted private query/context text.

Never query all rooms and filter unauthorized results only in the frontend. If Qdrant is unavailable, degrade to permitted SQLite metadata/keyword search rather than bypassing room policies.

For cloud model routing, check every selected excerpt and its citation provenance against the destination provider immediately before prompt construction/send. Re-check after context assembly so prompt templates, summaries, graph-derived metadata and citations cannot reintroduce denied data. Provider failure must not cause fallback to a different or cloud provider that has not been allowed.

## Unresolved data and lifecycle decisions

- Define source trust labels and citation retention/erasure behaviour, including externally hosted URLs whose contents later change.
- Define the consistency/availability policy for SQLite and Qdrant during deletion, failed re-index, backup restore and interrupted cleanup. This contract requires deny/unavailable until reconciliation, but operational timing/repair policy remains open.
- Define the retention period for revoked bridge metadata and the operational process for removing materialized projections; authorization must deny revoked projections immediately regardless of cleanup lag.
