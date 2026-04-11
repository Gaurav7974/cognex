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

                CREATE TABLE IF NOT EXISTS cognitive_unit_deltas (
                    delta_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL,
                    changed_field TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL,
                    reason TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_cu_project ON cognitive_units(project);
                CREATE INDEX IF NOT EXISTS idx_cu_scope ON cognitive_units(scope);
                CREATE INDEX IF NOT EXISTS idx_cu_type ON cognitive_units(unit_type);
                CREATE INDEX IF NOT EXISTS idx_cu_confidence ON cognitive_units(confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_cud_unit_id ON cognitive_unit_deltas(unit_id);
                CREATE INDEX IF NOT EXISTS idx_cud_changed_at ON cognitive_unit_deltas(changed_at);
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

    def mark_overridden(
        self,
        unit_id: str,
        changed_field: str = "confidence",
        old_value: str | None = None,
        new_value: str | None = None,
        changed_by: str = "",
        reason: str = "auto_decay",
    ) -> None:
        # Mark a unit as contradicted and decay confidence by 0.2, write delta record.
        with self._connect() as conn:
            # Get current unit for old_value if not provided
            unit = self.get(unit_id)
            if not unit:
                return

            if old_value is None and changed_field == "confidence":
                old_value = str(unit.confidence)
            if new_value is None and changed_field == "confidence":
                new_value = str(max(0.0, unit.confidence - 0.2))

            # Write delta record
            import uuid

            delta_id = str(uuid.uuid4().hex)[:12]
            conn.execute(
                """INSERT INTO cognitive_unit_deltas
                (delta_id, unit_id, changed_field, old_value, new_value, changed_by, changed_at, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    delta_id,
                    unit_id,
                    changed_field,
                    old_value,
                    new_value,
                    changed_by,
                    datetime.now(timezone.utc).isoformat(),
                    reason,
                ),
            )

            # Update unit
            conn.execute(
                """UPDATE cognitive_units
                SET override_count = override_count + 1,
                    confidence = MAX(0.0, confidence - 0.2)
                WHERE unit_id = ?""",
                (unit_id,),
            )

    def get_deltas(self, unit_id: str) -> list[dict]:
        # Get full change history for a unit.
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT delta_id, changed_field, old_value, new_value, changed_by, changed_at, reason
                FROM cognitive_unit_deltas
                WHERE unit_id = ?
                ORDER BY changed_at DESC""",
                (unit_id,),
            ).fetchall()
        return [
            {
                "delta_id": r["delta_id"],
                "changed_field": r["changed_field"],
                "old_value": r["old_value"],
                "new_value": r["new_value"],
                "changed_by": r["changed_by"],
                "changed_at": r["changed_at"],
                "reason": r["reason"],
            }
            for r in rows
        ]

    def check_staleness(self, unit_id: str) -> float:
        # Compute staleness score for a unit.
        unit = self.get(unit_id)
        if not unit:
            return 1.0

        # Base staleness from overrides
        base_staleness = min(1.0, unit.override_count * 0.2)

        # Age penalty
        age_penalty = 0.0
        if unit.last_verified:
            days_since_verified = (datetime.now(timezone.utc) - unit.last_verified).days
            if days_since_verified > 7:
                weeks_over = (days_since_verified - 7) // 7
                age_penalty = min(0.4, weeks_over * 0.1)

        total_staleness = base_staleness + age_penalty

        # If confidence too low, always stale
        if unit.confidence < 0.3:
            return 1.0

        return min(1.0, total_staleness)

    def decay_stale_units(self, project: str, threshold: float = 0.8) -> int:
        # Mark all units above staleness threshold as overridden.
        with self._connect() as conn:
            # Get all units for project
            rows = conn.execute(
                "SELECT unit_id FROM cognitive_units WHERE project = ?", (project,)
            ).fetchall()

            count = 0
            for row in rows:
                unit_id = row["unit_id"]
                staleness = self.check_staleness(unit_id)
                if staleness > threshold:
                    self.mark_overridden(unit_id, reason="auto_decay")
                    count += 1
            return count

    def verify(self, unit_id: str) -> None:
        # Confirm a unit still holds and update last_verified.
        with self._connect() as conn:
            conn.execute(
                "UPDATE cognitive_units SET last_verified = ? WHERE unit_id = ?",
                (datetime.now(timezone.utc).isoformat(), unit_id),
            )

    def get_bundle(
        self, project: str, scope: str | None = None, include_stale: bool = False
    ) -> list[CognitiveUnit]:
        # Get active units for project/scope ordered by confidence DESC, excluding stale by default.
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

        units = [self._row_to_unit(r) for r in rows]

        if not include_stale:
            units = [u for u in units if self.check_staleness(u.unit_id) <= 0.8]

        return units

    def get_relevant_units(
        self,
        query: str,
        project: str,
        task_context: str,
        limit: int = 10,
        include_stale: bool = False,
    ) -> list[CognitiveUnit]:
        # FTS search with relevance scoring.
        if not query:
            return []

        with self._connect() as conn:
            # Escape FTS characters
            for char in [
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
            ]:
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

            where = " AND ".join(conditions)
            sql = f"""
                SELECT cu.*, bm25(cognitive_units_fts) as bm25_score
                FROM cognitive_units cu
                JOIN cognitive_units_fts ON cognitive_units_fts.rowid = cu.rowid
                WHERE {where}
            """

            rows = conn.execute(sql, params).fetchall()

        units = []
        now = datetime.now(timezone.utc)
        seven_days_ago = (
            now.replace(day=now.day - 7)
            if now.day > 7
            else now.replace(month=now.month - 1, day=28)
        )

        for row in rows:
            unit = self._row_to_unit(row)

            # Skip stale unless included
            if not include_stale and self.check_staleness(unit.unit_id) > 0.8:
                continue

            # Compute composite score
            bm25_score = abs(row["bm25_score"])  # bm25 is negative, make positive
            score = bm25_score * unit.confidence

            # Recency boost
            if unit.last_verified and unit.last_verified > seven_days_ago:
                score *= 1.3

            # Scope match boost
            if task_context and unit.scope == task_context:
                score *= 1.5

            unit._relevance_score = score  # Add temporary attribute
            units.append(unit)

        # Sort by score descending, limit
        units.sort(key=lambda u: getattr(u, "_relevance_score", 0), reverse=True)
        return units[:limit]

    def export_snapshot(
        self, project: str, session_summary: str, scope: str | None = None
    ) -> dict:
        # Export structured cognitive snapshot.
        import uuid

        # Get all units for project/scope
        all_units = self.get_bundle(project, scope, include_stale=True)
        total_units = len(all_units)

        # Categorize units
        task_states = [u for u in all_units if u.unit_type == "task_state"]
        decisions = [
            u for u in all_units if u.unit_type == "decision" and u.confidence > 0.5
        ]
        constraints = [u for u in all_units if u.unit_type == "constraint"]
        progress = [u for u in all_units if u.unit_type == "progress"]

        # Compute stale count
        stale_count = sum(1 for u in all_units if self.check_staleness(u.unit_id) > 0.8)

        # Get delta trail
        with self._connect() as conn:
            delta_rows = conn.execute(
                """SELECT d.* FROM cognitive_unit_deltas d
                JOIN cognitive_units cu ON d.unit_id = cu.unit_id
                WHERE cu.project = ?
                ORDER BY d.changed_at DESC
                LIMIT 20""",
                (project,),
            ).fetchall()

        delta_trail = [
            {
                "delta_id": r["delta_id"],
                "unit_id": r["unit_id"],
                "changed_field": r["changed_field"],
                "old_value": r["old_value"],
                "new_value": r["new_value"],
                "changed_by": r["changed_by"],
                "changed_at": r["changed_at"],
                "reason": r["reason"],
            }
            for r in delta_rows
        ]

        # Unit serializer
        def unit_dict(u):
            return {
                "unit_id": u.unit_id,
                "unit_type": u.unit_type,
                "content": u.content,
                "rationale": u.rationale,
                "scope": u.scope,
                "confidence": u.confidence,
                "override_count": u.override_count,
                "last_verified": u.last_verified.isoformat()
                if u.last_verified
                else None,
                "created_at": u.created_at.isoformat(),
            }

        return {
            "snapshot_id": uuid.uuid4().hex[:12],
            "project": project,
            "scope": scope,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "session_summary": session_summary,
            "task_states": [unit_dict(u) for u in task_states],
            "decisions": [unit_dict(u) for u in decisions],
            "constraints": [unit_dict(u) for u in constraints],
            "progress": [unit_dict(u) for u in progress],
            "delta_trail": delta_trail,
            "stale_count": stale_count,
            "total_units": total_units,
        }

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
