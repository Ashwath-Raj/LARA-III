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
| `reminders` | `id`, `task_id`, `scheduled_at`, `reminder_type`, `message`, `status`, `delivery_channel`, nullable `delivered_at`, `rule_snapshot`, `created_at`, `updated_at` |
| `attachments` | `id`, `task_id`, `path_or_uri`, `display_name`, `mime_type`, `size_bytes`, nullable `checksum`, `provenance`, `room_id`, `sensitivity_label`, `created_at` |
| `submissions` | `id`, `task_id`, `platform`, `course_id`, `course_name`, `assignment_id`, `assignment_name`, `file_attachment_id`, `state`, nullable `approval_id`, nullable `submission_timestamp`, nullable `verification_evidence`, `created_at`, `updated_at` |
| `projects` | `id`, `name`, `description`, `room_id`, `status`, `created_at`, `updated_at` |
| `categories` | `id`, `name`, `sort_order`, `is_active`, `created_at`, `updated_at` |
| `rooms` | `id`, `name`, `sensitivity_default`, `storage_policy`, `retention_policy`, `created_at`, `updated_at` |
| `personas` | `id`, `name`, `purpose`, `policy_profile_id`, `is_enabled`, `created_at`, `updated_at` |
| `graph_nodes` | `id`, `node_type`, `display_name`, `room_id`, `sensitivity_label`, `source_ref`, `confidence`, `metadata_json`, `created_at`, `updated_at` |
| `graph_edges` | `id`, `source_node_id`, `relation_type`, `target_node_id`, `room_id`, `source_ref`, `policy_ref`, `created_at` |
| `documents` | `id`, `source_uri`, `display_name`, `mime_type`, `content_hash`, `room_id`, `sensitivity_label`, `ingestion_status`, `created_at`, `updated_at` |
| `document_chunks` | `id`, `document_id`, `chunk_index`, `text_ref_or_text`, `token_estimate`, `content_hash`, `metadata_json`, `created_at` |
| `jobs` | `id`, `goal`, `status`, `scope_json`, `budget_json`, `current_step_id`, `checkpoint_json`, `retry_count`, `started_at`, nullable `finished_at`, nullable `report_ref` |
| `job_steps` | `id`, `job_id`, `sequence_no`, `step_type`, `status`, `input_ref`, `output_ref`, `attempt_count`, `started_at`, nullable `finished_at`, nullable `error_code` |
| `approvals` | `id`, `job_id`, `action_type`, `target_ref`, `arguments_hash`, `arguments_preview`, `requested_by`, nullable `approved_by`, `status`, `reason`, `created_at`, `expires_at`, nullable `decided_at`, nullable `executed_at` |
| `audit_events` | `id`, `timestamp`, `actor_type`, `actor_id`, `action`, `target_ref`, `policy_decision`, nullable `approval_id`, `result_status`, nullable `evidence_ref`, `safe_metadata_json` |

Recommended additional tables as needed: `reminder_rules`, `cross_room_bridges`, `provider_connections` (without secret material), `notification_events`, `schema_migrations`, `task_events`, and `source_citations`.

### Integrity and indexing

- Add foreign keys and enable SQLite foreign-key enforcement.
- Index tasks by `(status, due_date)`, reminders by `(status, scheduled_at)`, graph edges by source/target IDs, document chunks by document ID, and job steps by `(job_id, sequence_no)`.
- Use transactions for task+reminder creation, submission-state changes, and approval consumption.
- Use idempotency keys for retriable create/submit preparation operations. A retry must not duplicate tasks or reminders.
- Treat `audit_events` as append-only from the application API. Do not expose ordinary edit/delete operations for audit records.
- Store UTC timestamps for instants; retain the relevant IANA timezone for display and schedule calculations. Date-only academic deadlines remain date-only rather than being forced into midnight timestamps.

## Task and submission states

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

A bridge is an explicit, typed projection of selected fields from one room to an allowed destination. It is not unrestricted graph traversal. Persist source room, destination room, field allowlist, purpose, creating principal, creation time, expiry/revocation state and policy reference. Access checks must occur before any node or edge metadata is returned. See `09_AUTONOMY_POLICY_MATRIX.md`.

## Document ingestion and chunking

Ingestion is a pipeline with observable states:

`discovered → access_checked → parsed → normalized → chunked → embedded → indexed`

Terminal states include `skipped`, `failed` and `deleted`. Store the failure code and permit safe retry. Re-ingestion with the same content hash should be idempotent.

1. Resolve the source and its room before reading content.
2. Check permission before extraction and before any remote processing.
3. Extract text using a parser appropriate to the source type. Preserve source offsets or page/section identifiers when available.
4. Normalize whitespace and boilerplate without removing headings, code blocks, tables or meaningful list structure.
5. Chunk by structural boundary first (heading/section/paragraph), then cap by the embedding model's supported input length. Avoid splitting a code block or table when a smaller structural unit is feasible.
6. Store chunk index, document reference, source location, content hash and room labels.
7. Generate embeddings locally by default. A cloud embedding provider requires the same disclosure policy as a cloud generation model.
8. Upsert vectors idempotently and verify the indexed count before marking ingestion complete.
9. On deletion, remove document text, chunks, graph references and vectors according to retention policy; record a safe audit event without preserving the deleted content.

Use configurable chunk size/overlap based on the selected embedding model and document type; do not bake an arbitrary universal token size into the database contract. Start with a moderate chunk target and test retrieval quality against representative academic notes, PDFs, code and web pages.

## Qdrant payload and retrieval

Each Qdrant point should store a stable chunk/document ID and only the metadata required for filtering and provenance, such as `room_id`, `sensitivity_label`, `document_id`, `chunk_index`, `source_type`, and content hash. Avoid copying secrets or unnecessary full private text into payloads.

Retrieval sequence:

1. Resolve the caller/persona and requested purpose.
2. Build the allowed room/resource filter from the policy engine.
3. Search only those permitted vectors.
4. Fetch chunk content after access re-check.
5. Deduplicate adjacent chunks and rank by relevance plus source quality/freshness where appropriate.
6. Return excerpts with source references and confidence/score metadata.
7. Log the query and safe source IDs, not unrestricted private query/context text.

Never query all rooms and filter unauthorized results only in the frontend. If Qdrant is unavailable, degrade to permitted SQLite metadata/keyword search rather than bypassing room policies.
