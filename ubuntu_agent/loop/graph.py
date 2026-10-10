"""Loop-scoped knowledge graph. Retrieval is always filtered by loop_id."""

from __future__ import annotations

import json
import uuid

from ubuntu_agent.models import utc_now
from ubuntu_agent.services import NotFoundError, PolicyDeniedError, ValidationError

NODE_TYPES = {
    "goal", "constraint", "claim", "proposal", "counterargument", "evidence",
    "source_summary", "decision", "unresolved", "conclusion", "external_response",
}
EDGE_TYPES = {"supports", "contradicts", "refines", "derived_from", "resolves"}


class LoopGraph:
    def __init__(self, database):
        self.database = database

    def add_node(self, loop_id: str, node_type: str, display_name: str, content: str,
                 *, room_id: str, sensitivity: str, provenance: dict | None = None) -> dict:
        if node_type not in NODE_TYPES:
            raise ValidationError("Unknown graph node type.")
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 200:
            raise ValidationError("Node display name is invalid.")
        if not isinstance(content, str) or len(content) > 20000:
            raise ValidationError("Node content is invalid.")
        now = utc_now()
        node_id = str(uuid.uuid4())
        with self.database.connect() as connection:
            connection.execute("INSERT INTO loop_nodes VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (node_id, loop_id, node_type, display_name.strip(), room_id, sensitivity,
                                content, json.dumps(provenance or {}, separators=(",", ":")), now, now))
            return dict(connection.execute("SELECT * FROM loop_nodes WHERE id=?", (node_id,)).fetchone())

    def add_edge(self, loop_id: str, source_id: str, relation: str, target_id: str,
                 *, room_id: str, sensitivity: str) -> dict:
        if relation not in EDGE_TYPES:
            raise ValidationError("Unknown graph relation.")
        edge_id = str(uuid.uuid4())
        with self.database.connect() as connection:
            source = connection.execute("SELECT * FROM loop_nodes WHERE id=? AND loop_id=?",
                                        (source_id, loop_id)).fetchone()
            target = connection.execute("SELECT * FROM loop_nodes WHERE id=? AND loop_id=?",
                                        (target_id, loop_id)).fetchone()
            if source is None or target is None:
                raise NotFoundError("Graph node not found.")
            connection.execute("INSERT INTO loop_edges VALUES (?,?,?,?,?,?,?,?)",
                               (edge_id, loop_id, source_id, relation, target_id, room_id, sensitivity, utc_now()))
            return dict(connection.execute("SELECT * FROM loop_edges WHERE id=?", (edge_id,)).fetchone())

    def nodes(self, loop_id: str) -> list[dict]:
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM loop_nodes WHERE loop_id=? ORDER BY created_at", (loop_id,))]

    def neighbours(self, loop_id: str, node_id: str) -> list[dict]:
        with self.database.connect() as connection:
            node = connection.execute("SELECT id FROM loop_nodes WHERE id=? AND loop_id=?",
                                      (node_id, loop_id)).fetchone()
            if node is None:
                raise NotFoundError("Graph node not found.")
            return [dict(row) for row in connection.execute(
                """SELECT * FROM loop_edges WHERE loop_id=? AND (source_node_id=? OR target_node_id=?)""",
                (loop_id, node_id, node_id))]

    def get_node(self, loop_id: str, node_id: str) -> dict:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM loop_nodes WHERE id=? AND loop_id=?",
                                     (node_id, loop_id)).fetchone()
        if row is None:
            raise NotFoundError("Graph node not found.")
        return dict(row)

    def search_sources(self, loop_id: str, query: str, *, ingested_only: bool = True) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValidationError("Search query is invalid.")
        tokens = {token.lower() for token in query.split() if token}
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM loop_sources WHERE loop_id=? AND (?=0 OR ingested=1)",
                (loop_id, 1 if ingested_only else 0)).fetchall()
        scored = []
        for row in rows:
            hay = f"{row['display_name']} {row['content']}".lower()
            score = sum(1 for token in tokens if token in hay)
            if score:
                scored.append((score, dict(row)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:10]]


def assert_loop_scope(row_loop_id: str, requested: str) -> None:
    if row_loop_id != requested:
        raise PolicyDeniedError("Memory access denied.")
