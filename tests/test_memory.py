import json
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from ubuntu_agent.database import Database
from ubuntu_agent.memory import (EmbeddingAdapter, EmbeddingError, MemoryService,
                                 MemoryValidationError, MemoryDeniedError, deterministic_chunks)
from ubuntu_agent.models import Actor


class FakeEmbedder:
    model = "fake-local-v1"

    def __init__(self, fail=False):
        self.fail = fail
        self.inputs = []

    def embed(self, texts):
        self.inputs.extend(texts)
        if self.fail:
            raise RuntimeError("offline")
        return [[float(len(text)), 1.0, 2.0] for text in texts]


class FakeVectors:
    dimensions = 3

    def __init__(self):
        self.items = {}
        self.fail_upsert = False
        self.fail_delete = False
        self.queries = []

    def upsert(self, points):
        if self.fail_upsert:
            raise RuntimeError("offline")
        self.items.update({point["id"]: point for point in points})

    def search(self, vector, *, room_ids, limit):
        self.queries.append(list(room_ids))
        ids = list(self.items)
        # Deliberately return IDs outside the requested scope to test SQLite checks.
        return [(item, 0.9 - index / 100) for index, item in enumerate(ids[:limit])]

    def contains(self, point_ids):
        return [item for item in point_ids if item in self.items]

    def reset(self, dimensions):
        self.items.clear()

    def delete(self, point_ids):
        if self.fail_delete:
            raise RuntimeError("offline")
        for item in point_ids:
            self.items.pop(item, None)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = Database(root / "agent.sqlite3")
        self.db.initialize()
        self.vectors = FakeVectors()
        self.embedder = FakeEmbedder()
        self.memory = MemoryService(self.db, self.embedder, self.vectors, data_dir=root)
        self.manager = Actor("local-user", "task_deadline_manager")
        self.researcher = Actor("local-user", "ai_ml_researcher")
        self.coach = Actor("local-user", "exam_study_coach")
        self.file = root / "notes.md"
        self.file.write_text("# Heading\n\nTrusted local note content.\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_ingestion_has_stable_chunk_provenance_and_reopens(self):
        result = self.memory.ingest_document(self.file, self.manager, "operations")
        again = self.memory.ingest_document(self.file, self.manager, "operations")
        self.assertTrue(again["unchanged"])
        found = self.memory.search_memory("local note", "retrieve notes", self.manager)
        self.assertEqual("Heading", found[0]["citation"]["location"]["heading"])
        self.assertEqual(result["document_id"], found[0]["citation"]["document_id"])
        reopened = Database(self.db.path)
        with reopened.connect() as conn:
            self.assertEqual(1, conn.execute("select count(*) from documents where ingestion_status='ready'").fetchone()[0])
            self.assertEqual(1, conn.execute("pragma foreign_keys").fetchone()[0])

    def test_empty_oversized_bad_encoding_and_unsupported_leave_no_records(self):
        for name, content, suffix in (("empty.txt", b"", ".txt"), ("large.txt", b"x" * 100, ".txt"),
                                      ("bad.txt", b"\xff", ".txt"), ("bad.pdf", b"valid", ".pdf")):
            with self.subTest(name=name):
                path = Path(self.temp.name) / name
                path.write_bytes(content)
                service = MemoryService(self.db, self.embedder, self.vectors, max_document_bytes=50)
                with self.assertRaises(MemoryValidationError):
                    service.ingest_document(path, self.manager, "operations")
        with self.db.connect() as conn:
            self.assertEqual(0, conn.execute("select count(*) from documents").fetchone()[0])

    def test_cross_room_candidate_does_not_return_content_and_query_is_policy_scoped(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        other = Path(self.temp.name) / "project.md"
        other.write_text("Private project note", encoding="utf-8")
        self.memory.ingest_document(other, self.researcher, "projects")
        found = self.memory.search_memory("note", "search", self.coach)
        self.assertTrue(all("Private project" not in item["snippet"] for item in found))
        self.assertNotIn("projects", self.vectors.queries[-1])

    def test_operations_document_scope_is_limited_to_authorized_persona(self):
        self.file.write_text("violet comet 742 Operations-only text", encoding="utf-8")
        self.memory.ingest_document(self.file, self.manager, "operations")

        authorized = self.memory.search_memory("violet comet 742", "authorized retrieval", self.manager)
        self.assertEqual(1, len(authorized))
        self.assertIn("Operations-only text", authorized[0]["snippet"])
        self.assertIn(str(self.file), authorized[0]["citation"]["source_ref"])

        self.vectors.queries.clear()
        denied = self.memory.search_memory("violet comet 742", "authorized scope=operations; verify cross-room isolation", self.coach)
        self.assertEqual([], denied)
        self.assertNotIn("operations", self.vectors.queries[-1])
        serialized = json.dumps(denied)
        for protected in ("Operations-only text", self.file.name, str(self.file), "citation", "operations", "internal"):
            self.assertNotIn(protected, serialized)

    def test_broader_filter_and_forged_qdrant_ids_cannot_widen_scope(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        self.assertEqual([], self.memory.search_memory("violet comet 742", "unfiltered", self.coach))
        self.assertNotIn("operations", self.vectors.queries[-1])
        with self.assertRaises(MemoryDeniedError):
            self.memory.search_memory("violet comet 742", "filter bypass", self.coach,
                                      resource_filters={"room_ids": ["operations"]})
        self.assertNotIn("operations", self.vectors.queries[-1])

        # This fake ignores Qdrant's filter and returns every indexed ID. SQLite
        # and the per-candidate policy check must still drop the Operations row.
        result = self.memory.search_memory("violet comet 742", "forged candidate", self.coach)
        self.assertEqual([], result)
        self.assertNotIn("operations", json.dumps(result))

    def test_unauthorized_citation_resolution_is_indistinguishable_from_missing(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        record = self.memory.search_memory("local note", "authorized", self.manager)[0]
        citation = record["citation"]["id"]
        with self.assertRaises(MemoryDeniedError) as caught:
            self.memory.get_authorized_source(citation, self.coach)
        self.assertEqual("Memory access denied.", str(caught.exception))

    def test_forged_or_inconsistent_persisted_persona_and_room_metadata_deny(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        with self.db.connect() as conn:
            conn.execute("UPDATE personas SET policy_profile_id='task_manager' WHERE id='exam_study_coach'")
        with self.assertRaises(MemoryDeniedError):
            self.memory.search_memory("local note", "tampered persona", self.coach)

        # Restore persona metadata and corrupt the trusted Operations label.
        with self.db.connect() as conn:
            conn.execute("UPDATE personas SET policy_profile_id='study_coach' WHERE id='exam_study_coach'")
            conn.execute("UPDATE rooms SET sensitivity_default='public' WHERE id='operations'")
        with self.assertRaises(MemoryDeniedError):
            self.memory._authorize(self.manager, "operations", "public", "memory.search", "memory.search")

    def test_chunk_document_metadata_disagreement_and_unknown_labels_are_dropped(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        with self.db.connect() as conn:
            conn.execute("UPDATE document_chunks SET sensitivity_label='sensitive' WHERE id=(SELECT id FROM document_chunks LIMIT 1)")
        result = self.memory.search_memory("local note", "metadata mismatch", self.manager)
        self.assertEqual([], result)
        with self.assertRaises(MemoryDeniedError):
            self.memory._authorize(self.manager, "operations", "mystery", "memory.search", "memory.search")

    def test_missing_authorized_room_metadata_fails_before_vector_query(self):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM rooms WHERE id='academic'")
        with self.assertRaises(MemoryDeniedError):
            self.memory.search_memory("local note", "missing room metadata", self.manager)
        self.assertEqual([], self.vectors.queries)

    def test_cli_persona_selection_reaches_memory_service(self):
        from ubuntu_agent import cli

        observed = {}

        class MemoryProbe:
            def __init__(self, db):
                pass

            def search_memory(self, query, purpose, actor, *, limit):
                observed["persona"] = actor.persona_id
                return []

        db_path = Path(self.temp.name) / "cli.sqlite3"
        output = io.StringIO()
        with patch.object(cli, "MemoryService", MemoryProbe), contextlib.redirect_stdout(output):
            code = cli.main(["--db", str(db_path), "--persona", "exam_study_coach", "memory-search",
                             "violet comet 742", "--purpose", "verify isolation"])
        self.assertEqual(0, code)
        self.assertEqual("exam_study_coach", observed["persona"])

    def test_missing_or_conflicting_trusted_metadata_fails_closed(self):
        with self.assertRaises(MemoryDeniedError):
            self.memory.ingest_document(self.file, self.manager, "missing")
        with self.assertRaises(MemoryDeniedError):
            self.memory.ingest_document(self.file, self.manager, "operations", sensitivity="public")

    def test_forged_old_duplicate_and_deleted_vector_ids_are_ignored(self):
        first = self.memory.ingest_document(self.file, self.manager, "operations")
        old_ids = list(self.vectors.items)
        self.vectors.items["forged"] = {"id": "forged", "vector": [0, 0, 0], "payload": {"room_id": "operations"}}
        self.file.write_text("Replacement content", encoding="utf-8")
        second = self.memory.update_document(self.file, self.manager, "operations")
        self.assertGreater(second["version"], first["version"])
        self.assertFalse(any(item["citation"]["version"] == first["version"] for item in self.memory.search_memory("x", "test", self.manager)))
        self.memory.delete_document(first["document_id"], self.manager)
        self.assertEqual([], self.memory.search_memory("x", "test", self.manager))

    def test_failed_index_does_not_activate_incomplete_version(self):
        failing_vectors = FakeVectors(); failing_vectors.fail_upsert = True
        service = MemoryService(self.db, self.embedder, failing_vectors)
        with self.assertRaises(Exception):
            service.ingest_document(self.file, self.manager, "operations")
        with self.db.connect() as conn:
            row = conn.execute("select active_version,ingestion_status from documents").fetchone()
        self.assertIsNone(row[0])
        self.assertEqual("failed", row[1])

    def test_reconciliation_recovers_failed_upsert_without_duplicate_activation(self):
        self.vectors.fail_upsert = True
        with self.assertRaises(Exception):
            self.memory.ingest_document(self.file, self.manager, "operations")
        self.vectors.fail_upsert = False
        result = self.memory.reconcile_memory_index()
        self.assertEqual(1, result["completed"])
        self.assertEqual(1, len(self.memory.search_memory("note", "test", self.manager)))
        self.assertEqual(0, self.memory.reconcile_memory_index()["completed"])

    def test_failed_delete_cleanup_keeps_tombstone_unsearchable(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        self.vectors.fail_delete = True
        document_id = self.memory.search_memory("note", "test", self.manager)[0]["citation"]["document_id"]
        self.memory.delete_document(document_id, self.manager)
        self.assertEqual([], self.memory.search_memory("note", "test", self.manager))

    def test_reconciliation_retries_pending_delete_idempotently(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        doc_id = self.memory.search_memory("note", "test", self.manager)[0]["citation"]["document_id"]
        self.vectors.fail_delete = True
        self.memory.delete_document(doc_id, self.manager)
        self.vectors.fail_delete = False
        self.assertEqual(1, self.memory.reconcile_memory_index()["completed"])
        self.assertEqual(0, self.memory.reconcile_memory_index()["completed"])
        self.assertEqual([], self.memory.search_memory("note", "test", self.manager))

    def test_citation_resolution_reauthorizes_and_cloud_path_has_no_assembly_interface(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        citation = self.memory.search_memory("note", "test", self.manager)[0]["citation"]["id"]
        self.assertIn("Trusted local note", self.memory.get_authorized_source(citation, self.manager)["text"])
        with self.assertRaises(MemoryDeniedError):
            self.memory.get_authorized_source(citation, Actor("forged", "task_deadline_manager"))
        with self.assertRaises(MemoryDeniedError):
            self.memory.get_context_for_destination([citation], self.manager, "gemini")

    def test_chunking_deterministic_and_bounded(self):
        value = "# A\n\n" + ("word " * 1000)
        self.assertEqual(deterministic_chunks(value), deterministic_chunks(value))
        self.assertTrue(all(len(item.text) <= 1600 for item in deterministic_chunks(value)))

    def test_embedding_model_change_requires_reindex_before_query(self):
        self.memory.ingest_document(self.file, self.manager, "operations")
        self.embedder.model = "changed-model"
        with self.assertRaises(MemoryValidationError):
            self.memory.search_memory("note", "test", self.manager)
        with self.assertRaises(MemoryValidationError):
            self.memory.reindex_memory_index()
        with patch.dict("os.environ", {"UBUNTU_AGENT_EMBEDDING_DIMENSIONS": "3"}):
            self.assertEqual("ready", self.memory.reindex_memory_index(confirmed=True)["status"])
        self.assertEqual(1, len(self.memory.search_memory("note", "test", self.manager)))

    def test_ollama_api_embed_response_with_embeddings_is_accepted(self):
        vector = [float(index) / 768 for index in range(768)]
        requests = []

        def transport(req, timeout):
            requests.append(req)
            return json.dumps({"embeddings": [vector]}).encode()

        adapter = EmbeddingAdapter(transport=transport)
        self.assertEqual([vector], adapter.embed(["violet comet 742"]))
        self.assertEqual("http://127.0.0.1:11434/api/embed", requests[0].full_url)
        self.assertEqual("embeddinggemma", json.loads(requests[0].data)["model"])

    def test_ollama_embedding_dimension_mismatch_is_rejected(self):
        adapter = EmbeddingAdapter(transport=lambda req, timeout: json.dumps(
            {"embeddings": [[0.0] * 767]}).encode())
        with self.assertRaisesRegex(EmbeddingError, "dimension does not match"):
            adapter.embed(["violet comet 742"])


if __name__ == "__main__":
    unittest.main()
