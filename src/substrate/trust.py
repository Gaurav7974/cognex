"""Trust Gradient Engine — learns from every permission decision."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import json
import sqlite3


class TrustLevel(enum.Enum):
    UNKNOWN = 0       # Never seen — requires approval
    OBSERVED = 1      # Approved N times — auto-approve read-only
    TRUSTED = 2       # Used M times across K sessions — auto-approve standard
    DELEGATED = 3     # Fully trusted — act autonomously, report post-hoc
    BLOCKED = -1      # Denied or violated — always requires approval


@dataclass(frozen=True)
class TrustRecord:
    """Trust profile for a single tool-in-context."""
    tool_name: str
    context: str = ""           # e.g. "file-edit", "bash", "web-fetch"
    project: str = ""
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    approval_count: int = 0
    denial_count: int = 0
    violation_count: int = 0    # Times it did something unexpected
    last_used: datetime | None = None
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_violation: datetime | None = None
    total_operations: int = 0
    safe_operations: int = 0

    def record_approval(self) -> TrustRecord:
        """Record a successful, approved operation."""
        new_approval = self.approval_count + 1
        new_total = self.total_operations + 1
        new_safe = self.safe_operations + 1
        new_level = self._compute_level(new_approval, self.denial_count, self.violation_count)
        return TrustRecord(
            tool_name=self.tool_name, context=self.context, project=self.project,
            trust_level=new_level, approval_count=new_approval,
            denial_count=self.denial_count, violation_count=self.violation_count,
            last_used=datetime.now(timezone.utc), first_seen=self.first_seen,
            last_violation=self.last_violation, total_operations=new_total,
            safe_operations=new_safe,
        )

    def record_denial(self) -> TrustRecord:
        """Record a denied operation (user said no)."""
        new_denial = self.denial_count + 1
        new_total = self.total_operations + 1
        new_level = self._compute_level(self.approval_count, new_denial, self.violation_count)
        return TrustRecord(
            tool_name=self.tool_name, context=self.context, project=self.project,
            trust_level=new_level, approval_count=self.approval_count,
            denial_count=new_denial, violation_count=self.violation_count,
            last_used=datetime.now(timezone.utc), first_seen=self.first_seen,
            last_violation=self.last_violation, total_operations=new_total,
            safe_operations=self.safe_operations,
        )

    def record_violation(self) -> TrustRecord:
        """Record a violation — the tool did something unexpected."""
        new_violation = self.violation_count + 1
        new_level = TrustLevel.BLOCKED if new_violation > 0 else self._compute_level(
            self.approval_count, self.denial_count, new_violation
        )
        return TrustRecord(
            tool_name=self.tool_name, context=self.context, project=self.project,
            trust_level=new_level, approval_count=self.approval_count,
            denial_count=self.denial_count, violation_count=new_violation,
            last_used=datetime.now(timezone.utc), first_seen=self.first_seen,
            last_violation=datetime.now(timezone.utc), total_operations=self.total_operations,
            safe_operations=self.safe_operations,
        )

    def _compute_level(self, approvals: int, denials: int, violations: int) -> TrustLevel:
        """Compute trust level from history."""
        if violations > 0:
            return TrustLevel.BLOCKED
        if approvals == 0:
            return TrustLevel.UNKNOWN
        # Need 5 approvals with no denials for OBSERVED
        if approvals >= 5 and denials == 0:
            return TrustLevel.OBSERVED
        # Need 20 approvals across 3+ sessions for TRUSTED
        if approvals >= 20 and denials <= 2:
            return TrustLevel.TRUSTED
        # Need 50+ approvals, near-zero denials for DELEGATED
        if approvals >= 50 and denials <= 1:
            return TrustLevel.DELEGATED
        return TrustLevel.OBSERVED if approvals >= 3 else TrustLevel.UNKNOWN

    @property
    def requires_approval(self) -> bool:
        """Does this operation need human approval?"""
        return self.trust_level in (TrustLevel.UNKNOWN, TrustLevel.BLOCKED)

    @property
    def trust_score(self) -> float:
        """0.0 (blocked) to 1.0 (fully delegated)."""
        total = self.approval_count + self.denial_count
        if total == 0:
            return 0.5  # Unknown = middle
        ratio = self.approval_count / total
        # Penalty for violations
        violation_penalty = self.violation_count * 0.2
        return max(0.0, min(1.0, ratio - violation_penalty))

    def as_dict(self) -> dict:
        return {
            "tool_name": self.tool_name, "context": self.context,
            "project": self.project, "trust_level": self.trust_level.value,
            "approval_count": self.approval_count, "denial_count": self.denial_count,
            "violation_count": self.violation_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "first_seen": self.first_seen.isoformat(),
            "last_violation": self.last_violation.isoformat() if self.last_violation else None,
            "total_operations": self.total_operations,
            "safe_operations": self.safe_operations,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TrustRecord:
        return cls(
            tool_name=d["tool_name"], context=d.get("context", ""),
            project=d.get("project", ""),
            trust_level=TrustLevel(d["trust_level"]),
            approval_count=d["approval_count"], denial_count=d["denial_count"],
            violation_count=d["violation_count"],
            last_used=datetime.fromisoformat(d["last_used"]) if d.get("last_used") else None,
            first_seen=datetime.fromisoformat(d["first_seen"]),
            last_violation=datetime.fromisoformat(d["last_violation"]) if d.get("last_violation") else None,
            total_operations=d["total_operations"],
            safe_operations=d["safe_operations"],
        )


@dataclass(frozen=True)
class PermissionDecision:
    """A single permission event — what was asked, what was decided."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tool_name: str = ""
    operation: str = ""       # e.g. "read file", "delete file", "run bash"
    context: str = ""
    project: str = ""
    approved: bool = False
    trust_level_at_time: TrustLevel = TrustLevel.UNKNOWN
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""          # Why it was approved/denied

    def as_dict(self) -> dict:
        return {
            "id": self.id, "tool_name": self.tool_name,
            "operation": self.operation, "context": self.context,
            "project": self.project, "approved": self.approved,
            "trust_level_at_time": self.trust_level_at_time.value,
            "timestamp": self.timestamp.isoformat(), "reason": self.reason,
        }


