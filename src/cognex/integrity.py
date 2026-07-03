from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ._pool import ConnectionPool
from .teleport import get_key_fingerprint, get_or_create_keys, sign_bundle, verify_signature

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)

def leaf_hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode()).hexdigest()

def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return hashlib.sha256(b'').hexdigest()
    level = sorted(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256((level[i] + level[i + 1]).encode()).hexdigest() for i in range(0, len(level), 2)]
    return level[0]

class IntegrityStore:

    def __init__(self, db_path: str | Path | None=None) -> None:
        self.db_path = Path(db_path) if db_path else Path.home() / '.cognex.db' / 'cognex.db'
        self._pool = ConnectionPool(self.db_path, pool_size=3)

    def close(self) -> None:
        self._pool.close_all()

    def project_records(self, project: str, ref_ids: list[str] | None=None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        refs = set(ref_ids or [])
        with self._pool.get_connection() as conn:
            specs = [('memories', 'id', 'project'), ('cognitive_units', 'unit_id', 'project'), ('decisions', 'id', 'project'), ('provenance_edges', 'edge_id', None)]
            for table, id_col, project_col in specs:
                try:
                    if project_col:
                        rows = conn.execute(f'SELECT * FROM {table} WHERE {project_col} = ?', (project,)).fetchall()
                    else:
                        rows = conn.execute(f'SELECT * FROM {table}').fetchall()
                except Exception:
                    continue
                for row in rows:
                    record = dict(row)
                    ref = str(record.get(id_col, ''))
                    if refs and ref not in refs:
                        continue
                    records.append({'table': table, 'id': ref, 'row': record})
        return records

    def compute_root(self, project: str) -> dict[str, Any]:
        records = self.project_records(project)
        leaves = [leaf_hash(r) for r in records]
        root = merkle_root(leaves)
        private_key, public_key = get_or_create_keys()
        signature = sign_bundle(root, private_key).hex()
        fingerprint = get_key_fingerprint(public_key)
        computed_at = datetime.now(timezone.utc).isoformat()
        with self._pool.get_connection() as conn:
            conn.execute('\n                INSERT OR REPLACE INTO integrity_roots\n                (root_hash, project, computed_at, record_count, signature, key_fingerprint)\n                VALUES (?, ?, ?, ?, ?, ?)\n                ', (root, project, computed_at, len(records), signature, fingerprint))
            conn.commit()
        return {'root_hash': root, 'project': project, 'computed_at': computed_at, 'record_count': len(records), 'signature': signature, 'key_fingerprint': fingerprint}

    def latest_root(self, project: str) -> dict[str, Any] | None:
        with self._pool.get_connection() as conn:
            row = conn.execute('SELECT * FROM integrity_roots WHERE project = ? ORDER BY computed_at DESC LIMIT 1', (project,)).fetchone()
        return dict(row) if row else None

    def verify(self, project: str, ref_ids: list[str] | None=None) -> dict[str, Any]:
        snapshot = self.compute_root(project)
        _, public_key = get_or_create_keys()
        sig_ok = verify_signature(snapshot['root_hash'], bytes.fromhex(snapshot['signature']), public_key)
        records = self.project_records(project, ref_ids)
        return {'project': project, 'root_hash': snapshot['root_hash'], 'record_count': snapshot['record_count'], 'signature_valid': sig_ok, 'verified': sig_ok and (not ref_ids or len(records) == len(set(ref_ids))), 'records': [{'ref': f"{r['table']}:{r['id']}", 'leaf_hash': leaf_hash(r)} for r in records[:100]]}