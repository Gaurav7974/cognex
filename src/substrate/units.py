# CognitiveUnitStore - storage layer for Cognitive Units.

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import CognitiveUnit


class ConnectionPool:
    # Thread-local connection pool for SQLite (reused from store.py pattern).

    def __init__(self, db_path: Path, pool_size: int = 3):
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = __import__("threading").local()
        self._lock = __import__("threading").Lock()
        self._connections: list[sqlite3.Connection] = []
        self._init_pool()

    def _init_pool(self) -> None:
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._connections.append(conn)

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA wal_autocheckpoint = 100")
        conn.execute("PRAGMA cache_size=-32000")
        conn.execute("PRAGMA mmap_size=134217728")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    @contextmanager
    def get_connection(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            with self._lock:
                if self._connections:
                    conn = self._connections.pop(0)
                else:
                    conn = self._create_connection()
            self._local.conn = conn
        try:
            yield conn
        finally:
            pass

    def close_all(self) -> None:
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


class CognitiveUnitStore:
    # Storage for Cognitive Units and CHP handoff support.

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(".substrate/substrate.db")
        self._pool = ConnectionPool(self.db_path, pool_size=3)
        self._init_db()

    def _connect(self):
        return self._pool.get_connection()

    def close(self) -> None:
        self._pool.close_all()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cognitive_units (
                    unit_id TEXT PRIMARY KEY,
                    unit_type TEXT NOT NULL DEFAULT 'decision',
                    content TEXT NOT NULL,
                    rationale TEXT DEFAULT '',
                    scope TEXT DEFAULT '',
                    confidence REAL DEFAULT 1.0,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    session_id TEXT DEFAULT '',
                    project TEXT DEFAULT '',
                    override_count INTEGER DEFAULT 0,
                    last_verified TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_cu_project ON cognitive_units(project);
                CREATE INDEX IF NOT EXISTS idx_cu_scope ON cognitive_units(scope);
                CREATE INDEX IF NOT EXISTS idx_cu_type ON cognitive_units(unit_type);
                CREATE INDEX IF NOT EXISTS idx_cu_confidence ON cognitive_units(confidence DESC);
            """)

            # FTS5 virtual table on content + rationale
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_units_fts
                    USING fts5(content, rationale, content='cognitive_units', content_rowid='rowid')
                """)

                # Triggers to keep FTS in sync
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS cu_fts_insert AFTER INSERT ON cognitive_units BEGIN
                        INSERT INTO cognitive_units_fts(rowid, content, rationale)
                        VALUES (new.rowid, new.content, new.rationale);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS cu_fts_update AFTER UPDATE ON cognitive_units BEGIN
                        UPDATE cognitive_units_fts
                        SET content=new.content, rationale=new.rationale
                        WHERE rowid=old.rowid;
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS cu_fts_delete AFTER DELETE ON cognitive_units BEGIN
                        DELETE FROM cognitive_units_fts WHERE rowid=old.rowid;
                    END
                """)
            except Exception:
                pass

    def save(self, unit: CognitiveUnit) -> CognitiveUnit:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cognitive_units
                (unit_id, unit_type, content, rationale, scope, confidence,
                 tags, created_at, session_id, project, override_count, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    unit.unit_id,
                    unit.unit_type,
                    unit.content,
                    unit.rationale,
                    unit.scope,
                    unit.confidence,
                    json.dumps(list(unit.tags)),
                    unit.created_at.isoformat(),
                    unit.session_id,
                    unit.project,
                    unit.override_count,
                    unit.last_verified.isoformat() if unit.last_verified else None,
                ),
            )
        return unit

    def get(self, unit_id: str) -> CognitiveUnit | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cognitive_units WHERE unit_id = ?", (unit_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_unit(row)

    def search(
        self,
        query: str = "",
        project: str = "",
        unit_type: str | None = None,
        limit: int = 20,
    ) -> list[CognitiveUnit]:
        with self._connect() as conn:
            # Try FTS5 if query provided
            if query:
                try:
                    return self._search_fts5(conn, query, project, unit_type, limit)
                except Exception:
                    pass

            # Fallback to LIKE search
            return self._search_like(conn, query, project, unit_type, limit)

    def _search_fts5(
        self,
        conn: sqlite3.Connection,
        query: str,
        project: str,
        unit_type: str | None,
        limit: int,
    ) -> list[CognitiveUnit]:
        # Escape special FTS5 characters
        for char in ['"', "'", "(", ")", "*", "-", "+", ":", "^", "{", "}", "[", "]"]:
            query = query.replace(char, " ")
        words = query.split()
        if not words:
            return []
        fts_query = " OR ".join(f'"{w}"*' for w in words if w)

        conditions = ["cognitive_units_fts MATCH ?"]
        params: list = [fts_query]

        if project:
            conditions.append("cu.project = ?")
            params.append(project)
        if unit_type:
            conditions.append("cu.unit_type = ?")
            params.append(unit_type)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT cu.* FROM cognitive_units cu
            JOIN cognitive_units_fts ON cognitive_units_fts.rowid = cu.rowid
            WHERE {where}
            ORDER BY cu.confidence DESC
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_unit(r) for r in rows]

    def _search_like(
        self,
        conn: sqlite3.Connection,
        query: str,
        project: str,
        unit_type: str | None,
        limit: int,
    ) -> list[CognitiveUnit]:
        conditions = []
        params: list = []

        if query:
            conditions.append("(content LIKE ? OR rationale LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if project:
            conditions.append("project = ?")
            params.append(project)
        if unit_type:
            conditions.append("unit_type = ?")
            params.append(unit_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM cognitive_units WHERE {where} ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_unit(r) for r in rows]

    def mark_overridden(self, unit_id: str) -> None:
        # Mark a unit as contradicted and decay confidence by 0.2.
        with self._connect() as conn:
            conn.execute(
                """UPDATE cognitive_units
                SET override_count = override_count + 1,
                    confidence = MAX(0.0, confidence - 0.2)
                WHERE unit_id = ?""",
                (unit_id,),
            )

    def verify(self, unit_id: str) -> None:
        # Confirm a unit still holds and update last_verified.
        with self._connect() as conn:
            conn.execute(
                "UPDATE cognitive_units SET last_verified = ? WHERE unit_id = ?",
                (datetime.now(timezone.utc).isoformat(), unit_id),
            )

    def get_bundle(self, project: str, scope: str | None = None) -> list[CognitiveUnit]:
        # Get active units for project/scope ordered by confidence DESC.
        with self._connect() as conn:
            conditions = ["project = ?"]
            params: list = [project]

            if scope:
                conditions.append("scope = ?")
                params.append(scope)

            where = " AND ".join(conditions)
            sql = (
                f"SELECT * FROM cognitive_units WHERE {where} ORDER BY confidence DESC"
            )
            rows = conn.execute(sql, params).fetchall()

        return [self._row_to_unit(r) for r in rows]

    @staticmethod
    def _row_to_unit(row: sqlite3.Row) -> CognitiveUnit:
        return CognitiveUnit(
            unit_id=row["unit_id"],
            unit_type=row["unit_type"],
            content=row["content"],
            rationale=row["rationale"],
            scope=row["scope"],
            confidence=row["confidence"],
            tags=tuple(json.loads(row["tags"])),
            created_at=datetime.fromisoformat(row["created_at"]),
            session_id=row["session_id"],
            project=row["project"],
            override_count=row["override_count"],
            last_verified=datetime.fromisoformat(row["last_verified"])
            if row["last_verified"]
            else None,
        )
