"""Shared SQLite connection pool and retry utilities.

This module is the single source of truth for SQLite connection
management across all Cognex engine modules. Previously,
ConnectionPool was copy-pasted into store.py, audit.py, and units.py.
Centralising here eliminates drift between implementations and ensures
every connection gets the same WAL-mode, busy-timeout, and cache
pragmas regardless of which subsystem opens it.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class ConnectionPool:
    """Thread-local SQLite connection pool.

    Design goals:
    - Each OS thread gets its own connection (thread-local storage)
      to avoid SQLite's check_same_thread restriction while still
      reusing connections across function calls within a thread.
    - A small pool of pre-warmed connections is handed out on first
      access from each thread; overflow threads create fresh connections.
    - All connections share the same pragma configuration: WAL mode,
      10-second busy timeout, 32 MB page cache, and memory temp store.

    Args:
        db_path: Absolute path to the SQLite database file.
        pool_size: Number of connections to pre-create. Threads beyond
            this count will create their own connection on demand.
    """

    def __init__(self, db_path: Path, pool_size: int = 3) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: list[sqlite3.Connection] = []
        self._init_pool()

    # ── Internal ──────────────────────────────────────────────────────────

    def _init_pool(self) -> None:
        """Pre-create pool_size connections."""
        for _ in range(self.pool_size):
            self._connections.append(self._create_connection())

    def _create_connection(self) -> sqlite3.Connection:
        """Create a single connection with all required pragmas applied."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Concurrency: allow readers while a writer holds the WAL lock.
        conn.execute("PRAGMA busy_timeout = 10000")   # wait up to 10 s on lock
        conn.execute("PRAGMA journal_mode = WAL")      # write-ahead logging
        conn.execute("PRAGMA wal_autocheckpoint = 100")# checkpoint every 100 pages
        # Performance: larger page cache and memory-backed temp tables.
        conn.execute("PRAGMA cache_size = -32000")     # 32 MB page cache
        conn.execute("PRAGMA mmap_size = 134217728")   # 128 MB memory-mapped I/O
        conn.execute("PRAGMA synchronous = NORMAL")    # safe with WAL
        conn.execute("PRAGMA temp_store = MEMORY")     # temp tables in RAM
        # Referential integrity for junction tables (tags, embeddings, etc.)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Public API ────────────────────────────────────────────────────────

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields a thread-local connection.

        The connection is kept alive in thread-local storage and reused
        across calls within the same thread, avoiding reconnect overhead.
        Threads that have no pre-warmed connection available create a
        fresh one on demand.
        """
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            with self._lock:
                conn = (
                    self._connections.pop(0)
                    if self._connections
                    else self._create_connection()
                )
            self._local.conn = conn
        yield conn
        # Connection intentionally stays in _local for reuse.

    def close_all(self) -> None:
        """Close every connection managed by this pool.

        Should be called on server shutdown or when the database is no
        longer needed (e.g., in tests).  Idempotent and exception-safe.
        """
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()

        # Also close the thread-local connection if this thread has one.
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None


def execute_with_retry(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | list | None = None,
    max_retries: int = 3,
) -> sqlite3.Cursor:
    """Execute SQL with exponential-backoff retry on lock errors.

    SQLite's busy_timeout pragma handles most lock contention at the OS
    level, but very short-lived locks can still slip through.  This
    function adds a Python-level retry loop with exponential backoff
    (100 ms → 200 ms → 400 ms …) as a second line of defence.

    Args:
        conn: An open SQLite connection.
        sql: The SQL statement to execute.
        params: Optional positional parameters.
        max_retries: Maximum number of attempts before re-raising.

    Returns:
        The ``sqlite3.Cursor`` from the successful execution.

    Raises:
        sqlite3.OperationalError: If all retries are exhausted or the
            error is not a lock-related one.
    """
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(max_retries):
        try:
            return conn.execute(sql, params) if params else conn.execute(sql)
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))  # 100 ms, 200 ms, 400 ms …
                continue
            raise
    # Unreachable in practice, but satisfies the type checker.
    assert last_error is not None
    raise last_error
