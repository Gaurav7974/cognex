
from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ._pool import ConnectionPool

logger = logging.getLogger(__name__)

# The canonical sentinel value for the first entry in the chain.
_GENESIS = "GENESIS"


def _safe_get(row, key: str, default=None):
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


class AuditLog:

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".cognex.db" / "cognex.db"
        elif isinstance(db_path, str):
            db_path = Path(db_path)

        self.db_path = db_path
        self._pool = ConnectionPool(db_path, pool_size=3)
        # Append operations must be serialised so that prev_checksum lookup
        # and INSERT are atomic within a single connection.
        import threading
        self._append_lock = threading.Lock()


    def append(
        self,
        event_type: str,
        session_id: str | None = None,
        project: str | None = None,
        agent_id: str | None = None,
        payload: dict | None = None,
    ) -> str:
        log_id = uuid4().hex[:16]
        payload = payload or {}
        created_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True)

        with self._append_lock:
            try:
                with self._pool.get_connection() as conn:
                    # Fetch the previous entry's checksum (chain linkage).
                    prev_row = conn.execute(
                        "SELECT checksum FROM audit_log ORDER BY created_at DESC LIMIT 1"
                    ).fetchone()
                    prev_checksum = prev_row["checksum"] if prev_row else _GENESIS

                    # Compute this entry's checksum including the chain link.
                    checksum_input = (
                        f"{log_id}:{event_type}:{session_id or ''}:"
                        f"{payload_json}:{prev_checksum}"
                    )
                    checksum = hashlib.sha256(
                        checksum_input.encode()
                    ).hexdigest()[:32]

                    conn.execute(
                        """
                        INSERT INTO audit_log
                        (log_id, event_type, session_id, project, agent_id,
                         payload, created_at, checksum, prev_checksum)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log_id, event_type, session_id, project, agent_id,
                            payload_json, created_at, checksum, prev_checksum,
                        ),
                    )
                    conn.commit()
            except Exception as exc:
                print(
                    f"Warning: Failed to log audit event {event_type!r}: {exc}",
                    file=sys.stderr,
                )
                return ""

        return log_id


    def get_recent(
        self, project: str | None = None, limit: int = 50
    ) -> list[dict]:
        with self._pool.get_connection() as conn:
            if project:
                rows = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, project, agent_id,
                           payload, created_at, checksum, prev_checksum
                    FROM   audit_log
                    WHERE  project = ?
                    ORDER  BY created_at DESC
                    LIMIT  ?
                    """,
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, project, agent_id,
                           payload, created_at, checksum, prev_checksum
                    FROM   audit_log
                    ORDER  BY created_at DESC
                    LIMIT  ?
                    """,
                    (limit,),
                ).fetchall()

        return [
            {
                "log_id": r["log_id"],
                "event_type": r["event_type"],
                "session_id": r["session_id"],
                "project": r["project"],
                "agent_id": r["agent_id"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
                "checksum": r["checksum"],
                "prev_checksum": _safe_get(r, "prev_checksum", _GENESIS),
            }
            for r in rows
        ]


    def verify_integrity(self, log_id: str) -> dict:
        with self._pool.get_connection() as conn:
            row = conn.execute(
                """
                SELECT log_id, event_type, session_id, payload,
                       checksum, prev_checksum
                FROM   audit_log
                WHERE  log_id = ?
                """,
                (log_id,),
            ).fetchone()

        if not row:
            return {
                "log_id": log_id,
                "valid": False,
                "stored_checksum": None,
                "computed_checksum": None,
                "error": f"Log entry {log_id!r} not found",
            }

        payload = json.loads(row["payload"])
        prev_checksum = _safe_get(row, "prev_checksum", _GENESIS) or _GENESIS
        checksum_input = (
            f"{row['log_id']}:{row['event_type']}:{row['session_id'] or ''}:"
            f"{json.dumps(payload, sort_keys=True)}:{prev_checksum}"
        )
        computed = hashlib.sha256(checksum_input.encode()).hexdigest()[:32]

        return {
            "log_id": log_id,
            "valid": computed == row["checksum"],
            "stored_checksum": row["checksum"],
            "computed_checksum": computed,
            "prev_checksum": prev_checksum,
            "event_type": row["event_type"],
            "session_id": row["session_id"],
            "payload": payload,
        }

    def verify_chain(
        self, project: str | None = None, limit: int = 200
    ) -> dict:
        with self._pool.get_connection() as conn:
            if project:
                rows = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, payload,
                           checksum, prev_checksum, created_at
                    FROM   audit_log
                    WHERE  project = ?
                    ORDER  BY created_at ASC
                    LIMIT  ?
                    """,
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, payload,
                           checksum, prev_checksum, created_at
                    FROM   audit_log
                    ORDER  BY created_at ASC
                    LIMIT  ?
                    """,
                    (limit,),
                ).fetchall()

        broken: list[str] = []
        expected_prev = _GENESIS

        for row in rows:
            log_id = row["log_id"]
            prev_checksum = _safe_get(row, "prev_checksum", _GENESIS) or _GENESIS

            if prev_checksum != expected_prev:
                broken.append(log_id)
                logger.warning(
                    "Chain break at %s: expected prev=%s, got %s",
                    log_id, expected_prev, prev_checksum,
                )
                # Don't abort — continue to find all breaks.

            payload = json.loads(row["payload"])
            checksum_input = (
                f"{row['log_id']}:{row['event_type']}:{row['session_id'] or ''}:"
                f"{json.dumps(payload, sort_keys=True)}:{prev_checksum}"
            )
            computed = hashlib.sha256(checksum_input.encode()).hexdigest()[:32]
            if computed != row["checksum"]:
                broken.append(log_id)
                logger.warning(
                    "Checksum mismatch at %s: stored=%s, computed=%s",
                    log_id, row["checksum"], computed,
                )

            expected_prev = row["checksum"]

        return {
            "valid": len(broken) == 0,
            "entries_checked": len(rows),
            "first_broken_at": broken[0] if broken else None,
            "broken_entries": broken,
        }


    def close(self) -> None:
        self._pool.close_all()
