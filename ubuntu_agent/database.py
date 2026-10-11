"""SQLite persistence and versioned migrations for the local core."""

import sqlite3
import os
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (1, """
    CREATE TABLE rooms (
      id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
      sensitivity_default TEXT NOT NULL CHECK (sensitivity_default IN ('public','internal','sensitive','restricted')),
      storage_policy TEXT NOT NULL, retention_policy TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE personas (
      id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, purpose TEXT NOT NULL,
      policy_profile_id TEXT NOT NULL, is_enabled INTEGER NOT NULL CHECK (is_enabled IN (0,1)),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE categories (
      id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, sort_order INTEGER NOT NULL,
      is_active INTEGER NOT NULL CHECK (is_active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE tasks (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      item_type TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN
       ('inbox','next','in_progress','waiting','review','ready_to_submit','done','archived')),
      priority TEXT NOT NULL CHECK (priority IN ('low','normal','high','urgent')),
      category_id TEXT NOT NULL REFERENCES categories(id), project_id TEXT,
      room_id TEXT NOT NULL REFERENCES rooms(id), persona_owner TEXT REFERENCES personas(id),
      due_date TEXT, due_at TEXT, timezone TEXT NOT NULL, personal_target_at TEXT,
      estimated_minutes INTEGER, source_text TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, completion_evidence TEXT,
      idempotency_key TEXT UNIQUE
    );
    CREATE INDEX tasks_status_due_date ON tasks(status, due_date);
    CREATE TABLE reminders (
      id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      scheduled_at TEXT NOT NULL, reminder_type TEXT NOT NULL, message TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('scheduled','delivered','missed','snoozed','dismissed','cancelled')),
      delivery_channel TEXT NOT NULL, delivered_at TEXT, rule_snapshot TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX reminders_status_scheduled_at ON reminders(status, scheduled_at);
    CREATE TABLE audit_events (
      id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, actor_type TEXT NOT NULL,
      actor_id TEXT NOT NULL, action TEXT NOT NULL, target_ref TEXT,
      policy_decision TEXT NOT NULL, approval_id TEXT, result_status TEXT NOT NULL,
      evidence_ref TEXT, safe_metadata_json TEXT NOT NULL
    );
    CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    """),
    (2, """
    CREATE TABLE task_idempotency_keys (
      principal_id TEXT NOT NULL,
      persona_id TEXT NOT NULL REFERENCES personas(id),
      idempotency_key TEXT NOT NULL,
      request_fingerprint TEXT NOT NULL,
      task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL,
      PRIMARY KEY (principal_id, persona_id, idempotency_key)
    );
    """),
    (3, """
    CREATE TABLE sources (
      id TEXT PRIMARY KEY, source_type TEXT NOT NULL, canonical_ref TEXT NOT NULL,
      display_name TEXT NOT NULL, trust_label TEXT NOT NULL, retrieved_at TEXT,
      metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
      UNIQUE(canonical_ref)
    );
    CREATE TABLE documents (
      id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
      source_uri TEXT NOT NULL, display_name TEXT NOT NULL, mime_type TEXT NOT NULL,
      content_hash TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      sensitivity_label TEXT NOT NULL CHECK(sensitivity_label IN ('public','internal','sensitive','restricted')),
      active_version INTEGER, ingestion_status TEXT NOT NULL,
      deleted_at TEXT, cleanup_status TEXT NOT NULL DEFAULT 'clean',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(source_id, room_id)
    );
    CREATE TABLE document_versions (
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      version INTEGER NOT NULL, content_hash TEXT NOT NULL, status TEXT NOT NULL,
      embedding_model TEXT, embedding_dimensions INTEGER, expected_chunks INTEGER NOT NULL DEFAULT 0,
      failure_code TEXT, created_at TEXT NOT NULL, activated_at TEXT,
      PRIMARY KEY(document_id, version)
    );
    CREATE TABLE document_chunks (
      id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version INTEGER NOT NULL,
      chunk_index INTEGER NOT NULL, text_content TEXT NOT NULL, source_location TEXT NOT NULL,
      token_estimate INTEGER NOT NULL, content_hash TEXT NOT NULL,
      room_id TEXT NOT NULL REFERENCES rooms(id),
      sensitivity_label TEXT NOT NULL CHECK(sensitivity_label IN ('public','internal','sensitive','restricted')),
      created_at TEXT NOT NULL,
      FOREIGN KEY(document_id,version) REFERENCES document_versions(document_id,version) ON DELETE CASCADE,
      UNIQUE(document_id,version,chunk_index)
    );
    CREATE INDEX document_chunks_document ON document_chunks(document_id,version);
    CREATE TABLE memory_index_state (
      singleton INTEGER PRIMARY KEY CHECK(singleton=1), model TEXT NOT NULL,
      dimensions INTEGER NOT NULL, needs_reindex INTEGER NOT NULL DEFAULT 0 CHECK(needs_reindex IN (0,1))
    );
    CREATE TABLE memory_index_jobs (
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      version INTEGER NOT NULL, operation TEXT NOT NULL CHECK(operation IN ('upsert','delete')),
      status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error_code TEXT,
      updated_at TEXT NOT NULL, PRIMARY KEY(document_id,version,operation)
    );
    """),
    (4, """
    ALTER TABLE reminders ADD COLUMN generation INTEGER NOT NULL DEFAULT 1 CHECK(generation > 0);
    CREATE TABLE jobs (
      id TEXT PRIMARY KEY, job_type TEXT NOT NULL, payload_json TEXT NOT NULL,
      idempotency_key TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL CHECK(status IN ('queued','running','retry_wait','succeeded','failed','cancelled')),
      attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0), max_attempts INTEGER NOT NULL CHECK(max_attempts BETWEEN 1 AND 5),
      available_at TEXT NOT NULL, lease_owner TEXT, lease_expires_at TEXT,
      error_class TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      started_at TEXT, finished_at TEXT, cancelled_at TEXT,
      CHECK ((status='running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) OR status!='running')
    );
    CREATE INDEX jobs_eligible ON jobs(status, available_at);
    CREATE INDEX jobs_lease_expiry ON jobs(status, lease_expires_at);
    CREATE TABLE approvals (
      id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, persona_id TEXT NOT NULL,
      action_type TEXT NOT NULL, risk_tier TEXT NOT NULL, resource_id TEXT NOT NULL,
      room_id TEXT NOT NULL, destination TEXT, arguments_json TEXT NOT NULL,
      arguments_hash TEXT NOT NULL, policy_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','expired','revoked','invalidated','consumed')),
      created_at TEXT NOT NULL, expires_at TEXT NOT NULL, decided_at TEXT,
      decided_by TEXT, decision_reason TEXT, consumed_at TEXT,
      CHECK ((status='consumed' AND consumed_at IS NOT NULL) OR status!='consumed')
    );
    CREATE INDEX approvals_pending ON approvals(status, expires_at);
    CREATE TABLE runtime_controls (
      singleton INTEGER PRIMARY KEY CHECK(singleton=1), paused INTEGER NOT NULL CHECK(paused IN (0,1)),
      killed INTEGER NOT NULL CHECK(killed IN (0,1)), updated_at TEXT NOT NULL, updated_by TEXT NOT NULL
    );
    INSERT INTO runtime_controls VALUES (1,0,0,'1970-01-01T00:00:00Z','system');
    """),
    (5, """
    CREATE TABLE desktop_workspaces (
      id TEXT PRIMARY KEY, purpose TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      status TEXT NOT NULL CHECK(status IN ('active','unavailable','cleaned')),
      layout_json TEXT NOT NULL, previous_layout_json TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE desktop_slots (
      id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES desktop_workspaces(id) ON DELETE CASCADE,
      slot_name TEXT NOT NULL CHECK(slot_name IN ('nw','ne','sw','se')),
      purpose TEXT NOT NULL, app_identity TEXT, requested_url TEXT, current_location TEXT,
      bounds_json TEXT, focused INTEGER NOT NULL DEFAULT 0 CHECK(focused IN (0,1)),
      ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN (0,1)),
      status TEXT NOT NULL CHECK(status IN ('active','unavailable','awaiting_user')),
      last_screenshot_id TEXT, UNIQUE(workspace_id, slot_name)
    );
    CREATE TABLE desktop_runs (
      id TEXT PRIMARY KEY, workspace_id TEXT REFERENCES desktop_workspaces(id),
      job_id TEXT, session_id TEXT NOT NULL, persona_id TEXT NOT NULL REFERENCES personas(id),
      room_id TEXT NOT NULL REFERENCES rooms(id),
      status TEXT NOT NULL CHECK(status IN ('queued','running','paused','awaiting_approval','cancelled','failed','succeeded')),
      permissions_json TEXT NOT NULL, domain_scope_json TEXT NOT NULL, deadline_at TEXT NOT NULL,
      cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX desktop_runs_status ON desktop_runs(status, updated_at);
    CREATE TABLE desktop_events (
      id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES desktop_runs(id) ON DELETE CASCADE,
      sequence INTEGER NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
      safe_payload_json TEXT NOT NULL, UNIQUE(run_id, sequence)
    );
    CREATE TABLE desktop_screenshots (
      id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES desktop_runs(id) ON DELETE CASCADE,
      slot_name TEXT, path TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
      scale REAL NOT NULL, captured_at TEXT NOT NULL, expires_at TEXT NOT NULL
    );
    CREATE TABLE desktop_run_plans (
      run_id TEXT PRIMARY KEY REFERENCES desktop_runs(id) ON DELETE CASCADE,
      plan_json TEXT NOT NULL
    );
    CREATE TABLE ai_loops (
      id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms(id),
      persona_id TEXT NOT NULL REFERENCES personas(id), goal TEXT NOT NULL,
      constraints_json TEXT NOT NULL, provider_mode TEXT NOT NULL,
      cloud_opt_in INTEGER NOT NULL DEFAULT 0 CHECK(cloud_opt_in IN (0,1)),
      status TEXT NOT NULL CHECK(status IN ('created','debating','awaiting_user','synthesized','imported','declined','cancelled','failed')),
      max_rounds INTEGER NOT NULL CHECK(max_rounds BETWEEN 3 AND 12),
      job_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled_at TEXT
    );
    CREATE TABLE loop_rounds (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      round_index INTEGER NOT NULL, stage TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
      summary TEXT NOT NULL DEFAULT '', output_json TEXT NOT NULL DEFAULT '{}',
      job_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(loop_id, round_index)
    );
    CREATE TABLE loop_artifacts (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      artifact_type TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE loop_handoffs (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      provider_mode TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('awaiting_user','imported','declined','cancelled')),
      compiled_prompt TEXT NOT NULL, imported_text TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE loop_nodes (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      node_type TEXT NOT NULL, display_name TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      sensitivity_label TEXT NOT NULL CHECK(sensitivity_label IN ('public','internal','sensitive','restricted')),
      content TEXT NOT NULL, provenance_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE loop_edges (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      source_node_id TEXT NOT NULL REFERENCES loop_nodes(id),
      relation_type TEXT NOT NULL CHECK(relation_type IN ('supports','contradicts','refines','derived_from','resolves')),
      target_node_id TEXT NOT NULL REFERENCES loop_nodes(id),
      room_id TEXT NOT NULL REFERENCES rooms(id),
      sensitivity_label TEXT NOT NULL CHECK(sensitivity_label IN ('public','internal','sensitive','restricted')),
      created_at TEXT NOT NULL
    );
    CREATE INDEX loop_edges_loop ON loop_edges(loop_id, source_node_id, target_node_id);
    CREATE TABLE loop_sources (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      display_name TEXT NOT NULL, trust_label TEXT NOT NULL, content TEXT NOT NULL,
      ingested INTEGER NOT NULL DEFAULT 0 CHECK(ingested IN (0,1)), created_at TEXT NOT NULL
    );
    CREATE TABLE local_api_sessions (
      id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, origin_allowlist_json TEXT NOT NULL,
      created_at TEXT NOT NULL, expires_at TEXT NOT NULL
    );
    """),
    (6, """
    CREATE TABLE IF NOT EXISTS loop_roles (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      role_name TEXT NOT NULL CHECK(role_name IN ('red_team','blue_team','judge','unbiased_reviewer')),
      role_label TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','active','complete','cancelled')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(loop_id, role_name)
    );
    """),
    (7, """
    ALTER TABLE loop_rounds ADD COLUMN role_name TEXT;
    ALTER TABLE loop_rounds ADD COLUMN input_json TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE loop_rounds ADD COLUMN provider_id TEXT;
    ALTER TABLE loop_rounds ADD COLUMN model_id TEXT;
    ALTER TABLE loop_rounds ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0);
    ALTER TABLE loop_rounds ADD COLUMN error_class TEXT;

    CREATE TABLE loop_execution_state (
      loop_id TEXT PRIMARY KEY REFERENCES ai_loops(id) ON DELETE CASCADE,
      status TEXT NOT NULL CHECK(status IN
        ('waiting','running','succeeded','failed','cancelled','review_required')),
      current_role TEXT,
      current_round INTEGER,
      pending_json TEXT NOT NULL,
      invocation_count INTEGER NOT NULL DEFAULT 0 CHECK(invocation_count >= 0),
      review_verdict TEXT CHECK(review_verdict IN ('pass','revise','insufficient_evidence')),
      final_synthesis TEXT,
      error_class TEXT,
      worker_id TEXT,
      lease_expires_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      CHECK ((status='running' AND worker_id IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR status!='running')
    );
    CREATE INDEX loop_execution_lease ON loop_execution_state(status, lease_expires_at);

    CREATE TABLE loop_roles_v7 (
      id TEXT PRIMARY KEY, loop_id TEXT NOT NULL REFERENCES ai_loops(id) ON DELETE CASCADE,
      role_name TEXT NOT NULL CHECK(role_name IN ('red_team','blue_team','judge','unbiased_reviewer')),
      role_label TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('pending','running','succeeded','failed','cancelled')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(loop_id, role_name)
    );
    INSERT INTO loop_roles_v7(id,loop_id,role_name,role_label,status,created_at,updated_at)
      SELECT id,loop_id,role_name,role_label,
        CASE status WHEN 'complete' THEN 'succeeded' WHEN 'active' THEN 'pending' ELSE status END,
        created_at,updated_at FROM loop_roles;
    DROP TABLE loop_roles;
    ALTER TABLE loop_roles_v7 RENAME TO loop_roles;

    INSERT INTO loop_execution_state
      (loop_id,status,current_role,current_round,pending_json,invocation_count,review_verdict,
       final_synthesis,error_class,worker_id,lease_expires_at,created_at,updated_at)
      SELECT l.id,
        CASE
          WHEN l.status='cancelled' THEN 'cancelled'
          WHEN l.status='failed' THEN 'failed'
          WHEN l.status='created' AND NOT EXISTS
            (SELECT 1 FROM loop_rounds r WHERE r.loop_id=l.id) THEN 'waiting'
          ELSE 'review_required'
        END,
        NULL,NULL,
        CASE
          WHEN l.status='created' AND NOT EXISTS
            (SELECT 1 FROM loop_rounds r WHERE r.loop_id=l.id)
          THEN '[{\"role\":\"blue_team\",\"stage\":\"propose\"},{\"role\":\"red_team\",\"stage\":\"challenge\"},{\"role\":\"judge\",\"stage\":\"synthesize\"},{\"role\":\"unbiased_reviewer\",\"stage\":\"audit\"}]'
          ELSE '[]'
        END,
        0,NULL,NULL,
        CASE
          WHEN l.status='created' AND NOT EXISTS
            (SELECT 1 FROM loop_rounds r WHERE r.loop_id=l.id) THEN NULL
          WHEN l.status IN ('cancelled','failed') THEN 'legacy_terminal_state'
          ELSE 'legacy_execution_not_resumable'
        END,
        NULL,NULL,l.created_at,l.updated_at
      FROM ai_loops l;
    UPDATE loop_execution_state SET status='review_required',pending_json='[]',
      error_class='legacy_budget_below_minimum'
      WHERE status='waiting' AND loop_id IN (SELECT id FROM ai_loops WHERE max_rounds < 4);
    """),
    (8, """
    CREATE TABLE conversations (
      id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      title TEXT NOT NULL, memory_enabled INTEGER NOT NULL DEFAULT 0 CHECK(memory_enabled IN (0,1)),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
    );
    CREATE INDEX conversations_principal_updated ON conversations(principal_id, updated_at DESC);
    CREATE TABLE conversation_messages (
      id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      sender TEXT NOT NULL CHECK(sender IN ('user','assistant')), content TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('complete','inference_failed','cancelled')),
      provider_id TEXT, model_id TEXT, retrieved_memory_json TEXT NOT NULL DEFAULT '[]',
      created_at TEXT NOT NULL
    );
    CREATE INDEX conversation_messages_order ON conversation_messages(conversation_id, created_at, id);
    """),
    (9, """
    ALTER TABLE conversation_messages ADD COLUMN memory_status TEXT NOT NULL DEFAULT 'not_indexed';
    CREATE TABLE conversation_memory_sources (
      user_message_id TEXT PRIMARY KEY REFERENCES conversation_messages(id) ON DELETE CASCADE,
      assistant_message_id TEXT NOT NULL REFERENCES conversation_messages(id) ON DELETE CASCADE,
      conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      document_id TEXT REFERENCES documents(id),
      status TEXT NOT NULL CHECK(status IN ('pending','indexed','excluded','failed')),
      error_code TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX conversation_memory_status ON conversation_memory_sources(status, updated_at);
    """),
    (10, """
    ALTER TABLE conversation_messages ADD COLUMN client_request_id TEXT;
    CREATE UNIQUE INDEX conversation_message_idempotency ON conversation_messages(conversation_id, client_request_id)
      WHERE client_request_id IS NOT NULL;
    UPDATE conversations SET memory_enabled=1;
    """),
    (11, """
    CREATE TABLE projects (
      id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL CHECK(status IN ('active','planning','completed','on_hold')),
      milestones_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX projects_principal_room ON projects(principal_id, room_id, updated_at DESC);
    CREATE TABLE calendar_events (
      id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id),
      title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', starts_at TEXT NOT NULL, ends_at TEXT,
      timezone TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('scheduled','cancelled')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      CHECK(ends_at IS NULL OR ends_at > starts_at)
    );
    CREATE INDEX calendar_events_principal_start ON calendar_events(principal_id, starts_at);
    CREATE TABLE local_settings (
      principal_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    """),
    (12, """
    ALTER TABLE local_api_sessions ADD COLUMN pairing_expires_at TEXT;
    UPDATE local_api_sessions SET pairing_expires_at=created_at;
    """),
)


