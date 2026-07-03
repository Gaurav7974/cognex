from __future__ import annotations
import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ._pool import ConnectionPool

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _tokens(text: str) -> set[str]:
    return {t for t in re.findall('[a-z0-9]+', text.lower()) if len(t) > 2}

def _overlap(a: str, b: str) -> float:
    left = _tokens(a)
    right = _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))

def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]

class Reconciler:

    def __init__(self, db_path: str | Path | None=None) -> None:
        self.db_path = Path(db_path) if db_path else Path.home() / '.cognex.db' / 'cognex.db'
        self._pool = ConnectionPool(self.db_path, pool_size=3)

    def close(self) -> None:
        self._pool.close_all()

    def classify_units(self, incoming: list[dict[str, Any]]) -> dict[str, Any]:
        report = {'new': [], 'identical': [], 'conflicts': []}
        with self._pool.get_connection() as conn:
            for item in incoming:
                content = item.get('content', '')
                project = item.get('project', '')
                scope = item.get('scope', '')
                rows = conn.execute('SELECT * FROM cognitive_units WHERE project = ? AND scope = ?', (project, scope)).fetchall()
                exact = [r for r in rows if content_hash(r['content']) == content_hash(content)]
                if exact:
                    report['identical'].append({'incoming_id': item.get('unit_id', ''), 'local_id': exact[0]['unit_id']})
                    continue
                candidates = [r for r in rows if _overlap(r['content'], content) >= 0.45]
                if candidates:
                    row = candidates[0]
                    cid = self._record_conflict('contradiction', row['unit_id'], item.get('unit_id', ''), project, scope, row['content'], content)
                    report['conflicts'].append({'conflict_id': cid, 'class': 'contradiction', 'local_id': row['unit_id'], 'incoming_id': item.get('unit_id', ''), 'local': row['content'][:120], 'incoming': content[:120]})
                else:
                    report['new'].append(item)
        return report

    def classify_memories(self, incoming: list[dict[str, Any]]) -> dict[str, Any]:
        report = {'new': [], 'identical': [], 'conflicts': []}
        with self._pool.get_connection() as conn:
            for item in incoming:
                content = item.get('content', '')
                project = item.get('project', '')
                scope = item.get('scope', '')
                rows = conn.execute('SELECT * FROM memories WHERE project = ? AND scope = ?', (project, scope)).fetchall()
                exact = [r for r in rows if content_hash(r['content']) == content_hash(content)]
                if exact:
                    report['identical'].append({'incoming_id': item.get('id', ''), 'local_id': exact[0]['id']})
                    continue
                candidates = [r for r in rows if _overlap(r['content'], content) >= 0.55]
                if candidates:
                    row = candidates[0]
                    cid = self._record_conflict('confidence_divergence', row['id'], item.get('id', ''), project, scope, row['content'], content)
                    report['conflicts'].append({'conflict_id': cid, 'class': 'confidence_divergence', 'local_id': row['id'], 'incoming_id': item.get('id', ''), 'local': row['content'][:120], 'incoming': content[:120]})
                else:
                    report['new'].append(item)
        return report

    def _record_conflict(self, item_class: str, local_ref: str, incoming_ref: str, project: str, scope: str, local_line: str, incoming_line: str) -> str:
        conflict_id = uuid.uuid4().hex[:16]
        with self._pool.get_connection() as conn:
            conn.execute('\n                INSERT INTO reconciliation_conflicts\n                (conflict_id, item_class, local_ref, incoming_ref, project, scope,\n                 local_line, incoming_line, created_at)\n                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n                ', (conflict_id, item_class, local_ref, incoming_ref, project, scope, local_line[:240], incoming_line[:240], _now()))
            conn.commit()
        return conflict_id

    def resolve(self, conflict_id: str, resolution: str, rationale: str) -> dict[str, Any]:
        if resolution not in {'keep_local', 'accept_incoming', 'merge'}:
            raise ValueError('resolution must be keep_local, accept_incoming, or merge')
        with self._pool.get_connection() as conn:
            row = conn.execute('SELECT * FROM reconciliation_conflicts WHERE conflict_id = ?', (conflict_id,)).fetchone()
            if not row:
                raise ValueError(f'Conflict not found: {conflict_id}')
            conn.execute('\n                UPDATE reconciliation_conflicts\n                SET resolution = ?, rationale = ?, resolved_at = ?\n                WHERE conflict_id = ?\n                ', (resolution, rationale, _now(), conflict_id))
            conn.commit()
        return {'conflict_id': conflict_id, 'resolution': resolution, 'status': 'resolved'}