"""Extracts structured memories from raw conversation transcripts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import MemoryEntry, MemoryScope, MemoryType


@dataclass
class ExtractionResult:
    memories: list[MemoryEntry]
    source_session: str
    count: int

    @property
    def memory_ids(self) -> tuple[str, ...]:
        return tuple(m.id for m in self.memories)


# Patterns that signal important memory-worthy content
_PREFERENCE_PATTERNS = [
    (r"(?:prefer|like to use|always use|don't use|avoid|never use)\s+(?:the\s+)?(\w+)", "preference"),
    (r"(?:I\s+)?(?:use|run|write)\s+(?:with|in|using)\s+(\w+)", "preference"),
    (r"(?:better\s+with|works\s+better\s+with|faster\s+with)\s+(\w+)", "preference"),
]

_DECISION_PATTERNS = [
    (r"(?:chose|choosing|decided|deciding|went\s+with|picked)\s+(?:the\s+)?(\w+)", "decision"),
    (r"(?:instead\s+of|rather\s+than|over)\s+(\w+)", "decision"),
    (r"(?:because|since|due\s+to)\s+(.+?)(?:\.|$)", "reasoning"),
]

_LESSON_PATTERNS = [
    (r"(?:failed|broke|error|issue|bug|problem)\s+(?:with|in|on)\s+(\w+)", "lesson"),
    (r"(?:don't|never)\s+(?:do|run|use|execute)\s+(.+?)(?:\.|$)", "lesson"),
    (r"(?:worked|succeeded|fixed)\s+(?:when|by|using)\s+(\w+)", "lesson"),
]

_PATTERN_PATTERNS = [
    (r"(?:always|usually|often|typically|every\s+time)\s+(\w+)", "pattern"),
    (r"(?:again|repeated|same\s+issue|same\s+problem)", "pattern"),
]


class MemoryExtractor:
    """Extracts structured memories from conversation text.

    Uses pattern matching as the base layer. In production, this would
    be backed by an LLM call — but the patterns give us a working
    foundation that requires no API calls.
    """

    def extract(
        self,
        transcript: str,
        session_id: str = "",
        project: str = "",
        context: str = "",
    ) -> ExtractionResult:
        """Extract all memories from a conversation transcript."""
        memories = []

        for memory_type, extractor in [
            (MemoryType.PREFERENCE, self._extract_preferences),
            (MemoryType.DECISION, self._extract_decisions),
            (MemoryType.LESSON, self._extract_lessons),
            (MemoryType.PATTERN, self._extract_patterns),
            (MemoryType.FACT, self._extract_facts),
        ]:
            found = extractor(transcript, session_id, project, context)
            memories.extend(found)

        return ExtractionResult(
            memories=memories,
            source_session=session_id,
            count=len(memories),
        )

    def _extract_preferences(
        self, text: str, session_id: str, project: str, context: str,
    ) -> list[MemoryEntry]:
        memories = []
        for pattern, label in _PREFERENCE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                # Deduplicate
                if not any(m.content == content for m in memories):
                    memories.append(MemoryEntry(
                        type=MemoryType.PREFERENCE,
                        scope=MemoryScope.PRIVATE,
                        content=content,
                        context=context or f"Learned from session {session_id}",
                        project=project,
                        tags=(label, "preference"),
                    ))
        return memories

    def _extract_decisions(
        self, text: str, session_id: str, project: str, context: str,
    ) -> list[MemoryEntry]:
        memories = []
        for pattern, label in _DECISION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                if len(content) < 10:  # Too short to be meaningful
                    continue
                if not any(m.content == content for m in memories):
                    memories.append(MemoryEntry(
                        type=MemoryType.DECISION,
                        scope=MemoryScope.PRIVATE,
                        content=content,
                        context=context or f"Learned from session {session_id}",
                        project=project,
                        tags=(label, "decision"),
                    ))
        return memories

    def _extract_lessons(
        self, text: str, session_id: str, project: str, context: str,
    ) -> list[MemoryEntry]:
        memories = []
        for pattern, label in _LESSON_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                if not any(m.content == content for m in memories):
                    memories.append(MemoryEntry(
                        type=MemoryType.LESSON,
                        scope=MemoryScope.PRIVATE,
                        content=content,
                        context=context or f"Learned from session {session_id}",
                        project=project,
                        tags=(label, "lesson"),
                    ))
        return memories

    def _extract_patterns(
        self, text: str, session_id: str, project: str, context: str,
    ) -> list[MemoryEntry]:
        memories = []
        for pattern, label in _PATTERN_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                if not any(m.content == content for m in memories):
                    memories.append(MemoryEntry(
                        type=MemoryType.PATTERN,
                        scope=MemoryScope.PRIVATE,
                        content=content,
                        context=context or f"Learned from session {session_id}",
                        project=project,
                        tags=(label, "pattern"),
                    ))
        return memories

    def _extract_facts(
        self, text: str, session_id: str, project: str, context: str,
    ) -> list[MemoryEntry]:
        """Extract explicit factual statements — things like 'X uses Y', 'X is configured with Y'."""
        memories = []
        fact_patterns = [
            r"(\w+)\s+(?:uses|is\s+built\s+with|runs\s+on|is\s+configured\s+with|depends\s+on)\s+(\w+)",
            r"(?:the\s+)?(\w+)\s+(?:API|endpoint|service)\s+(?:is\s+at|lives\s+at|runs\s+at)\s+(\S+)",
            r"(?:we\s+)?(?:use|have|run)\s+(?:the\s+)?(\w+)\s+(?:for|to|in)\s+(\w+)",
        ]
        for pattern in fact_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                if len(content) < 15:
                    continue
                if not any(m.content == content for m in memories):
                    memories.append(MemoryEntry(
                        type=MemoryType.FACT,
                        scope=MemoryScope.PROJECT,
                        content=content,
                        context=context or f"Learned from session {session_id}",
                        project=project,
                        tags=("fact",),
                    ))
        return memories

    def extract_manual(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        scope: MemoryScope = MemoryScope.PRIVATE,
        project: str = "",
        tags: tuple[str, ...] = (),
        context: str = "",
    ) -> MemoryEntry:
        """Manually create a memory entry (for when the AI explicitly states something)."""
        return MemoryEntry(
            type=memory_type,
            scope=scope,
            content=content,
            context=context,
            project=project,
            tags=tags,
        )
