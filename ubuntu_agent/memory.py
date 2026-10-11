"""Local, SQLite-authoritative document memory with policy-checked vector retrieval."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib import request

from .bootstrap import PERSONAS as TRUSTED_PERSONAS, PRINCIPAL_ID, ROOMS as TRUSTED_ROOMS
from .models import AccessContext, Actor, DecisionKind, RiskTier, utc_now
from .policy import PolicyEngine

MAX_DOCUMENT_BYTES = 1_000_000
CHUNK_CHARS = 1600
OVERLAP_CHARS = 160
SUPPORTED = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain"}


class MemoryError(RuntimeError):
    code = "MEMORY_ERROR"


class MemoryUnavailableError(MemoryError):
    code = "MEMORY_UNAVAILABLE"


class MemoryValidationError(MemoryError):
    code = "MEMORY_VALIDATION_ERROR"


class MemoryDeniedError(MemoryError):
    code = "MEMORY_DENIED"


class EmbeddingError(MemoryUnavailableError):
    pass


class VectorStore(Protocol):
    def upsert(self, points: list[dict]) -> None: ...
    def contains(self, point_ids: list[str]) -> list[str]: ...
    def search(self, vector: list[float], *, room_ids: list[str], limit: int) -> list[tuple[str, float]]: ...
    def delete(self, point_ids: list[str]) -> None: ...


class EmbeddingAdapter:
    def __init__(self, endpoint: str | None = None, model: str | None = None, timeout: float | None = None,
                 transport=None, dimensions: int | None = None):
        self.endpoint = (endpoint or os.getenv("UBUNTU_AGENT_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("UBUNTU_AGENT_EMBEDDING_MODEL", "embeddinggemma")
        self.timeout = float(timeout if timeout is not None else os.getenv("UBUNTU_AGENT_EMBEDDING_TIMEOUT", "30"))
        self.dimensions = int(dimensions if dimensions is not None else
                              os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768"))
        self.transport = transport or self._http

    @staticmethod
    def _http(req, timeout):
        with request.urlopen(req, timeout=timeout) as response:
            return response.read()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text for text in texts):
            raise MemoryValidationError("Embedding input is invalid.")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 32):
            body = json.dumps({"model": self.model, "input": texts[start:start + 32]}).encode()
            req = request.Request(f"{self.endpoint}/api/embed", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
            try:
                payload = json.loads(self.transport(req, self.timeout))
            except Exception as exc:
                raise EmbeddingError("Ollama embedding request failed.") from exc
            batch = payload.get("embeddings") if isinstance(payload, dict) else None
            if not isinstance(batch, list) or len(batch) != len(texts[start:start + 32]):
                raise EmbeddingError("Ollama returned an invalid embeddings response.")
            for vector in batch:
                if (not isinstance(vector, list) or not vector or
                        any(not isinstance(value, (float, int)) or isinstance(value, bool) or
                            not math.isfinite(value) for value in vector)):
                    raise EmbeddingError("Ollama returned an invalid embedding vector.")
                if len(vector) != self.dimensions:
                    raise EmbeddingError("Ollama embedding dimension does not match the configured dimension.")
                vectors.append([float(value) for value in vector])
        dimensions = len(vectors[0])
        if dimensions != self.dimensions or any(len(vector) != dimensions for vector in vectors):
            raise EmbeddingError("Ollama embedding dimension does not match the configured dimension.")
        return vectors


class QdrantLocalStore:
    """Persistent embedded Qdrant. Import the optional SDK only when memory is used."""
    def __init__(self, path: str | Path, dimensions: int):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path, 0o700)
        self.dimensions = dimensions
        import fcntl
        self._lock_file = (self.path / ".ubuntu-agent.lock").open("a+")
        os.chmod(self.path / ".ubuntu-agent.lock", 0o600)
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_file.close()
            raise MemoryUnavailableError("Local vector storage is already open by another application instance.") from exc
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise MemoryUnavailableError("Optional RAG dependencies are not installed.") from exc
        self._models = models
        try:
            self.client = QdrantClient(path=str(self.path))
            names = {collection.name for collection in self.client.get_collections().collections}
            if "ubuntu_memory" not in names:
                self.client.create_collection("ubuntu_memory", vectors_config=models.VectorParams(
                    size=dimensions, distance=models.Distance.COSINE))
            else:
                info = self.client.get_collection("ubuntu_memory")
                current = info.config.params.vectors.size
                if current != dimensions:
                    self.dimensions = current
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError("Local vector index is unavailable.") from exc

    def upsert(self, points: list[dict]) -> None:
        try:
            self.client.upsert("ubuntu_memory", points=[self._models.PointStruct(
                id=item["id"], vector=item["vector"], payload=item["payload"]) for item in points], wait=True)
        except Exception as exc:
            raise MemoryUnavailableError("Local vector index write failed.") from exc

    def contains(self, point_ids: list[str]) -> list[str]:
        try:
            found = self.client.retrieve("ubuntu_memory", ids=point_ids, with_payload=False, with_vectors=False)
            return [str(point.id) for point in found]
        except Exception as exc:
            raise MemoryUnavailableError("Local vector index verification failed.") from exc

    def search(self, vector: list[float], *, room_ids: list[str], limit: int) -> list[tuple[str, float]]:
        try:
            f = self._models.Filter(must=[self._models.FieldCondition(key="room_id", match=self._models.MatchAny(any=room_ids))])
            found = self.client.query_points("ubuntu_memory", query=vector, query_filter=f, limit=limit).points
            return [(str(item.id), float(item.score)) for item in found]
        except Exception as exc:
            raise MemoryUnavailableError("Local vector search is unavailable.") from exc

    def delete(self, point_ids: list[str]) -> None:
        if point_ids:
            try:
                self.client.delete("ubuntu_memory", points_selector=self._models.PointIdsList(points=point_ids), wait=True)
            except Exception as exc:
                raise MemoryUnavailableError("Local vector cleanup failed.") from exc

    def reset(self, dimensions: int) -> None:
        try:
            self.client.delete_collection("ubuntu_memory")
            self.client.create_collection("ubuntu_memory", vectors_config=self._models.VectorParams(
                size=dimensions, distance=self._models.Distance.COSINE))
            self.dimensions = dimensions
        except Exception as exc:
            raise MemoryUnavailableError("Local vector index could not be prepared for explicit reindex.") from exc


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    start: int
    end: int
    heading: str | None


def deterministic_chunks(text: str) -> list[Chunk]:
    """Split at paragraphs/headings, then bounded character windows with stable source offsets."""
    if not text.strip():
        raise MemoryValidationError("Document is empty.")
    chunks: list[Chunk] = []
    heading: str | None = None
    cursor = 0
    current: list[tuple[int, int, str]] = []
    current_size = 0

    def flush():
        nonlocal current, current_size
        if not current:
            return
        raw_start, raw_end = current[0][0], current[-1][1]
        value = "\n\n".join(part for _, _, part in current).strip()
        if value:
            chunks.append(Chunk(value, len(chunks), raw_start, raw_end, heading))
        current, current_size = [], 0

    for paragraph in text.split("\n\n"):
        start = text.find(paragraph, cursor)
        if start < 0:
            continue
        end = start + len(paragraph)
        cursor = end
        stripped = paragraph.strip()
        if stripped.startswith("#"):
            flush()
            heading = stripped.lstrip("#").strip()[:200] or None
        if len(stripped) > CHUNK_CHARS:
            flush()
            step = CHUNK_CHARS - OVERLAP_CHARS
            for pos in range(0, len(stripped), step):
                part = stripped[pos:pos + CHUNK_CHARS]
                chunks.append(Chunk(part, len(chunks), start + pos, min(end, start + pos + len(part)), heading))
            continue
        if current_size + len(stripped) > CHUNK_CHARS:
            flush()
        if stripped:
            current.append((start, end, stripped))
            current_size += len(stripped)
    flush()
    return chunks


def _stable_chunk_id(document_id: str, version: int, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ubuntu-agent:{document_id}:{version}:{index}"))


class MemoryService:
    def __init__(self, database, embedder=None, vector_store=None, policy=None, *, data_dir=None,
                 max_document_bytes: int = MAX_DOCUMENT_BYTES):
        self.db = database
        self.policy = policy or PolicyEngine()
        self.embedder = embedder or EmbeddingAdapter()
        root = Path(data_dir) if data_dir else database.path.parent
        self.vector_store = vector_store or QdrantLocalStore(
            root / "qdrant", dimensions=int(os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768")))
        self.max_document_bytes = max_document_bytes

    def _embed(self, texts):
        try:
            vectors = self.embedder.embed(texts)
        except MemoryError:
            raise
        except Exception as exc:
            raise EmbeddingError("Local embedding service request failed.") from exc
        expected = getattr(self.vector_store, "dimensions", None)
        if expected is None:
            expected = getattr(self.embedder, "dimensions", None)
        if expected is None:
            expected = int(os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768"))
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingError("Local embedding service returned an invalid vector count.")
        for vector in vectors:
            if (not isinstance(vector, list) or not vector or
                    any(not isinstance(value, (float, int)) or isinstance(value, bool) or
                        not math.isfinite(value) for value in vector)):
                raise EmbeddingError("Local embedding service returned an invalid vector.")
            if len(vector) != expected:
                raise EmbeddingError("Local embedding dimension does not match the configured dimension.")
        return [[float(value) for value in vector] for vector in vectors]

    def _upsert(self, points):
        try:
            self.vector_store.upsert(points)
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError("Local vector index write failed.") from exc

    def _search_vectors(self, vector, room_ids, limit):
        try:
            return self.vector_store.search(vector, room_ids=room_ids, limit=limit)
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError("Local vector search is unavailable.") from exc

    def _verify_vectors(self, point_ids):
        try:
            present = set(self.vector_store.contains(point_ids))
        except Exception as exc:
            if isinstance(exc, MemoryError):
                raise
            raise MemoryUnavailableError("Local vector index verification failed.") from exc
        if present != set(point_ids):
            raise MemoryUnavailableError("Local vector index did not confirm all chunks.")

    def _delete_vectors(self, ids):
        try:
            self.vector_store.delete(ids)
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError("Local vector cleanup failed.") from exc

    def _check_embedding_state(self, dimensions: int):
        with self.db.connect() as conn:
            state = conn.execute("SELECT * FROM memory_index_state WHERE singleton=1").fetchone()
        if state and (state["needs_reindex"] or state["model"] != self.embedder.model or state["dimensions"] != dimensions):
            raise MemoryValidationError("Embedding model or dimensions changed; explicit reindex is required.")

    def _authorize(self, actor: Actor, room_id: str | None, sensitivity: str | None, action: str, resource: str):
        if (not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID or
                not isinstance(actor.persona_id, str) or actor.persona_id not in TRUSTED_PERSONAS or
                not isinstance(room_id, str) or room_id not in TRUSTED_ROOMS or
                not isinstance(sensitivity, str) or not sensitivity):
            raise MemoryDeniedError("Memory access denied.")
        expected_name, expected_purpose, expected_profile = TRUSTED_PERSONAS[actor.persona_id]
        expected_room_name, expected_sensitivity = TRUSTED_ROOMS[room_id]
        with self.db.connect() as conn:
            persona = conn.execute("SELECT name,purpose,policy_profile_id,is_enabled FROM personas WHERE id=?",
                                   (actor.persona_id,)).fetchone()
            room = conn.execute("SELECT name,sensitivity_default,storage_policy,retention_policy FROM rooms WHERE id=?",
                                (room_id,)).fetchone()
        if (not persona or tuple(persona[key] for key in ("name", "purpose", "policy_profile_id", "is_enabled")) !=
                (expected_name, expected_purpose, expected_profile, 1) or not room or
                tuple(room[key] for key in ("name", "sensitivity_default", "storage_policy", "retention_policy")) !=
                (expected_room_name, expected_sensitivity, "local", "user_managed") or
                sensitivity not in {"public", "internal", "sensitive", "restricted"}):
            raise MemoryDeniedError("Memory access denied.")
        risk = "read" if action == "memory.search" else "prepare"
        try:
            context = AccessContext(actor.principal_id, actor.persona_id, None, room_id, resource, action,
                                    sensitivity, "local", risk, "normal")
            decision = self.policy.evaluate_access(context)
        except Exception as exc:
            raise MemoryDeniedError("Memory access denied.") from exc
        if decision.decision != DecisionKind.ALLOW:
            raise MemoryDeniedError("Memory access denied.")

    def _trusted_room(self, room_id: str | None, actor: Actor, action: str, resource: str):
        if not room_id:
            raise MemoryDeniedError("Memory access denied.")
        with self.db.connect() as conn:
            room = conn.execute("SELECT id,sensitivity_default FROM rooms WHERE id=?", (room_id,)).fetchone()
        if room is None:
            raise MemoryDeniedError("Memory access denied.")
        self._authorize(actor, room["id"], room["sensitivity_default"], action, resource)
        return room["id"], room["sensitivity_default"]

    def ingest_document(self, path: str | Path, actor: Actor, room_id: str, *, sensitivity: str | None = None):
        source_path = Path(path).expanduser()
        canonical = str(source_path.resolve(strict=False))
        room, label = self._trusted_room(room_id, actor, "memory.ingest", canonical)
        if sensitivity is not None and sensitivity != label:
            raise MemoryDeniedError("Memory access denied.")
        if source_path.is_symlink() or source_path.suffix.lower() not in SUPPORTED:
            raise MemoryValidationError("Only explicitly selected Markdown and plain-text files are supported.")
        try:
            stat = source_path.stat()
            if not source_path.is_file() or stat.st_size <= 0 or stat.st_size > self.max_document_bytes:
                raise MemoryValidationError("Document is empty or exceeds the configured size limit.")
            raw = source_path.read_bytes()
            text = raw.decode("utf-8", errors="strict")
        except MemoryError:
            raise
        except (OSError, UnicodeError) as exc:
            raise MemoryValidationError("Document cannot be read as valid UTF-8.") from exc
        digest = hashlib.sha256(raw).hexdigest()
        chunks = deterministic_chunks(text)
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"source:{canonical}"))
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"document:{source_id}:{room}"))
        now = utc_now()
        with self.db.connect() as conn:
            doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if doc and doc["deleted_at"]:
                raise MemoryDeniedError("Memory access denied.")
            if doc and doc["content_hash"] == digest and doc["ingestion_status"] == "ready":
                return {"document_id": document_id, "version": doc["active_version"], "status": "ready", "unchanged": True}
            version = (conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM document_versions WHERE document_id=?",
                                     (document_id,)).fetchone()[0])
            conn.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?)",
                         (source_id, "local_file", canonical, source_path.name, "user_selected", now,
                          json.dumps({"mime_type": SUPPORTED[source_path.suffix.lower()]}), now))
            conn.execute("""INSERT INTO documents(id,source_id,source_uri,display_name,mime_type,content_hash,room_id,
                         sensitivity_label,active_version,ingestion_status,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,NULL,'indexing',?,?) ON CONFLICT(id) DO UPDATE SET
                         ingestion_status='indexing',content_hash=excluded.content_hash,updated_at=excluded.updated_at""",
                         (document_id, source_id, canonical, source_path.name, SUPPORTED[source_path.suffix.lower()],
                          digest, room, label, now, now))
            model = self.embedder.model
            expected_dims = conn.execute("SELECT dimensions FROM memory_index_state WHERE singleton=1").fetchone()
            if expected_dims and expected_dims[0] <= 0:
                raise MemoryValidationError("Embedding configuration requires explicit reindex.")
            conn.execute("INSERT INTO document_versions VALUES(?,?,?,?,?,?,?,NULL,?,NULL)",
                         (document_id, version, digest, "indexing", model, expected_dims[0] if expected_dims else None,
                          len(chunks), now))
            conn.executemany("INSERT INTO document_chunks VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
                (_stable_chunk_id(document_id, version, chunk.index), document_id, version, chunk.index,
                 chunk.text, json.dumps({"start": chunk.start, "end": chunk.end, "line_start": text.count("\n", 0, chunk.start)+1,
                                        "line_end": text.count("\n", 0, chunk.end)+1, "heading": chunk.heading}),
                 max(1, len(chunk.text.split())), hashlib.sha256(chunk.text.encode()).hexdigest(), room, label, now)
                for chunk in chunks])
            conn.execute("INSERT OR REPLACE INTO memory_index_jobs VALUES(?,?, 'upsert','pending',0,NULL,?)",
                         (document_id, version, now))
        try:
            vectors = self._embed([chunk.text for chunk in chunks])
            dimensions = len(vectors[0])
            try:
                self._check_embedding_state(dimensions)
            except MemoryValidationError:
                with self.db.connect() as conn:
                    conn.execute("UPDATE memory_index_state SET needs_reindex=1 WHERE singleton=1")
                raise
            point_ids = [_stable_chunk_id(document_id, version, chunk.index) for chunk in chunks]
            self._upsert([{"id": point_id, "vector": vector,
                                      "payload": {"room_id": room, "document_id": document_id,
                                                  "document_version": version, "chunk_index": chunk.index}}
                                     for chunk, vector, point_id in zip(chunks, vectors, point_ids, strict=True)])
            self._verify_vectors(point_ids)
        except Exception as exc:
            with self.db.connect() as conn:
                conn.execute("UPDATE document_versions SET status='failed',failure_code=? WHERE document_id=? AND version=?",
                             (getattr(exc, "code", "INDEX_FAILED"), document_id, version))
                conn.execute("UPDATE documents SET ingestion_status=CASE WHEN active_version IS NULL THEN 'failed' ELSE 'ready' END WHERE id=?",
                             (document_id,))
                conn.execute("UPDATE memory_index_jobs SET status='pending',attempts=attempts+1,last_error_code=?,updated_at=? WHERE document_id=? AND version=?",
                             (getattr(exc, "code", "INDEX_FAILED"), utc_now(), document_id, version))
            raise
        with self.db.connect() as conn:
            conn.execute("INSERT INTO memory_index_state VALUES(1,?,?,0) ON CONFLICT(singleton) DO NOTHING",
                         (self.embedder.model, dimensions))
            previous = conn.execute("SELECT active_version FROM documents WHERE id=?", (document_id,)).fetchone()[0]
            conn.execute("UPDATE document_versions SET status='active',activated_at=? WHERE document_id=? AND version=?",
                         (utc_now(), document_id, version))
            cleanup = "ready" if previous is None else "cleanup_pending"
            conn.execute("UPDATE documents SET active_version=?,ingestion_status=?,cleanup_status='clean',updated_at=? WHERE id=?",
                         (version, cleanup, utc_now(), document_id))
            conn.execute("UPDATE memory_index_jobs SET status='done',updated_at=? WHERE document_id=? AND version=? AND operation='upsert'",
                         (utc_now(), document_id, version))
            if previous is not None:
                conn.execute("INSERT OR REPLACE INTO memory_index_jobs VALUES(?,?, 'delete','pending',0,NULL,?)",
                             (document_id, previous, utc_now()))
        if previous is not None:
            self._cleanup_version(document_id, previous)
        return {"document_id": document_id, "version": version, "status": "ready"}

    def update_document(self, path: str | Path, actor: Actor, room_id: str, **kwargs):
        return self.ingest_document(path, actor, room_id, **kwargs)

    def _cleanup_version(self, document_id: str, version: int):
        with self.db.connect() as conn:
            ids = [row[0] for row in conn.execute("SELECT id FROM document_chunks WHERE document_id=? AND version=?", (document_id, version))]
        try:
            self._delete_vectors(ids)
            if ids and hasattr(self.vector_store, "contains") and set(self.vector_store.contains(ids)):
                raise MemoryUnavailableError("Local vector cleanup could not be verified.")
            with self.db.connect() as conn:
                conn.execute("DELETE FROM document_versions WHERE document_id=? AND version=?", (document_id, version))
                conn.execute("UPDATE memory_index_jobs SET status='done',updated_at=? WHERE document_id=? AND version=? AND operation='delete'",
                             (utc_now(), document_id, version))
                conn.execute("UPDATE documents SET ingestion_status='ready',updated_at=? WHERE id=? AND ingestion_status='cleanup_pending'",
                             (utc_now(), document_id))
        except Exception as exc:
            with self.db.connect() as conn:
                conn.execute("UPDATE memory_index_jobs SET status='pending',attempts=attempts+1,last_error_code=?,updated_at=? WHERE document_id=? AND version=? AND operation='delete'",
                             (getattr(exc, "code", "INDEX_CLEANUP_FAILED"), utc_now(), document_id, version))

    def delete_document(self, document_id: str, actor: Actor):
        with self.db.connect() as conn:
            doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if doc is None:
                raise MemoryDeniedError("Memory access denied.")
            self._authorize(actor, doc["room_id"], doc["sensitivity_label"], "memory.delete", document_id)
            conn.execute("UPDATE documents SET deleted_at=?,ingestion_status='deleted',updated_at=?,cleanup_status='pending' WHERE id=?",
                         (utc_now(), utc_now(), document_id))
            conn.execute("INSERT OR REPLACE INTO memory_index_jobs VALUES(?,?, 'delete','pending',0,NULL,?)",
                         (document_id, doc["active_version"] or 0, utc_now()))
            versions = [row[0] for row in conn.execute("SELECT version FROM document_versions WHERE document_id=?", (document_id,))]
        try:
            for version in versions:
                self._cleanup_version(document_id, version)
        except MemoryError:
            pass
        return {"document_id": document_id, "status": "deleted"}

    def reconcile_memory_index(self, *, limit: int = 20):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise MemoryValidationError("Reconciliation limit is invalid.")
        with self.db.connect() as conn:
            jobs = [dict(row) for row in conn.execute("SELECT * FROM memory_index_jobs WHERE status='pending' ORDER BY updated_at LIMIT ?", (limit,))]
        completed = 0
        for job in jobs:
            if job["operation"] == "delete":
                self._cleanup_version(job["document_id"], job["version"])
                with self.db.connect() as conn:
                    state = conn.execute("SELECT status FROM memory_index_jobs WHERE document_id=? AND version=? AND operation='delete'",
                                         (job["document_id"], job["version"])).fetchone()
                completed += bool(state and state[0] == "done")
            else:
                with self.db.connect() as conn:
                    rows = conn.execute("SELECT * FROM document_chunks WHERE document_id=? AND version=? ORDER BY chunk_index",
                                        (job["document_id"], job["version"])).fetchall()
                if not rows:
                    continue
                try:
                    vectors = self._embed([row["text_content"] for row in rows])
                    self._check_embedding_state(len(vectors[0]))
                    self._upsert([{"id": row["id"], "vector": vector,
                                               "payload": {"room_id": row["room_id"], "document_id": row["document_id"],
                                                           "document_version": row["version"], "chunk_index": row["chunk_index"]}}
                                              for row, vector in zip(rows, vectors, strict=True)])
                    self._verify_vectors([row["id"] for row in rows])
                    with self.db.connect() as conn:
                        previous_row = conn.execute("SELECT active_version,deleted_at FROM documents WHERE id=?",
                                                     (job["document_id"],)).fetchone()
                        previous = previous_row["active_version"] if previous_row else None
                        cleanup_status = "cleanup_pending" if previous is not None and previous != job["version"] else "ready"
                        conn.execute("INSERT INTO memory_index_state VALUES(1,?,?,0) ON CONFLICT(singleton) DO NOTHING",
                                     (self.embedder.model, len(vectors[0])))
                        conn.execute("UPDATE document_versions SET status='active',failure_code=NULL WHERE document_id=? AND version=?",
                                     (job["document_id"], job["version"]))
                        conn.execute("UPDATE documents SET active_version=?,ingestion_status=?,updated_at=? WHERE id=? AND deleted_at IS NULL",
                                     (job["version"], cleanup_status, utc_now(), job["document_id"]))
                        conn.execute("UPDATE memory_index_jobs SET status='done',updated_at=? WHERE document_id=? AND version=? AND operation='upsert'",
                                     (utc_now(), job["document_id"], job["version"]))
                        if previous is not None and previous != job["version"]:
                            conn.execute("INSERT OR REPLACE INTO memory_index_jobs VALUES(?,?, 'delete','pending',0,NULL,?)",
                                         (job["document_id"], previous, utc_now()))
                    completed += 1
                    if previous is not None and previous != job["version"]:
                        self._cleanup_version(job["document_id"], previous)
                except MemoryError as exc:
                    with self.db.connect() as conn:
                        conn.execute("UPDATE memory_index_jobs SET attempts=attempts+1,last_error_code=?,updated_at=? WHERE document_id=? AND version=? AND operation='upsert'",
                                     (exc.code, utc_now(), job["document_id"], job["version"]))
        return {"processed": len(jobs), "completed": completed}

    def reindex_memory_index(self, *, confirmed: bool = False):
        """Explicitly replace all local vectors using the configured embedding model."""
        if confirmed is not True or not callable(getattr(self.vector_store, "reset", None)):
            raise MemoryValidationError("Explicit reindex confirmation is required.")
        with self.db.connect() as conn:
            docs = [dict(row) for row in conn.execute(
                "SELECT id,active_version FROM documents WHERE deleted_at IS NULL AND active_version IS NOT NULL")]
            conn.execute("UPDATE documents SET ingestion_status='indexing' WHERE deleted_at IS NULL")
            conn.execute("UPDATE memory_index_state SET needs_reindex=1 WHERE singleton=1")
        try:
            # The old index is discarded only after the caller explicitly confirmed this operation.
            self.vector_store.reset(int(os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768")))
            dimension = None
            for doc in docs:
                with self.db.connect() as conn:
                    rows = conn.execute("SELECT * FROM document_chunks WHERE document_id=? AND version=? ORDER BY chunk_index",
                                        (doc["id"], doc["active_version"])).fetchall()
                if not rows:
                    continue
                vectors = self._embed([row["text_content"] for row in rows])
                dimension = len(vectors[0])
                if dimension != int(os.getenv("UBUNTU_AGENT_EMBEDDING_DIMENSIONS", "768")):
                    raise MemoryValidationError("Configured embedding dimension does not match local model output.")
                self._upsert([{"id": row["id"], "vector": vector,
                               "payload": {"room_id": row["room_id"], "document_id": row["document_id"],
                                           "document_version": row["version"], "chunk_index": row["chunk_index"]}}
                              for row, vector in zip(rows, vectors, strict=True)])
                self._verify_vectors([row["id"] for row in rows])
            with self.db.connect() as conn:
                if dimension is not None:
                    conn.execute("INSERT INTO memory_index_state VALUES(1,?,?,0) ON CONFLICT(singleton) DO UPDATE SET model=excluded.model,dimensions=excluded.dimensions,needs_reindex=0",
                                 (self.embedder.model, dimension))
                else:
                    conn.execute("UPDATE memory_index_state SET model=?,needs_reindex=0 WHERE singleton=1",
                                 (self.embedder.model,))
                conn.execute("UPDATE documents SET ingestion_status='ready',updated_at=? WHERE deleted_at IS NULL AND active_version IS NOT NULL",
                             (utc_now(),))
            return {"status": "ready", "documents": len(docs), "embedding_model": self.embedder.model,
                    "dimensions": dimension}
        except Exception as exc:
            with self.db.connect() as conn:
                conn.execute("UPDATE documents SET ingestion_status='indexing' WHERE deleted_at IS NULL AND active_version IS NOT NULL")
                conn.execute("UPDATE memory_index_state SET needs_reindex=1 WHERE singleton=1")
            if isinstance(exc, MemoryError):
                raise
            raise MemoryUnavailableError("Explicit local reindex did not complete; memory remains unavailable until retried.") from exc

    def search_memory(self, query: str, purpose: str, actor: Actor, *, limit: int = 5, resource_filters=None):
        if not isinstance(query, str) or not query.strip() or len(query) > 4000 or not isinstance(purpose, str) or not purpose.strip():
            raise MemoryValidationError("Search request is invalid.")
        if not 1 <= limit <= 20:
            raise MemoryValidationError("Search limit is invalid.")
        rooms = []
        # The trusted actor and bootstrap profile define candidate rooms; policy
        # narrows that set to the content types allowed for memory search.
        if (not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID or
                not isinstance(actor.persona_id, str) or actor.persona_id not in TRUSTED_PERSONAS):
            raise MemoryDeniedError("Memory access denied.")
        from .policy import ROOM_ACCESS
        profile = TRUSTED_PERSONAS[actor.persona_id][2]
        configured_rooms = ROOM_ACCESS.get(profile)
        if not isinstance(configured_rooms, dict):
            raise MemoryDeniedError("Memory access denied.")
        with self.db.connect() as conn:
            for room_id in configured_rooms:
                room = conn.execute("SELECT sensitivity_default FROM rooms WHERE id=?", (room_id,)).fetchone()
                if room is None:
                    raise MemoryDeniedError("Memory access denied.")
                try:
                    self._authorize(actor, room_id, room[0], "memory.search", "memory.search")
                except MemoryDeniedError:
                    continue
                rooms.append((room_id, room[0]))
        if not rooms:
            raise MemoryDeniedError("Memory access denied.")
        if resource_filters is not None:
            if not isinstance(resource_filters, dict) or set(resource_filters) - {"room_ids"}:
                raise MemoryValidationError("Resource filters may only narrow the trusted room scope.")
            requested = resource_filters.get("room_ids", [])
            if not isinstance(requested, list) or any(not isinstance(item, str) for item in requested):
                raise MemoryValidationError("Resource filters are invalid.")
            rooms = [item for item in rooms if item[0] in set(requested)]
            if not rooms:
                raise MemoryDeniedError("Memory access denied.")
        vectors = self._embed([query])
        self._check_embedding_state(len(vectors[0]))
        found = self._search_vectors(vectors[0], [item[0] for item in rooms], min(limit * 5, 100))
        allowed = dict(rooms)
        results = []
        with self.db.connect() as conn:
            for candidate in found:
                if not isinstance(candidate, (tuple, list)) or len(candidate) != 2:
                    continue
                chunk_id, score = candidate
                if not isinstance(chunk_id, str) or not chunk_id:
                    continue
                # Ignore malformed/forged candidate IDs without revealing anything about them.
                row = conn.execute("""SELECT c.*,d.source_id,d.source_uri,d.room_id AS document_room_id,
                          d.sensitivity_label AS document_sensitivity,d.display_name,d.active_version,d.ingestion_status,
                          d.deleted_at,d.cleanup_status,s.canonical_ref,s.display_name AS source_display_name FROM document_chunks c
                          JOIN documents d ON d.id=c.document_id JOIN sources s ON s.id=d.source_id
                          WHERE c.id=?""", (chunk_id,)).fetchone()
                if not row or row["room_id"] not in allowed:
                    continue
                conversational_source = conn.execute("""SELECT s.status,c.deleted_at,c.memory_enabled
                    FROM conversation_memory_sources s JOIN conversations c ON c.id=s.conversation_id
                    WHERE s.document_id=? LIMIT 1""", (row["document_id"],)).fetchone()
                if conversational_source and (conversational_source["status"] != "indexed" or
                                               conversational_source["deleted_at"] is not None or
                                               not conversational_source["memory_enabled"]):
                    continue
                if (row["document_room_id"] != row["room_id"] or
                        row["document_sensitivity"] != row["sensitivity_label"] or
                        row["sensitivity_label"] not in ("internal", "sensitive", "restricted", "public") or
                        not isinstance(row["source_uri"], str) or row["source_uri"] != row["canonical_ref"] or
                        not isinstance(row["display_name"], str) or not row["display_name"].strip() or
                        row["source_display_name"] != row["display_name"]):
                    continue
                if row["active_version"] != row["version"] or row["deleted_at"] or row["ingestion_status"] != "ready" or row["cleanup_status"] != "clean":
                    continue
                try:
                    self._authorize(actor, row["room_id"], row["sensitivity_label"], "memory.search", row["id"])
                except MemoryDeniedError:
                    continue
                try:
                    location = json.loads(row["source_location"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if (not isinstance(location, dict) or not isinstance(score, (int, float)) or
                        isinstance(score, bool) or not math.isfinite(score)):
                    continue
                citation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"citation:{row['id']}"))
                results.append({"snippet": row["text_content"], "score": score,
                                "citation": {"id": citation_id, "source_id": row["source_id"],
                                             "document_id": row["document_id"], "version": row["version"],
                                             "chunk_id": row["id"], "source_ref": row["canonical_ref"],
                                             "location": location}, "title": row["display_name"]})
                if len(results) >= limit:
                    break
        return results

    def get_context_for_destination(self, citation_ids: list[str], actor: Actor, destination: str):
        """Fail closed for external disclosure; only a separately specified local context is supported."""
        if destination != "local":
            raise MemoryDeniedError("Memory access denied.")
        return [self.get_authorized_source(citation_id, actor) for citation_id in citation_ids]

    def get_authorized_source(self, citation_id: str, actor: Actor):
        if not isinstance(citation_id, str):
            raise MemoryDeniedError("Memory access denied.")
        with self.db.connect() as conn:
            # Citation IDs are deterministic but resolved only against current authoritative state.
            records = conn.execute("SELECT id FROM document_chunks").fetchall()
            match = next((r[0] for r in records if str(uuid.uuid5(uuid.NAMESPACE_URL, f"citation:{r[0]}")) == citation_id), None)
        if not match:
            raise MemoryDeniedError("Memory access denied.")
        results = self._resolve_chunk(match, actor)
        return results

    def _resolve_chunk(self, chunk_id: str, actor: Actor):
        with self.db.connect() as conn:
            row = conn.execute("""SELECT c.*,d.active_version,d.deleted_at,d.ingestion_status,d.cleanup_status,
                d.display_name,d.source_uri,d.room_id AS document_room_id,d.sensitivity_label AS document_sensitivity,
                s.canonical_ref,s.display_name AS source_display_name,d.source_id FROM document_chunks c JOIN documents d ON d.id=c.document_id
                JOIN sources s ON s.id=d.source_id WHERE c.id=?""", (chunk_id,)).fetchone()
        if (not row or row["deleted_at"] or row["active_version"] != row["version"] or
                row["ingestion_status"] != "ready" or row["cleanup_status"] != "clean" or
                row["document_room_id"] != row["room_id"] or
                row["document_sensitivity"] != row["sensitivity_label"] or
                row["source_uri"] != row["canonical_ref"] or row["display_name"] != row["source_display_name"]):
            raise MemoryDeniedError("Memory access denied.")
        self._authorize(actor, row["room_id"], row["sensitivity_label"], "memory.search", row["id"])
        try:
            location = json.loads(row["source_location"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise MemoryDeniedError("Memory access denied.") from exc
        if not isinstance(location, dict):
            raise MemoryDeniedError("Memory access denied.")
        return {"text": row["text_content"], "title": row["display_name"], "source_id": row["source_id"],
                "document_id": row["document_id"], "version": row["version"], "chunk_id": row["id"],
                "source_ref": row["canonical_ref"], "location": location}

