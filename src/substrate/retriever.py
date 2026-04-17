"""Finds relevant memories for a new session or query."""

from __future__ import annotations

from .models import MemoryEntry, MemoryScope, MemoryType
from .store import MemoryStore


class MemoryRetriever:
    """Finds the right memories at the right time.

    Combines multiple signals:
    - Text relevance (keyword match)
    - Recency (newer memories score higher)
    - Frequency (accessed often = important)
    - Project affinity (project-specific memories first)
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    def find_relevant(
        self,
        query: str,
        project: str = "",
        limit: int = 10,
        memory_types: tuple[MemoryType, ...] | None = None,
    ) -> list[MemoryEntry]:
        # Phase 1: Broad search with reduced candidate multiplier
        # Moved scoring to SQL layer via FTS5 bm25() to reduce Python work
        candidates = self.store.search(
            query=query,
            project=project,
            limit=int(limit * 1.5),  # Reduced from limit*3 to limit*1.5
            min_relevance=0.1,
        )

        # Phase 2: Filter by type (Python-side type filtering only)
        scored = []
        for mem in candidates:
            if memory_types and mem.type not in memory_types:
                continue
            # Minimal Python scoring for project/recency bonuses
            # FTS5 BM25 score already in mem.relevance_score from SQL
            score = self._score(mem, query, project)
            scored.append((score, mem))

        # Phase 3: Return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        # Touch the winners — they're being used
        for _, mem in top:
            self.store.save(mem.touch())

        return [mem for _, mem in top]

    def get_session_context(
        self,
        project: str = "",
        limit: int = 15,
    ) -> list[MemoryEntry]:
        """Get memories to inject at the start of a new session.

        Returns a mix of:
        - Recent project memories (what we just worked on)
        - High-relevance preferences (how the user likes things)
        - Recent lessons (what to avoid)
        """
        memories = []

        # Preferences — always useful
        prefs = self.store.search(
            memory_type=MemoryType.PREFERENCE,
            project=project,
            limit=5,
            min_relevance=0.3,
        )
        memories.extend(prefs)

        # Recent project context
        if project:
            recent = self.store.search(
                project=project,
                limit=5,
                min_relevance=0.2,
            )
            memories.extend(recent)

        # Recent lessons — avoid repeating mistakes
        lessons = self.store.search(
            memory_type=MemoryType.LESSON,
            project=project,
            limit=3,
            min_relevance=0.3,
        )
        memories.extend(lessons)

        # Deduplicate by ID
        seen = set()
        unique = []
        for m in memories:
            if m.id not in seen:
                seen.add(m.id)
                unique.append(m)

        return unique[:limit]

    def find_similar_decisions(
        self,
        current_situation: str,
        project: str = "",
        limit: int = 3,
    ) -> list[MemoryEntry]:
        """Find past decisions similar to the current situation.

        Used for the Decision Ledger: "Last time you faced this..."
        """
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
        """Find recurring patterns related to a topic."""
        return self.store.search(
            query=topic,
            memory_type=MemoryType.PATTERN,
            project=project,
            limit=5,
        )

    def _score(self, mem: MemoryEntry, query: str, project: str) -> float:
        """Score a memory's relevance to the current context."""
        score = mem.relevance_score

        # Project match bonus
        if project and mem.project == project:
            score *= 1.5

        # Keyword overlap bonus
        query_words = set(query.lower().split())
        content_words = set(mem.content.lower().split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            score *= 1.0 + (overlap * 0.3)

        # Tag match bonus
        for tag in mem.tags:
            if tag.lower() in query.lower():
                score *= 1.2

        # Recency bonus (memories from last 7 days get a boost)
        from datetime import datetime, timezone, timedelta

        age = datetime.now(timezone.utc) - mem.created_at
        if age < timedelta(days=7):
            score *= 1.3
        elif age < timedelta(days=30):
            score *= 1.1

        return round(score, 4)