class Database:
    """Short-lived SQLite connection provider; each operation gets a fresh connection."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        if str(self.path) != ":memory:":
            os.chmod(self.path, 0o600)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        from .bootstrap import seed_trusted_state
        from .models import utc_now

        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            if current > max((version for version, _ in MIGRATIONS), default=0):
                raise sqlite3.DatabaseError("Database schema version is newer than this application")
            for version, sql in MIGRATIONS:
                if version > current:
                    self._execute_statements(connection, sql)
                    if version == 2:
                        self._backfill_legacy_idempotency(connection)
                    connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", (version, utc_now()))
            seed_trusted_state(connection)

    @staticmethod
    def _execute_statements(connection: sqlite3.Connection, script: str) -> None:
        statement = ""
        for line in script.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                if statement.strip():
                    connection.execute(statement)
                statement = ""
        if statement.strip():
            raise sqlite3.ProgrammingError("Incomplete SQL migration statement")

    @staticmethod
    def _backfill_legacy_idempotency(connection: sqlite3.Connection) -> None:
        rows = connection.execute("""SELECT id,persona_owner,idempotency_key,title,description,item_type,status,priority,
            category_id,project_id,room_id,due_date,due_at,timezone,source_text,created_at FROM tasks WHERE idempotency_key IS NOT NULL""").fetchall()
        for row in rows:
            if row["persona_owner"] is None:
                continue
            fields = {"title": row["title"], "description": row["description"], "item_type": row["item_type"],
                "status": row["status"], "priority": row["priority"], "category_id": row["category_id"],
                "room_id": row["room_id"], "due_date": row["due_date"], "due_at": row["due_at"],
                "timezone": row["timezone"], "source_text": row["source_text"]}
            if row["project_id"] is not None:
                fields["project_id"] = row["project_id"]
            encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            fingerprint = hashlib.sha256(encoded).hexdigest()
            connection.execute("""INSERT INTO task_idempotency_keys
                (principal_id,persona_id,idempotency_key,request_fingerprint,task_id,created_at)
                VALUES ('local-user',?,?,?,?,?)""",
                (row["persona_owner"],row["idempotency_key"],fingerprint,row["id"],row["created_at"]))

    def integrity_check(self) -> str:
        with self.connect() as connection:
            return connection.execute("PRAGMA integrity_check").fetchone()[0]
