
from __future__ import annotations

import threading
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import MemoryEntry, MemoryScope, MemoryType, SessionSnapshot
from .store import MemoryStore
from .extractor import MemoryExtractor, ExtractionResult
from .retriever import MemoryRetriever


@dataclass
class CognexReport:

    total_memories: int
    memories_by_type: dict[str, int]
    total_sessions: int
    top_projects: list[tuple[str, int]]
    oldest_memory_age_days: float
    newest_memory_age_days: float

    def as_text(self) -> str:
        lines = [
            "=== Cognex Engine ===",
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


class CognexEngine:

    def __init__(self, db_path: str | Path | None = None, pool_size: int | None = None):
        self.store = MemoryStore(db_path=db_path, pool_size=pool_size)
        self.extractor = MemoryExtractor()
        self.retriever = MemoryRetriever(self.store)
        self._sessions: dict[str, dict] = {}
        self._sessions_lock: threading.Lock = threading.Lock()
        self._current_project: str = ""

    def get_current_session(self) -> str | None:
        with self._sessions_lock:
            if not self._sessions:
                return None
            for session_id in reversed(list(self._sessions.keys())):
                if self._sessions[session_id].get("active", False):
                    return session_id
            return None


    def start_session(self, session_id: str, project: str = "") -> list[MemoryEntry]:
        with self._sessions_lock:
            self._sessions[session_id] = {
                "session_id": session_id,
                "project": project,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "active": True
            }
        self._current_project = project

        from .arcs import SessionArcManager
        try:
            SessionArcManager.get_or_create_arc(session_id, project, self.store)
        except Exception as e:
            logger.error("Failed to get or create session arc: %s", e)

        return self.retriever.get_session_context(project=project, session_id=session_id)

    def end_session(
        self,
        summary: str = "",
        key_decisions: tuple[str, ...] = (),
        tools_used: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> SessionSnapshot:
        current_session_id = self.get_current_session()
        session = SessionSnapshot(
            session_id=current_session_id or "unknown",
            project=self._current_project,
            summary=summary,
            key_decisions=key_decisions,
            tools_used=tools_used,
            errors_encountered=errors,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.store.save_session(session)

        if current_session_id and self._current_project:
            from .arcs import SessionArcManager
            try:
                SessionArcManager.get_or_create_arc(current_session_id, self._current_project, self.store)
            except Exception as e:
                logger.error("Failed to update session arc on end_session: %s", e)

        if current_session_id:
            with self._sessions_lock:
                if current_session_id in self._sessions:
                    self._sessions[current_session_id]["active"] = False
        return session


    def process_transcript(
        self,
        transcript: str,
        session_id: str | None = None,
        project: str | None = None,
        context: str = "",
    ) -> ExtractionResult:
        sid = session_id or self.get_current_session() or ""
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
        entry = MemoryEntry(
            type=memory_type,
            scope=scope,
            content=content,
            context=context,
            project=project or self._current_project,
            tags=tags,
        )
        return self.store.save(entry)

    def get_context(
        self, query: str = "", project: str = "", limit: int = 10
    ) -> list[MemoryEntry]:
        proj = project or self._current_project
        session_id = self.get_current_session() or ""
        if query:
            return self.retriever.find_relevant_hybrid(
                query=query, project=proj, limit=limit, session_id=session_id
            )
        return self.retriever.get_session_context(
            project=proj, limit=limit, session_id=session_id
        )

    def find_similar_decisions(self, situation: str) -> list[MemoryEntry]:
        return self.retriever.find_similar_decisions(
            situation,
            project=self._current_project,
        )


    def decay_memories(self, factor: float = 0.95) -> int:
        from .feedback import OutcomeFeedback
        modifiers = OutcomeFeedback.compute_uniqueness_modifiers(self.store)
        return self.store.decay_all(factor, modifiers=modifiers)

    def report(self) -> CognexReport:
        with self.store._connect() as conn:
            try:
                total = self.store.count()
                by_type: dict[str, int] = {}
                for mt in MemoryType:
                    count = len(self.store.search(memory_type=mt, limit=9999))
                    if count > 0:
                        by_type[mt.value] = count

                sessions = self.store.get_sessions(limit=9999)

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

                return CognexReport(
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
        return self.get_current_session()

    @property
    def current_project(self) -> str:
        return self._current_project
