"""Main orchestrator — ties memory store, extractor, and retriever together."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from .models import MemoryEntry, MemoryScope, MemoryType, SessionSnapshot
from .store import MemoryStore
from .extractor import MemoryExtractor, ExtractionResult
from .retriever import MemoryRetriever


@dataclass
class SubstrateReport:
    """Summary of the substrate's current state."""

    total_memories: int
    memories_by_type: dict[str, int]
    total_sessions: int
    top_projects: list[tuple[str, int]]
    oldest_memory_age_days: float
    newest_memory_age_days: float

    def as_text(self) -> str:
        lines = [
            "=== Cognitive Substrate ===",
            f"Memories: {self.total_memories}",
            f"Sessions: {self.total_sessions}",
            "",
            "By type:",
        ]
        for t, c in self.memories_by_type.items():
            lines.append(f"  {t}: {c}")
        if self.top_projects:
            lines.append("")
            lines.append("Top projects:")
            for proj, count in self.top_projects:
                lines.append(f"  {proj}: {count} memories")
        return "\n".join(lines)


class CognitiveSubstrate:
    """The persistent memory layer for an AI agent.

    Usage:
        substrate = CognitiveSubstrate()
        # Start a session
        substrate.start_session("session-abc", project="my-api")
        # Process conversation
        substrate.process_transcript("I prefer pytest over unittest...")
        # Get context for next session
        memories = substrate.get_context("my-api")
    """

    def __init__(self, db_path: str | Path | None = None, pool_size: int | None = None):
        self.store = MemoryStore(db_path=db_path, pool_size=pool_size)
        self.extractor = MemoryExtractor()
        self.retriever = MemoryRetriever(self.store)
        self._current_session: str | None = None
        self._current_project: str = ""

    # ── Session Lifecycle ─────────────────────────────────────

    def start_session(self, session_id: str, project: str = "") -> list[MemoryEntry]:
        """Start a new session. Returns relevant memories to inject."""
        self._current_session = session_id
        self._current_project = project
        return self.retriever.get_session_context(project=project)

    def end_session(
        self,
        summary: str = "",
        key_decisions: tuple[str, ...] = (),
        tools_used: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> SessionSnapshot:
        """End the current session. Saves snapshot and extracts memories."""
        session = SessionSnapshot(
            session_id=self._current_session or "unknown",
            project=self._current_project,
            summary=summary,
            key_decisions=key_decisions,
            tools_used=tools_used,
            errors_encountered=errors,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.store.save_session(session)
        self._current_session = None
        return session

    # ── Memory Operations ─────────────────────────────────────

    def process_transcript(
        self,
        transcript: str,
        session_id: str | None = None,
        project: str | None = None,
        context: str = "",
    ) -> ExtractionResult:
        """Process a conversation transcript and extract memories."""
        sid = session_id or self._current_session or ""
        proj = project or self._current_project or ""
        result = self.extractor.extract(
            transcript=transcript,
            session_id=sid,
            project=proj,
            context=context,
        )
        if result.memories:
            self.store.save_many(result.memories)
        return result

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        scope: MemoryScope = MemoryScope.PRIVATE,
        project: str = "",
        tags: tuple[str, ...] = (),
        context: str = "",
    ) -> MemoryEntry:
        """Manually add a memory entry."""
        entry = self.extractor.extract_manual(
            content=content,
            memory_type=memory_type,
            scope=scope,
            project=project or self._current_project,
            tags=tags,
            context=context,
        )
        return self.store.save(entry)

    def get_context(
        self, query: str = "", project: str = "", limit: int = 10
    ) -> list[MemoryEntry]:
        """Get relevant memories for the current context."""
        proj = project or self._current_project
        if query:
            return self.retriever.find_relevant(query=query, project=proj, limit=limit)
        return self.retriever.get_session_context(project=proj, limit=limit)

    def find_similar_decisions(self, situation: str) -> list[MemoryEntry]:
        """Find past decisions similar to current situation."""
        return self.retriever.find_similar_decisions(
            situation,
            project=self._current_project,
        )

    # ── Maintenance ───────────────────────────────────────────

    def decay_memories(self, factor: float = 0.95) -> int:
        """Age all memories. Faded ones are auto-deleted."""
        return self.store.decay_all(factor)

    def report(self) -> SubstrateReport:
        """Get a summary of the substrate's state.

        All queries run in a single transaction for consistent snapshot.
        """
        with self.store._connect() as conn:
            # The _connect() context manager already ensures transaction isolation
            try:
                total = self.store.count()
                by_type: dict[str, int] = {}
                for mt in MemoryType:
                    count = len(self.store.search(memory_type=mt, limit=9999))
                    if count > 0:
                        by_type[mt.value] = count

                sessions = self.store.get_sessions(limit=9999)

                # Top projects
                project_counts: dict[str, int] = {}
                for mt in MemoryType:
                    for mem in self.store.search(memory_type=mt, limit=9999):
                        if mem.project:
                            project_counts[mem.project] = (
                                project_counts.get(mem.project, 0) + 1
                            )
                top_projects = sorted(
                    project_counts.items(), key=lambda x: x[1], reverse=True
                )[:5]

                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                all_mems = self.store.search(limit=9999)
                oldest = max(((now - m.created_at).days for m in all_mems), default=0)
                newest = min(((now - m.created_at).days for m in all_mems), default=0)

                conn.commit()

                return SubstrateReport(
                    total_memories=total,
                    memories_by_type=by_type,
                    total_sessions=len(sessions),
                    top_projects=top_projects,
                    oldest_memory_age_days=oldest,
                    newest_memory_age_days=newest,
                )
            except Exception:
                conn.rollback()
                raise

    @property
    def current_session(self) -> str | None:
        return self._current_session

    @property
    def current_project(self) -> str:
        return self._current_project
