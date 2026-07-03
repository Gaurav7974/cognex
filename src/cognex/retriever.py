
from __future__ import annotations

from .models import MemoryEntry, MemoryScope, MemoryType
from .store import MemoryStore


class MemoryRetriever:

    def __init__(self, store: MemoryStore):
        self.store = store

    def find_relevant(
        self,
        query: str,
        project: str = "",
        limit: int = 10,
        memory_types: tuple[MemoryType, ...] | None = None,
        session_id: str = "",
    ) -> list[MemoryEntry]:
        candidates = self.store.search(
            query=query,
            project=project,
            limit=int(limit * 1.5),
            min_relevance=0.1,
        )

        scored = []
        for mem in candidates:
            if memory_types and mem.type not in memory_types:
                continue
            score = self._score(mem, query, project)
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        for _, mem in top:
            self.store.save(mem.touch(), session_id=session_id)

        return [mem for _, mem in top]

    def find_relevant_hybrid(
        self,
        query: str,
        project: str = "",
        limit: int = 10,
        memory_types: tuple[MemoryType, ...] | None = None,
        session_id: str = "",
    ) -> list[MemoryEntry]:
        from .embeddings import EmbeddingEngine

        bm25_candidates = self.store.search(
            query=query,
            project=project,
            limit=int(limit * 1.5),
            min_relevance=0.1,
        )
        if memory_types:
            bm25_candidates = [m for m in bm25_candidates if m.type in memory_types]

        if not EmbeddingEngine.AVAILABLE:
            top = bm25_candidates[:limit]
            for mem in top:
                self.store.save(mem.touch(), session_id=session_id)
            return top

        semantic_results = self.store.search_semantic(
            query=query,
            limit=int(limit * 1.5),
            project=project,
        )
        semantic_candidates = [mem for _, mem in semantic_results]
        if memory_types:
            semantic_candidates = [m for m in semantic_candidates if m.type in memory_types]

        rrf_scores: dict[str, float] = {}
        memory_by_id: dict[str, MemoryEntry] = {}

        for rank, mem in enumerate(bm25_candidates):
            memory_by_id[mem.id] = mem
            rrf_scores[mem.id] = rrf_scores.get(mem.id, 0.0) + (1.0 / (60.0 + rank))

        for rank, mem in enumerate(semantic_candidates):
            memory_by_id[mem.id] = mem
            rrf_scores[mem.id] = rrf_scores.get(mem.id, 0.0) + (1.0 / (60.0 + rank))

        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)
        top_ids = sorted_ids[:limit]

        top_memories = []
        for mid in top_ids:
            mem = memory_by_id[mid]
            self.store.save(mem.touch(), session_id=session_id)
            top_memories.append(mem)

        return top_memories

    def get_session_context(
        self,
        project: str = "",
        limit: int = 15,
        session_id: str = "",
    ) -> list[MemoryEntry]:
        memories = []

        prefs = self.store.search(
            memory_type=MemoryType.PREFERENCE,
            project=project,
            limit=5,
            min_relevance=0.3,
        )
        memories.extend(prefs)

        if project:
            recent = self.store.search(
                project=project,
                limit=5,
                min_relevance=0.2,
            )
            memories.extend(recent)

        lessons = self.store.search(
            memory_type=MemoryType.LESSON,
            project=project,
            limit=3,
            min_relevance=0.3,
        )
        memories.extend(lessons)

        seen = set()
        unique = []
        for m in memories:
            if m.id not in seen:
                seen.add(m.id)
                unique.append(m)

        top = unique[:limit]
        touched = []
        for mem in top:
            self.store.save(mem.touch(), session_id=session_id)
            touched.append(mem)

        return touched

    def find_similar_decisions(
        self,
        current_situation: str,
        project: str = "",
        limit: int = 3,
    ) -> list[MemoryEntry]:
        return self.store.search(
            query=current_situation,
            memory_type=MemoryType.DECISION,
            project=project,
            limit=limit,
        )

    def find_patterns_for(
        self,
        topic: str,
        project: str = "",
    ) -> list[MemoryEntry]:
        return self.store.search(
            query=topic,
            memory_type=MemoryType.PATTERN,
            project=project,
            limit=5,
        )

    def _score(self, mem: MemoryEntry, query: str, project: str) -> float:
        score = mem.relevance_score

        if project and mem.project == project:
            score *= 1.5

        query_words = set(query.lower().split())
        content_words = set(mem.content.lower().split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            score *= 1.0 + (overlap * 0.3)

        for tag in mem.tags:
            if tag.lower() in query.lower():
                score *= 1.2

        from datetime import datetime, timezone, timedelta

        age = datetime.now(timezone.utc) - mem.created_at
        if age < timedelta(days=7):
            score *= 1.3
        elif age < timedelta(days=30):
            score *= 1.1

        return round(score, 4)
