"""Append-only audit log for tracking system events and state changes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ConnectionPool:
    """Thread-local connection pool for SQLite.
    
    Reuses connections across calls for better performance.
    Maintains a small pool (2-3 connections) with WAL mode and busy_timeout.
    """

    def __init__(self, db_path: Path, pool_size: int = 3):
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: list[sqlite3.Connection] = []
        self._init_pool()

    def _init_pool(self) -> None:
        """Initialize the connection pool."""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._connections.append(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new connection with pragmas."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Concurrency pragmas for multi-client access
        conn.execute("PRAGMA busy_timeout = 10000")  # Wait up to 10s for locks
        conn.execute("PRAGMA journal_mode = WAL")  # Write-ahead logging
        conn.execute("PRAGMA wal_autocheckpoint = 100")  # Checkpoint every 100 pages
        # Performance pragmas for faster queries
        conn.execute("PRAGMA cache_size=-32000")  # 32MB cache
        conn.execute("PRAGMA mmap_size=134217728")  # 128MB mmap
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool, yield it, return it to pool."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            # Get connection from pool
            with self._lock:
                if self._connections:
                    conn = self._connections.pop(0)
                else:
                    # Pool empty - create new connection
                    conn = self._create_connection()

            self._local.conn = conn

        try:
            yield conn
        finally:
            # Connection stays in _local for reuse
            pass

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()


class AuditLog:
    """Append-only audit log for tracking system events.
    
    All entries are immutable once written. Never UPDATE or DELETE.
    Each entry includes a checksum for integrity verification.
    """

    def __init__(self, db_path: str | Path | None = None):
        """Initialize AuditLog with database connection pool.
        
        Args:
            db_path: Path to SQLite database. Defaults to current .substrate/substrate.db
        """
        if db_path is None:
            db_path = Path(".substrate") / "substrate.db"
        elif isinstance(db_path, str):
            db_path = Path(db_path)

        self.db_path = db_path
        self._pool = ConnectionPool(db_path, pool_size=3)

    def append(
        self,
        event_type: str,
        session_id: str | None = None,
        project: str | None = None,
        agent_id: str | None = None,
        payload: dict | None = None,
    ) -> str:
        """Append a new audit log entry (append-only).
        
        Args:
            event_type: Type of event (e.g., 'session_start', 'unit_commit')
            session_id: Associated session ID (optional)
            project: Associated project name (optional)
            agent_id: Associated agent ID (optional)
            payload: Event data as dict (optional)
        
        Returns:
            log_id: Unique identifier for the log entry (empty string if DB is busy)
        """
        log_id = uuid4().hex[:16]
        payload = payload or {}
        
        # Compute checksum: sha256(log_id:event_type:session_id:payload_json)[:32]
        checksum_input = f"{log_id}:{event_type}:{session_id or ''}:{json.dumps(payload, sort_keys=True)}"
        checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:32]
        
        created_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload)
        
        try:
            with self._pool.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log 
                    (log_id, event_type, session_id, project, agent_id, payload, created_at, checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (log_id, event_type, session_id, project, agent_id, payload_json, created_at, checksum),
                )
                conn.commit()
        except Exception as e:
            # Gracefully handle DB lock or other errors - audit is non-critical
            # Log to stderr if needed, but don't raise
            import sys
            print(f"Warning: Failed to log audit event {event_type}: {e}", file=sys.stderr)
            return ""  # Return empty string on failure
        
        return log_id

    def get_recent(self, project: str | None = None, limit: int = 50) -> list[dict]:
        """Get recent audit log entries.
        
        Args:
            project: Filter by project name (optional). If None, returns all.
            limit: Maximum number of entries to return (default 50)
        
        Returns:
            List of audit log entries (newest first)
        """
        with self._pool.get_connection() as conn:
            if project:
                cursor = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, project, agent_id, payload, created_at, checksum
                    FROM audit_log
                    WHERE project = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (project, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT log_id, event_type, session_id, project, agent_id, payload, created_at, checksum
                    FROM audit_log
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            
            rows = cursor.fetchall()
            entries = []
            for row in rows:
                entries.append({
                    "log_id": row["log_id"],
                    "event_type": row["event_type"],
                    "session_id": row["session_id"],
                    "project": row["project"],
                    "agent_id": row["agent_id"],
                    "payload": json.loads(row["payload"]),
                    "created_at": row["created_at"],
                    "checksum": row["checksum"],
                })
            
            return entries

    def verify_integrity(self, log_id: str) -> dict:
        """Verify integrity of an audit log entry by recomputing its checksum.
        
        Args:
            log_id: The log_id to verify
        
        Returns:
            dict with keys:
                - log_id: The log ID verified
                - valid: True if checksum matches, False otherwise
                - stored_checksum: Checksum stored in database
                - computed_checksum: Newly computed checksum
                - event_type: Event type (if found)
                - session_id: Session ID (if found)
                - payload: Payload dict (if found)
        """
        with self._pool.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT log_id, event_type, session_id, payload, checksum
                FROM audit_log
                WHERE log_id = ?
                """,
                (log_id,),
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    "log_id": log_id,
                    "valid": False,
                    "stored_checksum": None,
                    "computed_checksum": None,
                    "error": f"Log entry {log_id} not found",
                }
            
            # Recompute checksum using same formula as append()
            payload = json.loads(row["payload"])
            checksum_input = f"{row['log_id']}:{row['event_type']}:{row['session_id'] or ''}:{json.dumps(payload, sort_keys=True)}"
            computed_checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:32]
            
            return {
                "log_id": log_id,
                "valid": computed_checksum == row["checksum"],
                "stored_checksum": row["checksum"],
                "computed_checksum": computed_checksum,
                "event_type": row["event_type"],
                "session_id": row["session_id"],
                "payload": payload,
            }

    def close(self) -> None:
        """Close all database connections."""
        self._pool.close_all()
