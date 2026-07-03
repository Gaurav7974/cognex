from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ._pool import ConnectionPool
from .integrity import IntegrityStore, canonical_json
from .teleport import get_key_fingerprint, get_or_create_keys, sign_bundle, verify_signature

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _line(text: str, limit: int=96) -> str:
    text = ' '.join((text or '').split())
    return text[:limit - 3] + '...' if len(text) > limit else text

class HandoffStore:

    def __init__(self, db_path: str | Path | None=None) -> None:
        self.db_path = Path(db_path) if db_path else Path.home() / '.cognex.db' / 'cognex.db'
        self._pool = ConnectionPool(self.db_path, pool_size=3)
        self.integrity = IntegrityStore(self.db_path)

    def close(self) -> None:
        self.integrity.close()
        self._pool.close_all()

    def create(self, project: str, goal_stack: list[str], in_flight_ops: list[str], notes: str, prior_baseline: str='') -> dict[str, Any]:
        root = self.integrity.compute_root(project)
        manifest = {'manifest_id': uuid.uuid4().hex[:16], 'version': '1.0', 'created_at': _now(), 'project': project, 'goal_stack': goal_stack[:8], 'in_flight_ops': in_flight_ops[:12], 'notes': _line(notes, 240), 'constraints': [], 'epistemic': {}, 'open_questions': [], 'recent_decisions': [], 'counterfactuals': [], 'merkle_root': root['root_hash'], 'key_fingerprint': root['key_fingerprint'], 'baseline_marker': self._latest_audit_marker(project), 'prior_baseline': prior_baseline, 'deltas': []}
        with self._pool.get_connection() as conn:
            units = conn.execute('SELECT * FROM cognitive_units WHERE project = ? ORDER BY confidence DESC, created_at DESC LIMIT 40', (project,)).fetchall()
            counts: dict[str, int] = {}
            top: dict[str, list[dict[str, str]]] = {}
            for row in units:
                status = row['epistemic_status'] or 'assumed'
                counts[status] = counts.get(status, 0) + 1
                top.setdefault(status, [])
                if len(top[status]) < 5:
                    top[status].append({'id': row['unit_id'], 'gist': _line(row['content'])})
                if row['unit_type'] == 'constraint' and len(manifest['constraints']) < 12:
                    manifest['constraints'].append({'id': row['unit_id'], 'gist': _line(row['content'])})
            manifest['epistemic'] = {'counts': counts, 'top': top}
            qs = conn.execute("SELECT question_id, content FROM open_questions WHERE project = ? AND status = 'open' ORDER BY created_at DESC LIMIT 12", (project,)).fetchall()
            manifest['open_questions'] = [{'id': r['question_id'], 'q': _line(r['content'])} for r in qs]
            decisions = conn.execute('SELECT id, reasoning FROM decisions WHERE project = ? ORDER BY timestamp DESC LIMIT 12', (project,)).fetchall()
            manifest['recent_decisions'] = [{'id': r['id'], 'gist': _line(r['reasoning'])} for r in decisions]
            alts = conn.execute("\n                SELECT n.node_id, n.ref_id, e.rationale\n                FROM provenance_nodes n\n                JOIN provenance_edges e ON e.from_node = n.node_id\n                WHERE n.project = ? AND n.node_type = 'alternative'\n                ORDER BY n.created_at DESC LIMIT 20\n                ", (project,)).fetchall()
            manifest['counterfactuals'] = [{'id': r['node_id'], 'ref': r['ref_id'], 'reason': _line(r['rationale'])} for r in alts]
            if prior_baseline:
                manifest['deltas'] = self._deltas_since(conn, project, prior_baseline)
        payload = canonical_json(manifest)
        private_key, public_key = get_or_create_keys()
        manifest['signature'] = sign_bundle(payload, private_key).hex()
        manifest['key_fingerprint'] = get_key_fingerprint(public_key)
        return manifest

    def resume(self, manifest_json: str | dict[str, Any]) -> dict[str, Any]:
        manifest = json.loads(manifest_json) if isinstance(manifest_json, str) else dict(manifest_json)
        signature = manifest.pop('signature', '')
        _, public_key = get_or_create_keys()
        verified = False
        if signature:
            verified = verify_signature(canonical_json(manifest), bytes.fromhex(signature), public_key)
        manifest['signature'] = signature
        if not verified:
            return {'status': 'failed', 'reason': 'manifest signature invalid'}
        stale = self._stale_units(manifest.get('project', ''))
        return {'status': 'ready', 'signature_valid': True, 'project': manifest.get('project', ''), 'goal_stack': manifest.get('goal_stack', []), 'in_flight_ops': manifest.get('in_flight_ops', []), 'must_not_revisit': manifest.get('counterfactuals', []), 'open_questions': manifest.get('open_questions', []), 'stale_units': stale, 'merkle_root': manifest.get('merkle_root', ''), 'baseline_marker': manifest.get('baseline_marker', ''), 'deltas': manifest.get('deltas', [])}

    def _latest_audit_marker(self, project: str) -> str:
        with self._pool.get_connection() as conn:
            row = conn.execute('SELECT log_id FROM audit_log WHERE project = ? ORDER BY created_at DESC LIMIT 1', (project,)).fetchone()
        return row['log_id'] if row else ''

    def _deltas_since(self, conn, project: str, baseline: str) -> list[dict[str, Any]]:
        row = conn.execute('SELECT created_at FROM audit_log WHERE log_id = ?', (baseline,)).fetchone()
        if not row:
            return []
        since = row['created_at']
        units = conn.execute('SELECT unit_id, content, epistemic_status FROM cognitive_units WHERE project = ? AND created_at > ? ORDER BY created_at DESC LIMIT 30', (project, since)).fetchall()
        memories = conn.execute('SELECT id, gist FROM memories WHERE project = ? AND created_at > ? ORDER BY created_at DESC LIMIT 30', (project, since)).fetchall()
        return ([{'kind': 'unit', 'id': r['unit_id'], 'gist': _line(r['content']), 'status': r['epistemic_status']} for r in units] + [{'kind': 'memory', 'id': r['id'], 'gist': _line(r['gist'])} for r in memories])[:40]

    def _stale_units(self, project: str) -> list[dict[str, str]]:
        now = _now()
        with self._pool.get_connection() as conn:
            rows = conn.execute('SELECT unit_id, content, verification_condition FROM cognitive_units WHERE project = ? AND staleness_deadline IS NOT NULL AND staleness_deadline <= ? ORDER BY staleness_deadline ASC LIMIT 20', (project, now)).fetchall()
        return [{'id': r['unit_id'], 'gist': _line(r['content']), 'verification_condition': _line(r['verification_condition'], 140)} for r in rows]