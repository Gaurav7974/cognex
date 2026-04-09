"""SQLite-backed persistent memory store."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .migrations import run_migrations
from .models import MemoryEntry, MemoryScope, MemoryType, SessionSnapshot


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
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None


def execute_with_retry(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | None = None,
    max_retries: int = 3,
) -> sqlite3.Cursor:
    """Execute SQL with exponential backoff retry for locked database.

    Args:
        conn: SQLite connection
        sql: SQL statement to execute
        params: Optional parameters for the SQL statement
        max_retries: Maximum number of retry attempts

    Returns:
        Cursor from successful execution

    Raises:
        Last exception if all retries fail
    """
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(max_retries):
        try:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)
        except sqlite3.OperationalError as e:
            last_error = e
            is_lock_error = "locked" in str(e).lower()
            is_last_attempt = attempt >= max_retries - 1
            if is_lock_error and not is_last_attempt:
                # Exponential backoff: 100ms, 200ms, 400ms...
                time.sleep(0.1 * (2**attempt))
                continue
            raise e
    # All retries exhausted - raise the last error
    assert last_error is not None  # Type narrowing
    raise last_error


class MemoryStore:
    """Persistent storage for memories and session snapshots.

    Uses SQLite — zero dependencies, single file, works everywhere.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(".substrate/memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Use connection pool (2-3 connections)
        self._pool = ConnectionPool(self.db_path, pool_size=3)
        self._init_db()

    # ── Internal ──────────────────────────────────────────────

    def _connect(self):
        """Get a connection from the pool. Returns a context manager."""
        return self._pool.get_connection()

    def close(self) -> None:
        """Close any open connections (important for cleanup on Windows)."""
        # Close pool connections
        self._pool.close_all()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'private',
                    content TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    relevance_score REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    access_count INTEGER DEFAULT 0,
                    project TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_mem_project ON memories(project);
                CREATE INDEX IF NOT EXISTS idx_mem_relevance ON memories(relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at DESC);

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    key_decisions TEXT DEFAULT '[]',
                    tools_used TEXT DEFAULT '[]',
                    errors_encountered TEXT DEFAULT '[]',
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    memory_ids TEXT DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
                CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
            """)

            # FTS5 full-text search index
            # Check if FTS5 is available before creating
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
                    USING fts5(
                        content,
                        context,
                        type,
                        project,
                        tags,
                        content='memories',
                        content_rowid='rowid'
                    )
                """)

                # Populate FTS index from existing memories (only if empty)
                fts_count = conn.execute(
                    "SELECT COUNT(*) FROM memories_fts"
                ).fetchone()[0]
                if fts_count == 0:
                    conn.execute("""
                        INSERT OR IGNORE INTO memories_fts(rowid, content, context, type, project, tags)
                        SELECT rowid, content, context, type, project, tags 
                        FROM memories
                    """)

                # Triggers to keep FTS index in sync automatically
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_insert
                    AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, content, context, type, project, tags)
                        VALUES (new.rowid, new.content, new.context, new.type, new.project, new.tags);
                    END
                """)

                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_update
                    AFTER UPDATE ON memories BEGIN
                        UPDATE memories_fts 
                        SET content=new.content, context=new.context,
                            type=new.type, project=new.project, tags=new.tags
                        WHERE rowid=old.rowid;
                    END
                """)

                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_delete
                    AFTER DELETE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid=old.rowid;
                    END
                """)
            except Exception:
                # FTS5 not available - continue without it
                pass

            # Run schema migrations for upgrades
            run_migrations(conn)

    # ── Memory CRUD ───────────────────────────────────────────

    def save(self, memory: MemoryEntry) -> MemoryEntry:
        """Save or update a memory entry."""
        with self._connect() as conn:
            execute_with_retry(
                conn,
                """
                INSERT OR REPLACE INTO memories
                (id, type, scope, content, context, relevance_score,
                 created_at, last_accessed, access_count, project, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    memory.id,
                    memory.type.value,
                    memory.scope.value,
                    memory.content,
                    memory.context,
                    memory.relevance_score,
                    memory.created_at.isoformat(),
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.access_count,
                    memory.project,
                    json.dumps(memory.tags),
                ),
            )
        return memory

    def save_many(self, memories: list[MemoryEntry]) -> int:
        """Bulk save. Returns count saved."""
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO memories
                (id, type, scope, content, context, relevance_score,
                 created_at, last_accessed, access_count, project, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        m.id,
                        m.type.value,
                        m.scope.value,
                        m.content,
                        m.context,
                        m.relevance_score,
                        m.created_at.isoformat(),
                        m.last_accessed.isoformat() if m.last_accessed else None,
                        m.access_count,
                        m.project,
                        json.dumps(m.tags),
                    )
                    for m in memories
                ],
            )
        return len(memories)

    def get(self, memory_id: str) -> MemoryEntry | None:
        """Get a single memory by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        if not row:
            return None
        entry = self._row_to_memory(row)
        # Touch it — accessing boosts relevance
        touched = entry.touch()
        self.save(touched)
        return touched

    def delete(self, memory_id: str) -> bool:
        """Delete a memory. Returns True if it existed."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    def count(self) -> int:
        """Total memories stored."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0]

    # ── Search & Retrieval ────────────────────────────────────

    def _fts5_available(self, conn: sqlite3.Connection) -> bool:
        """Check if FTS5 table exists and is usable."""
        try:
            conn.execute("SELECT 1 FROM memories_fts LIMIT 1")
            return True
        except sqlite3.OperationalError:
            return False

    def search(
        self,
        query: str = "",
        memory_type: MemoryType | None = None,
        project: str = "",
        scope: MemoryScope | None = None,
        tags: tuple[str, ...] = (),
        limit: int = 20,
        min_relevance: float = 0.0,
    ) -> list[MemoryEntry]:
        """Find memories matching criteria, ordered by relevance.

        Uses FTS5 BM25 ranking when available, falls back to LIKE search.
        """
        with self._connect() as conn:
            # Try FTS5 search if query provided and FTS5 available
            if query and self._fts5_available(conn):
                return self._search_fts5(
                    conn, query, memory_type, project, scope, tags, limit, min_relevance
                )

            # Fallback to LIKE search
            return self._search_like(
                conn, query, memory_type, project, scope, tags, limit, min_relevance
            )

    def _search_fts5(
        self,
        conn: sqlite3.Connection,
        query: str,
        memory_type: MemoryType | None,
        project: str,
        scope: MemoryScope | None,
        tags: tuple[str, ...],
        limit: int,
        min_relevance: float,
    ) -> list[MemoryEntry]:
        """FTS5 BM25 ranked search."""
        try:
            # Build filter conditions
            conditions = []
            params: list = []

            if memory_type:
                conditions.append("m.type = ?")
                params.append(memory_type.value)
            if project:
                conditions.append("m.project = ?")
                params.append(project)
            if scope:
                conditions.append("m.scope = ?")
                params.append(scope.value)
            if min_relevance > 0:
                conditions.append("m.relevance_score >= ?")
                params.append(min_relevance)
            if tags:
                for tag in tags:
                    conditions.append("m.tags LIKE ?")
                    params.append(f"%{tag}%")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # Escape special FTS5 characters and prepare query
            fts_query = self._escape_fts5_query(query)

            sql = f"""
                SELECT 
                    m.*,
                    -bm25(memories_fts) as search_score
                FROM memories_fts
                JOIN memories m ON memories_fts.rowid = m.rowid
                WHERE memories_fts MATCH ? AND {where_clause}
                ORDER BY search_score DESC
                LIMIT ?
            """
            params = [fts_query] + params + [limit]

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_memory(r) for r in rows]

        except sqlite3.OperationalError:
            # FTS query failed - fall back to LIKE
            return self._search_like(
                conn, query, memory_type, project, scope, tags, limit, min_relevance
            )

    def _escape_fts5_query(self, query: str) -> str:
        """Escape special FTS5 characters and format query."""
        # Remove FTS5 special characters that could cause syntax errors
        special_chars = [
            '"',
            "'",
            "(",
            ")",
            "*",
            "-",
            "+",
            ":",
            "^",
            "{",
            "}",
            "[",
            "]",
        ]
        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, " ")

        # Split into words and join with OR for broader matching
        words = escaped.split()
        if not words:
            return '""'  # Empty query

        # Use prefix matching for each word
        return " OR ".join(f'"{word}"*' for word in words if word)

    def _search_like(
        self,
        conn: sqlite3.Connection,
        query: str,
        memory_type: MemoryType | None,
        project: str,
        scope: MemoryScope | None,
        tags: tuple[str, ...],
        limit: int,
        min_relevance: float,
    ) -> list[MemoryEntry]:
        """Fallback LIKE search."""
        conditions = []
        params: list = []

        if memory_type:
            conditions.append("type = ?")
            params.append(memory_type.value)
        if project:
            conditions.append("project = ?")
            params.append(project)
        if scope:
            conditions.append("scope = ?")
            params.append(scope.value)
        if min_relevance > 0:
            conditions.append("relevance_score >= ?")
            params.append(min_relevance)
        if tags:
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
        if query:
            # Split query into words — match if ANY word is found
            words = query.split()
            word_conditions = []
            for word in words:
                word_conditions.append("(content LIKE ? OR context LIKE ?)")
                params.extend([f"%{word}%", f"%{word}%"])
            conditions.append("(" + " OR ".join(word_conditions) + ")")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM memories WHERE {where} ORDER BY relevance_score DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Most recently created memories."""
        return self.search(limit=limit)

    def get_by_project(self, project: str, limit: int = 50) -> list[MemoryEntry]:
        """All memories for a specific project."""
        return self.search(project=project, limit=limit)

    def get_by_type(self, mtype: MemoryType, limit: int = 50) -> list[MemoryEntry]:
        """All memories of a specific type."""
        return self.search(memory_type=mtype, limit=limit)

    def decay_all(self, factor: float = 0.95) -> int:
        """Age all memories. Returns count decayed."""
        with self._connect() as conn:
            execute_with_retry(
                conn,
                "UPDATE memories SET relevance_score = relevance_score * ? WHERE relevance_score > 0.01",
                (factor,),
            )
            # Clean up memories that faded to nothing
            cur = execute_with_retry(
                conn, "DELETE FROM memories WHERE relevance_score < 0.01"
            )
        return cur.rowcount

    # ── Session Snapshots ─────────────────────────────────────

    def save_session(self, session: SessionSnapshot) -> SessionSnapshot:
        with self._connect() as conn:
            execute_with_retry(
                conn,
                """
                INSERT OR REPLACE INTO sessions
                (session_id, project, summary, key_decisions, tools_used,
                 errors_encountered, started_at, ended_at, input_tokens,
                 output_tokens, memory_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session.session_id,
                    session.project,
                    session.summary,
                    json.dumps(session.key_decisions),
                    json.dumps(session.tools_used),
                    json.dumps(session.errors_encountered),
                    session.started_at.isoformat(),
                    session.ended_at.isoformat() if session.ended_at else None,
                    session.input_tokens,
                    session.output_tokens,
                    json.dumps(session.memory_ids_extracted),
                ),
            )
        return session

    def get_session(self, session_id: str) -> SessionSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return SessionSnapshot(
            session_id=row["session_id"],
            project=row["project"],
            summary=row["summary"],
            key_decisions=tuple(json.loads(row["key_decisions"])),
            tools_used=tuple(json.loads(row["tools_used"])),
            errors_encountered=tuple(json.loads(row["errors_encountered"])),
            started_at=__import__("datetime").datetime.fromisoformat(row["started_at"]),
            ended_at=__import__("datetime").datetime.fromisoformat(row["ended_at"])
            if row["ended_at"]
            else None,
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            memory_ids_extracted=tuple(json.loads(row["memory_ids"])),
        )

    def get_sessions(self, project: str = "", limit: int = 20) -> list[SessionSnapshot]:
        with self._connect() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project = ? ORDER BY started_at DESC LIMIT ?",
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [
            SessionSnapshot(
                session_id=r["session_id"],
                project=r["project"],
                summary=r["summary"],
                key_decisions=tuple(json.loads(r["key_decisions"])),
                tools_used=tuple(json.loads(r["tools_used"])),
                errors_encountered=tuple(json.loads(r["errors_encountered"])),
                started_at=__import__("datetime").datetime.fromisoformat(
                    r["started_at"]
                ),
                ended_at=__import__("datetime").datetime.fromisoformat(r["ended_at"])
                if r["ended_at"]
                else None,
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                memory_ids_extracted=tuple(json.loads(r["memory_ids"])),
            )
            for r in rows
        ]

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryEntry:
        from datetime import datetime as _dt

        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            scope=MemoryScope(row["scope"]),
            content=row["content"],
            context=row["context"],
            relevance_score=row["relevance_score"],
            created_at=_dt.fromisoformat(row["created_at"]),
            last_accessed=_dt.fromisoformat(row["last_accessed"])
            if row["last_accessed"]
            else None,
            access_count=row["access_count"],
            project=row["project"],
            tags=tuple(json.loads(row["tags"])),
        )
