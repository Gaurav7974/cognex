
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class ConnectionPool:

    def __init__(self, db_path: Path, pool_size: int = 3) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: list[sqlite3.Connection] = []
        self._init_pool()


    def _init_pool(self) -> None:
        for _ in range(self.pool_size):
            self._connections.append(self._create_connection())

    def _create_connection(self) -> sqlite3.Connection:
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


    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
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
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()

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