class TrustGradientEngine:
    """Learns trust from every permission interaction.

    Usage:
        engine = TrustGradientEngine()
        # Check if something needs approval
        needs_approval = engine.requires_approval("BashTool", "run git status", project="api")
        # Record the outcome
        engine.record_approval("BashTool", "run git status", project="api")
        # Or record a denial
        engine.record_denial("BashTool", "rm -rf /", project="api")
        # Or record a violation
        engine.record_violation("BashTool", "deleted wrong file", project="api")
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(".substrate/trust.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trust_records (
                    tool_name TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '',
                    project TEXT NOT NULL DEFAULT '',
                    trust_level INTEGER DEFAULT 0,
                    approval_count INTEGER DEFAULT 0,
                    denial_count INTEGER DEFAULT 0,
                    violation_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    first_seen TEXT NOT NULL,
                    last_violation TEXT,
                    total_operations INTEGER DEFAULT 0,
                    safe_operations INTEGER DEFAULT 0,
                    PRIMARY KEY (tool_name, context, project)
                );

                CREATE TABLE IF NOT EXISTS permission_decisions (
                    id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    project TEXT DEFAULT '',
                    approved INTEGER NOT NULL,
                    trust_level_at_time INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    reason TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_tool ON permission_decisions(tool_name);
                CREATE INDEX IF NOT EXISTS idx_decisions_project ON permission_decisions(project);
                CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON permission_decisions(timestamp DESC);
            """)

    # ── Core API ──────────────────────────────────────────────

    def requires_approval(self, tool_name: str, operation: str = "", project: str = "") -> bool:
        """Check if this operation needs human approval."""
        record = self.get_trust(tool_name, project=project)
        return record.requires_approval

    def get_trust(self, tool_name: str, context: str = "", project: str = "") -> TrustRecord:
        """Get trust record for a tool."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trust_records WHERE tool_name = ? AND context = ? AND project = ?",
                (tool_name, context, project),
            ).fetchone()
        if row:
            return TrustRecord(
                tool_name=row["tool_name"], context=row["context"], project=row["project"],
                trust_level=TrustLevel(row["trust_level"]),
                approval_count=row["approval_count"], denial_count=row["denial_count"],
                violation_count=row["violation_count"],
                last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
                first_seen=datetime.fromisoformat(row["first_seen"]),
                last_violation=datetime.fromisoformat(row["last_violation"]) if row["last_violation"] else None,
                total_operations=row["total_operations"],
                safe_operations=row["safe_operations"],
            )
        return TrustRecord(tool_name=tool_name, context=context, project=project)

    def record_approval(self, tool_name: str, operation: str = "", context: str = "", project: str = "", reason: str = "") -> PermissionDecision:
        """Record that an operation was approved."""
        decision = PermissionDecision(
            tool_name=tool_name, operation=operation, context=context,
            project=project, approved=True, reason=reason,
        )
        self._save_decision(decision)
        self._update_trust(tool_name, context, project, lambda r: r.record_approval())
        return decision

    def record_denial(self, tool_name: str, operation: str = "", context: str = "", project: str = "", reason: str = "") -> PermissionDecision:
        """Record that an operation was denied."""
        decision = PermissionDecision(
            tool_name=tool_name, operation=operation, context=context,
            project=project, approved=False, reason=reason,
        )
        self._save_decision(decision)
        self._update_trust(tool_name, context, project, lambda r: r.record_denial())
        return decision

    def record_violation(self, tool_name: str, operation: str = "", context: str = "", project: str = "", reason: str = "") -> PermissionDecision:
        """Record that a tool did something unexpected."""
        decision = PermissionDecision(
            tool_name=tool_name, operation=operation, context=context,
            project=project, approved=True, reason=reason,
        )
        self._save_decision(decision)
        self._update_trust(tool_name, context, project, lambda r: r.record_violation())
        return decision

    # ── Queries ───────────────────────────────────────────────

    def get_recent_decisions(self, limit: int = 20, project: str = "") -> list[PermissionDecision]:
        with self._connect() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM permission_decisions WHERE project = ? ORDER BY timestamp DESC LIMIT ?",
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM permission_decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
        return [
            PermissionDecision(
                id=r["id"], tool_name=r["tool_name"], operation=r["operation"],
                context=r["context"], project=r["project"], approved=bool(r["approved"]),
                trust_level_at_time=TrustLevel(r["trust_level_at_time"]),
                timestamp=datetime.fromisoformat(r["timestamp"]), reason=r["reason"],
            )
            for r in rows
        ]

    def get_trust_summary(self, project: str = "") -> list[TrustRecord]:
        """Get all trust records, sorted by trust level."""
        with self._connect() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM trust_records WHERE project = ? ORDER BY trust_level DESC, approval_count DESC",
                    (project,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trust_records ORDER BY trust_level DESC, approval_count DESC"
                ).fetchall()
        return [
            TrustRecord(
                tool_name=r["tool_name"], context=r["context"], project=r["project"],
                trust_level=TrustLevel(r["trust_level"]),
                approval_count=r["approval_count"], denial_count=r["denial_count"],
                violation_count=r["violation_count"],
                last_used=datetime.fromisoformat(r["last_used"]) if r["last_used"] else None,
                first_seen=datetime.fromisoformat(r["first_seen"]),
                last_violation=datetime.fromisoformat(r["last_violation"]) if r["last_violation"] else None,
                total_operations=r["total_operations"],
                safe_operations=r["safe_operations"],
            )
            for r in rows
        ]

    def approval_rate(self, tool_name: str = "", project: str = "") -> float:
        """Overall approval rate (0.0 to 1.0)."""
        decisions = self.get_recent_decisions(limit=9999, project=project)
        if tool_name:
            decisions = [d for d in decisions if d.tool_name == tool_name]
        if not decisions:
            return 0.5
        approved = sum(1 for d in decisions if d.approved)
        return approved / len(decisions)

    # ── Internal ──────────────────────────────────────────────

    def _save_decision(self, decision: PermissionDecision) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO permission_decisions
                (id, tool_name, operation, context, project, approved,
                 trust_level_at_time, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.id, decision.tool_name, decision.operation,
                decision.context, decision.project, int(decision.approved),
                decision.trust_level_at_time.value,
                decision.timestamp.isoformat(), decision.reason,
            ))

    def _update_trust(self, tool_name: str, context: str, project: str,
                      updater) -> None:
        """Update trust record using an updater function."""
        record = self.get_trust(tool_name, context, project)
        updated = updater(record)
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trust_records
                (tool_name, context, project, trust_level, approval_count,
                 denial_count, violation_count, last_used, first_seen,
                 last_violation, total_operations, safe_operations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                updated.tool_name, updated.context, updated.project,
                updated.trust_level.value, updated.approval_count,
                updated.denial_count, updated.violation_count,
                updated.last_used.isoformat() if updated.last_used else None,
                updated.first_seen.isoformat(),
                updated.last_violation.isoformat() if updated.last_violation else None,
                updated.total_operations, updated.safe_operations,
            ))

    def close(self) -> None:
        pass
