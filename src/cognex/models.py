
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class MemoryType(enum.Enum):

    FACT = "fact"  # A piece of knowledge learned
    PREFERENCE = "preference"  # A user preference discovered
    DECISION = "decision"  # A choice that was made + why
    PATTERN = "pattern"  # A recurring behavior observed
    CONTEXT = "context"  # Project/environment context
    LESSON = "lesson"  # What went wrong/right


class MemoryScope(enum.Enum):

    PRIVATE = "private"  # Only this user
    PROJECT = "project"  # Shared across users of this project
    GLOBAL = "global"  # Universal, applies everywhere


@dataclass(frozen=True)
class MemoryEntry:

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: MemoryType = MemoryType.FACT
    scope: MemoryScope = MemoryScope.PRIVATE
    content: str = ""
    context: str = ""
    relevance_score: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime | None = None
    access_count: int = 0
    project: str = ""
    tags: tuple[str, ...] = ()
    gist: str = ""

    def touch(self) -> MemoryEntry:
        return MemoryEntry(
            id=self.id,
            type=self.type,
            scope=self.scope,
            content=self.content,
            context=self.context,
            relevance_score=min(self.relevance_score + 0.1, 2.0),
            created_at=self.created_at,
            last_accessed=datetime.now(timezone.utc),
            access_count=self.access_count + 1,
            project=self.project,
            tags=self.tags,
            gist=self.gist,
        )

    def decay(self, factor: float = 0.95) -> MemoryEntry:
        return MemoryEntry(
            id=self.id,
            type=self.type,
            scope=self.scope,
            content=self.content,
            context=self.context,
            relevance_score=round(self.relevance_score * factor, 4),
            created_at=self.created_at,
            last_accessed=self.last_accessed,
            access_count=self.access_count,
            project=self.project,
            tags=self.tags,
            gist=self.gist,
        )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "scope": self.scope.value,
            "content": self.content,
            "context": self.context,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat()
            if self.last_accessed
            else None,
            "access_count": self.access_count,
            "project": self.project,
            "tags": list(self.tags),
            "gist": self.gist,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEntry:
        return cls(
            id=d["id"],
            type=MemoryType(d["type"]),
            scope=MemoryScope(d["scope"]),
            content=d["content"],
            context=d["context"],
            relevance_score=d["relevance_score"],
            created_at=datetime.fromisoformat(d["created_at"]),
            last_accessed=datetime.fromisoformat(d["last_accessed"])
            if d.get("last_accessed")
            else None,
            access_count=d["access_count"],
            project=d.get("project", ""),
            tags=tuple(d.get("tags", [])),
            gist=d.get("gist", ""),
        )


@dataclass(frozen=True)
class SessionSnapshot:

    session_id: str
    project: str = ""
    summary: str = ""
    key_decisions: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    errors_encountered: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    memory_ids_extracted: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project": self.project,
            "summary": self.summary,
            "key_decisions": list(self.key_decisions),
            "tools_used": list(self.tools_used),
            "errors_encountered": list(self.errors_encountered),
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "memory_ids": list(self.memory_ids_extracted),
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionSnapshot:
        return cls(
            session_id=d["session_id"],
            project=d.get("project", ""),
            summary=d.get("summary", ""),
            key_decisions=tuple(d.get("key_decisions", [])),
            tools_used=tuple(d.get("tools_used", [])),
            errors_encountered=tuple(d.get("errors_encountered", [])),
            started_at=datetime.fromisoformat(d["started_at"]),
            ended_at=datetime.fromisoformat(d["ended_at"])
            if d.get("ended_at")
            else None,
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            memory_ids_extracted=tuple(d.get("memory_ids_extracted", [])),
        )


class StateUnitType(enum.Enum):

    DECISION = "decision"
    CONSTRAINT = "constraint"
    PROGRESS = "progress"
    TASK_STATE = "task_state"


@dataclass(frozen=True)
class StateUnit:

    unit_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    unit_type: str = "decision"
    content: str = ""
    rationale: str = ""
    scope: str = ""
    confidence: float = 1.0
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    project: str = ""
    override_count: int = 0
    last_verified: datetime | None = None
    epistemic_status: str = "assumed"
    verification_condition: str = ""
    depends_on: tuple[str, ...] = ()
    staleness_deadline: datetime | None = None

    def as_dict(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "unit_type": self.unit_type,
            "content": self.content,
            "rationale": self.rationale,
            "scope": self.scope,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
            "project": self.project,
            "override_count": self.override_count,
            "last_verified": self.last_verified.isoformat()
            if self.last_verified
            else None,
            "epistemic_status": self.epistemic_status,
            "verification_condition": self.verification_condition,
            "depends_on": list(self.depends_on),
            "staleness_deadline": self.staleness_deadline.isoformat()
            if self.staleness_deadline
            else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StateUnit:
        return cls(
            unit_id=d["unit_id"],
            unit_type=d.get("unit_type", "decision"),
            content=d["content"],
            rationale=d.get("rationale", ""),
            scope=d.get("scope", ""),
            confidence=d.get("confidence", 1.0),
            tags=tuple(d.get("tags", [])),
            created_at=datetime.fromisoformat(d["created_at"]),
            session_id=d.get("session_id", ""),
            project=d.get("project", ""),
            override_count=d.get("override_count", 0),
            last_verified=datetime.fromisoformat(d["last_verified"])
            if d.get("last_verified")
            else None,
            epistemic_status=d.get("epistemic_status", "assumed"),
            verification_condition=d.get("verification_condition", ""),
            depends_on=tuple(d.get("depends_on", [])),
            staleness_deadline=datetime.fromisoformat(d["staleness_deadline"])
            if d.get("staleness_deadline")
            else None,
        )
