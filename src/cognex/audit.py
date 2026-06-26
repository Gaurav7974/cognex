"""Append-only audit log with tamper-evident hash chain.

Design
------
Each audit log entry contains:

1. **Per-entry checksum** — SHA-256 over
   ``log_id:event_type:session_id:payload_json:prev_checksum`` (first 32 hex
   chars).  This ties every entry to its predecessor.

2. **prev_checksum** — the checksum of the immediately preceding entry,
   chronologically.  The first entry ever uses the sentinel ``"GENESIS"``.

3. **Chain verification** (``verify_chain()``) — fetches entries in
   chronological order and walks the chain, re-computing each checksum and
   confirming that ``prev_checksum`` matches the previous entry's checksum.
   A missing or modified entry breaks every subsequent link, making
   selective-deletion attacks detectable.

The log is intentionally **append-only**: the ``append()`` method is the
only write path and it never updates or deletes rows.  The underlying
SQLite table has no ``DELETE`` permission in the application layer.
"""

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
    """sqlite3.Row does not support .get(); this shim provides that behaviour.

    Also handles pre-migration rows where the column may not exist at all
    (e.g., prev_checksum before migration v10 was applied).
    """
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


class AuditLog:
    """Append-only, hash-chained audit log.

    Every event type (session_start, unit_commit, outcome_feedback, …) is
    recorded here for a tamper-evident history of all system events.
    """

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

    # ── Write ─────────────────────────────────────────────────────────────

    def append(
        self,
        event_type: str,
        session_id: str | None = None,
        project: str | None = None,
        agent_id: str | None = None,
        payload: dict | None = None,
    ) -> str:
        """Append a new entry to the audit log.

        The entry's checksum is computed over its own fields **plus** the
        checksum of the previous entry, forming a tamper-evident chain.

        Returns:
            The ``log_id`` of the new entry, or ``""`` on failure (audit
            errors are non-fatal — the system continues operating).
        """
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

    # ── Read ──────────────────────────────────────────────────────────────

    def get_recent(
        self, project: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Return recent audit log entries (newest first).

        Args:
            project: Optional project filter.
            limit: Maximum rows to return.
        """
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

    # ── Verification ──────────────────────────────────────────────────────

    def verify_integrity(self, log_id: str) -> dict:
        """Verify the checksum of a single audit log entry.

        Returns a dict with ``valid`` (bool) plus diagnostic fields.
        """
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
        """Walk the hash chain and verify every link.

        Fetches up to *limit* entries in chronological (oldest-first) order
        and re-computes each entry's checksum, confirming that:

        1. The computed checksum matches the stored checksum.
        2. The entry's ``prev_checksum`` matches the previous entry's
           stored checksum (or ``"GENESIS"`` for the first entry).

        Any discrepancy indicates tampering (deletion or modification of a
        log entry).

        Returns:
            Dict with keys:
            - ``valid`` (bool) — True iff the entire scanned chain is intact.
            - ``entries_checked`` (int) — Number of entries verified.
            - ``first_broken_at`` (str | None) — ``log_id`` of the first
              broken link, or ``None`` if the chain is valid.
            - ``broken_entries`` (list[str]) — All broken ``log_id`` values.
        """
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

            # Verify chain link.
            if prev_checksum != expected_prev:
                broken.append(log_id)
                logger.warning(
                    "Chain break at %s: expected prev=%s, got %s",
                    log_id, expected_prev, prev_checksum,
                )
                # Don't abort — continue to find all breaks.

            # Verify the entry's own checksum.
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

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close all pooled database connections."""
        self._pool.close_all()
