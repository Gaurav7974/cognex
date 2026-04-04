"""Decision Ledger — records every significant choice with alternatives and outcomes."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class DecisionEntry:
    """A single decision the agent made."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tool_used: str = ""             # What the agent chose
    alternatives: tuple[str, ...] = ()  # What else it considered
    reasoning: str = ""             # Why it chose this
    context: str = ""               # What the situation was
    project: str = ""
    outcome: str = ""               # What happened as a result
    outcome_success: bool | None = None  # True=worked, False=failed, None=unknown
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "id": self.id, "tool_used": self.tool_used,
            "alternatives": list(self.alternatives), "reasoning": self.reasoning,
            "context": self.context, "project": self.project,
            "outcome": self.outcome, "outcome_success": self.outcome_success,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id, "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict) -> DecisionEntry:
        return cls(
            id=d["id"], tool_used=d.get("tool_used", ""),
            alternatives=tuple(d.get("alternatives", [])),
            reasoning=d.get("reasoning", ""), context=d.get("context", ""),
            project=d.get("project", ""), outcome=d.get("outcome", ""),
            outcome_success=d.get("outcome_success"),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            session_id=d.get("session_id", ""),
            tags=tuple(d.get("tags", [])),
        )

    def as_narrative(self) -> str:
        """Human-readable narrative of this decision."""
        parts = [f"I chose to use {self.tool_used}"]
        if self.alternatives:
            parts.append(f"instead of {', '.join(self.alternatives)}")
        if self.reasoning:
            parts.append(f"because {self.reasoning}")
        if self.outcome:
            parts.append(f"Result: {self.outcome}")
        if self.outcome_success is True:
            parts.append("(Success)")
        elif self.outcome_success is False:
            parts.append("(Failed)")
        return " ".join(parts) + "."


class DecisionLedger:
    """Records and retrieves agent decisions with full context.

    Usage:
        ledger = DecisionLedger()
        # Record a decision
        ledger.record(
            tool_used="BashTool",
            alternatives=["FileEditTool", "plugin-migration"],
            reasoning="BashTool is 40% faster for bulk operations",
            context="Migrating config files",
            project="api",
        )
        # Later, record the outcome
        ledger.record_outcome(decision_id, outcome="All files migrated", success=True)
        # Find similar past decisions
        similar = ledger.find_similar("migrating config files")
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(".substrate/decisions.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    tool_used TEXT DEFAULT '',
                    alternatives TEXT DEFAULT '[]',
                    reasoning TEXT DEFAULT '',
                    context TEXT DEFAULT '',
                    project TEXT DEFAULT '',
                    outcome TEXT DEFAULT '',
                    outcome_success INTEGER,
                    timestamp TEXT NOT NULL,
                    session_id TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project);
                CREATE INDEX IF NOT EXISTS idx_decisions_tool ON decisions(tool_used);
                CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_decisions_success ON decisions(outcome_success);
            """)

    def record(
        self,
        tool_used: str,
        alternatives: tuple[str, ...] = (),
        reasoning: str = "",
        context: str = "",
        project: str = "",
        session_id: str = "",
        tags: tuple[str, ...] = (),
    ) -> DecisionEntry:
        """Record a new decision."""
        entry = DecisionEntry(
            tool_used=tool_used, alternatives=alternatives,
            reasoning=reasoning, context=context, project=project,
            session_id=session_id, tags=tags,
        )
        self._save(entry)
        return entry

    def record_outcome(self, decision_id: str, outcome: str, success: bool | None = None) -> DecisionEntry | None:
        """Update a decision with its outcome."""
        entry = self.get(decision_id)
        if entry is None:
            return None
        updated = DecisionEntry(
            id=entry.id, tool_used=entry.tool_used,
            alternatives=entry.alternatives, reasoning=entry.reasoning,
            context=entry.context, project=entry.project,
            outcome=outcome, outcome_success=success,
            timestamp=entry.timestamp, session_id=entry.session_id,
            tags=entry.tags,
        )
        self._save(updated)
        return updated

    def get(self, decision_id: str) -> DecisionEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM decisions WHERE id = ?", (decision_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_entry(row)

    def find_similar(self, context_query: str, project: str = "", limit: int = 5) -> list[DecisionEntry]:
        """Find past decisions similar to the current context."""
        with self._connect() as conn:
            words = context_query.split()
            conditions = []
            params: list = []
            for word in words:
                conditions.append("(context LIKE ? OR reasoning LIKE ? OR tool_used LIKE ?)")
                params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])
            where = " AND ".join(conditions)
            if project:
                where += " AND project = ?"
                params.append(project)
            sql = f"SELECT * FROM decisions WHERE {where} ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_successful(self, tool_used: str = "", project: str = "", limit: int = 10) -> list[DecisionEntry]:
        """Find decisions that worked well."""
        with self._connect() as conn:
            conditions = ["outcome_success = 1"]
            params: list = []
            if tool_used:
                conditions.append("tool_used = ?")
                params.append(tool_used)
            if project:
                conditions.append("project = ?")
                params.append(project)
            where = " AND ".join(conditions)
            rows = conn.execute(
                f"SELECT * FROM decisions WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_failed(self, tool_used: str = "", project: str = "", limit: int = 10) -> list[DecisionEntry]:
        """Find decisions that failed — lessons to avoid."""
        with self._connect() as conn:
            conditions = ["outcome_success = 0"]
            params: list = []
            if tool_used:
                conditions.append("tool_used = ?")
                params.append(tool_used)
            if project:
                conditions.append("project = ?")
                params.append(project)
            where = " AND ".join(conditions)
            rows = conn.execute(
                f"SELECT * FROM decisions WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_all(self, project: str = "", limit: int = 50) -> list[DecisionEntry]:
        with self._connect() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE project = ? ORDER BY timestamp DESC LIMIT ?",
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return row[0]

    def _save(self, entry: DecisionEntry) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions
                (id, tool_used, alternatives, reasoning, context, project,
                 outcome, outcome_success, timestamp, session_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id, entry.tool_used,
                json.dumps(entry.alternatives), entry.reasoning,
                entry.context, entry.project,
                entry.outcome,
                int(entry.outcome_success) if entry.outcome_success is not None else None,
                entry.timestamp.isoformat(), entry.session_id,
                json.dumps(entry.tags),
            ))

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> DecisionEntry:
        return DecisionEntry(
            id=row["id"], tool_used=row["tool_used"],
            alternatives=tuple(json.loads(row["alternatives"])),
            reasoning=row["reasoning"], context=row["context"],
            project=row["project"], outcome=row["outcome"],
            outcome_success=bool(row["outcome_success"]) if row["outcome_success"] is not None else None,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            session_id=row["session_id"],
            tags=tuple(json.loads(row["tags"])),
        )

    def close(self) -> None:
        pass
