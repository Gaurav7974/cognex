"""SQLite-backed persistent memory store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import MemoryEntry, MemoryScope, MemoryType, SessionSnapshot


class MemoryStore:
    """Persistent storage for memories and session snapshots.

    Uses SQLite — zero dependencies, single file, works everywhere.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(".substrate/memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Internal ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """Close any open connections (important for cleanup on Windows)."""
        # SQLite connections are per-call, so this is a no-op,
        # but we keep the API for future connection pooling.
        pass

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

    # ── Memory CRUD ───────────────────────────────────────────

    def save(self, memory: MemoryEntry) -> MemoryEntry:
        """Save or update a memory entry."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories
                (id, type, scope, content, context, relevance_score,
                 created_at, last_accessed, access_count, project, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id, memory.type.value, memory.scope.value,
                memory.content, memory.context, memory.relevance_score,
                memory.created_at.isoformat(),
                memory.last_accessed.isoformat() if memory.last_accessed else None,
                memory.access_count, memory.project,
                json.dumps(memory.tags),
            ))
        return memory

    def save_many(self, memories: list[MemoryEntry]) -> int:
        """Bulk save. Returns count saved."""
        with self._connect() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO memories
                (id, type, scope, content, context, relevance_score,
                 created_at, last_accessed, access_count, project, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    m.id, m.type.value, m.scope.value,
                    m.content, m.context, m.relevance_score,
                    m.created_at.isoformat(),
                    m.last_accessed.isoformat() if m.last_accessed else None,
                    m.access_count, m.project,
                    json.dumps(m.tags),
                )
                for m in memories
            ])
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
        """Find memories matching criteria, ordered by relevance."""
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

        with self._connect() as conn:
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
            conn.execute(
                "UPDATE memories SET relevance_score = relevance_score * ? WHERE relevance_score > 0.01",
                (factor,),
            )
            # Clean up memories that faded to nothing
            cur = conn.execute("DELETE FROM memories WHERE relevance_score < 0.01")
        return cur.rowcount

    # ── Session Snapshots ─────────────────────────────────────

    def save_session(self, session: SessionSnapshot) -> SessionSnapshot:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, project, summary, key_decisions, tools_used,
                 errors_encountered, started_at, ended_at, input_tokens,
                 output_tokens, memory_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id, session.project, session.summary,
                json.dumps(session.key_decisions),
                json.dumps(session.tools_used),
                json.dumps(session.errors_encountered),
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.input_tokens, session.output_tokens,
                json.dumps(session.memory_ids_extracted),
            ))
        return session

    def get_session(self, session_id: str) -> SessionSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return SessionSnapshot(
            session_id=row["session_id"], project=row["project"],
            summary=row["summary"],
            key_decisions=tuple(json.loads(row["key_decisions"])),
            tools_used=tuple(json.loads(row["tools_used"])),
            errors_encountered=tuple(json.loads(row["errors_encountered"])),
            started_at=__import__("datetime").datetime.fromisoformat(row["started_at"]),
            ended_at=__import__("datetime").datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
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
                session_id=r["session_id"], project=r["project"],
                summary=r["summary"],
                key_decisions=tuple(json.loads(r["key_decisions"])),
                tools_used=tuple(json.loads(r["tools_used"])),
                errors_encountered=tuple(json.loads(r["errors_encountered"])),
                started_at=__import__("datetime").datetime.fromisoformat(r["started_at"]),
                ended_at=__import__("datetime").datetime.fromisoformat(r["ended_at"]) if r["ended_at"] else None,
                input_tokens=r["input_tokens"], output_tokens=r["output_tokens"],
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
            last_accessed=_dt.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
            access_count=row["access_count"],
            project=row["project"],
            tags=tuple(json.loads(row["tags"])),
        )
