from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ._pool import ConnectionPool
NODE_TYPES = {'claim', 'evidence', 'constraint', 'assumption', 'alternative', 'question'}
EDGE_TYPES = {'derived_from', 'supported_by', 'constrained_by', 'rejected_because', 'supersedes', 'answers', 'transferred_from'}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class ProvenanceStore:

    def __init__(self, db_path: str | Path | None=None) -> None:
        self.db_path = Path(db_path) if db_path else Path.home() / '.cognex.db' / 'cognex.db'
        self._pool = ConnectionPool(self.db_path, pool_size=3)

    def close(self) -> None:
        self._pool.close_all()

    def ensure_node(self, node_type: str, ref_table: str, ref_id: str, project: str='', session_id: str='') -> str:
        if node_type not in NODE_TYPES:
            node_type = 'claim'
        with self._pool.get_connection() as conn:
            row = conn.execute('SELECT node_id FROM provenance_nodes WHERE ref_table = ? AND ref_id = ? AND node_type = ?', (ref_table, ref_id, node_type)).fetchone()
            if row:
                return row['node_id']
            node_id = uuid.uuid4().hex[:16]
            conn.execute('\n                INSERT INTO provenance_nodes\n                (node_id, node_type, ref_table, ref_id, project, created_at, session_id)\n                VALUES (?, ?, ?, ?, ?, ?, ?)\n                ', (node_id, node_type, ref_table, ref_id, project, _now(), session_id))
            conn.commit()
            return node_id

    def resolve_ref(self, node_or_ref_id: str) -> str | None:
        with self._pool.get_connection() as conn:
            row = conn.execute('SELECT node_id FROM provenance_nodes WHERE node_id = ?', (node_or_ref_id,)).fetchone()
            if row:
                return row['node_id']
            row = conn.execute('SELECT node_id FROM provenance_nodes WHERE ref_id = ? ORDER BY created_at DESC LIMIT 1', (node_or_ref_id,)).fetchone()
            return row['node_id'] if row else None

    def link(self, from_ref: str, to_ref: str, edge_type: str, rationale: str='') -> str:
        if edge_type not in EDGE_TYPES:
            raise ValueError(f'invalid edge_type: {edge_type}')
        from_node = self.resolve_ref(from_ref)
        to_node = self.resolve_ref(to_ref)
        if not from_node or not to_node:
            raise ValueError('from_ref and to_ref must resolve to provenance nodes')
        if self._path_exists(to_node, from_node):
            raise ValueError('provenance link would create a cycle')
        edge_id = uuid.uuid4().hex[:16]
        with self._pool.get_connection() as conn:
            conn.execute('\n                INSERT INTO provenance_edges\n                (edge_id, from_node, to_node, edge_type, rationale, created_at)\n                VALUES (?, ?, ?, ?, ?, ?)\n                ', (edge_id, from_node, to_node, edge_type, rationale, _now()))
            conn.commit()
        return edge_id

    def _path_exists(self, start: str, target: str) -> bool:
        seen: set[str] = set()
        frontier = [start]
        with self._pool.get_connection() as conn:
            while frontier:
                node = frontier.pop()
                if node == target:
                    return True
                if node in seen:
                    continue
                seen.add(node)
                rows = conn.execute('SELECT to_node FROM provenance_edges WHERE from_node = ?', (node,)).fetchall()
                frontier.extend((r['to_node'] for r in rows))
        return False

    def trace(self, node_or_ref_id: str, direction: str='origins', depth: int=3) -> dict[str, Any]:
        root = self.resolve_ref(node_or_ref_id)
        if not root:
            return {'root': node_or_ref_id, 'found': False, 'tree': []}
        depth = max(0, min(int(depth), 8))
        with self._pool.get_connection() as conn:
            return {'root': root, 'found': True, 'direction': direction, 'tree': self._trace_node(conn, root, direction, depth, set(), None)}

    def _trace_node(self, conn: sqlite3.Connection, node_id: str, direction: str, depth: int, seen: set[str], edge_type: str | None) -> dict[str, Any]:
        row = conn.execute('SELECT * FROM provenance_nodes WHERE node_id = ?', (node_id,)).fetchone()
        if not row:
            return {'id': node_id, 'missing': True}
        item = {'id': row['node_id'], 'type': row['node_type'], 'ref': f"{row['ref_table']}:{row['ref_id']}", 'content': self._one_line(conn, row['ref_table'], row['ref_id'])}
        if edge_type:
            item['edge_type'] = edge_type
        if depth <= 0 or node_id in seen:
            return item
        seen.add(node_id)
        if direction == 'impacts':
            sql = 'SELECT to_node AS next_node, edge_type FROM provenance_edges WHERE from_node = ?'
        else:
            sql = 'SELECT from_node AS next_node, edge_type FROM provenance_edges WHERE to_node = ?'
        rows = conn.execute(sql, (node_id,)).fetchall()
        item['children'] = [self._trace_node(conn, r['next_node'], direction, depth - 1, seen, r['edge_type']) for r in rows]
        return item

    @staticmethod
    def _one_line(conn: sqlite3.Connection, table: str, ref_id: str) -> str:
        column_map = {'memories': ('content', 'id'), 'cognitive_units': ('content', 'unit_id'), 'decisions': ('reasoning', 'id'), 'open_questions': ('content', 'question_id')}
        if table not in column_map:
            return ''
        content_col, id_col = column_map[table]
        try:
            row = conn.execute(f'SELECT {content_col} FROM {table} WHERE {id_col} = ?', (ref_id,)).fetchone()
        except sqlite3.OperationalError:
            return ''
        if not row or not row[0]:
            return ''
        text = ' '.join(str(row[0]).split())
        return text[:117] + '...' if len(text) > 120 else text