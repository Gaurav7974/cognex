
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import MemoryEntry, MemoryScope, MemoryType


@dataclass
class ExtractionResult:
    memories:       list[MemoryEntry]
    source_session: str
    count:          int
    patterns_fired: dict[str, int] = field(default_factory=dict)

    @property
    def memory_ids(self) -> tuple[str, ...]:
        return tuple(m.id for m in self.memories)


# Pattern definitions — (regex, label, confidence_weight)

_PREFERENCE_PATTERNS: list[tuple[str, str, float]] = [
    (r"(?:prefer|like to use|always use|don't use|avoid|never use)\s+(?:the\s+)?(\w+)", "pref:prefer", 0.85),
    (r"(?:I\s+)?(?:use|run|write)\s+(?:with|in|using)\s+(\w+)", "pref:use_with", 0.75),
    (r"(?:better\s+with|works\s+better\s+with|faster\s+with)\s+(\w+)",                 "pref:better_with", 0.80),
]

_DECISION_PATTERNS: list[tuple[str, str, float]] = [
    (r"(?:chose|choosing|decided|deciding|went\s+with|picked)\s+(?:the\s+)?(\w+)", "dec:chose", 0.90),
    (r"(?:instead\s+of|rather\s+than|over)\s+(\w+)",                               "dec:instead_of", 0.80),
    (r"(?:because|since|due\s+to)\s+(.+?)(?:\.|$)",                                "dec:reasoning", 0.70),
]

_LESSON_PATTERNS: list[tuple[str, str, float]] = [
    (r"(?:failed|broke|error|issue|bug|problem)\s+(?:with|in|on)\s+(\w+)", "lesson:failure", 0.90),
    (r"(?:don't|never)\s+(?:do|run|use|execute)\s+(.+?)(?:\.|$)",           "lesson:avoid", 0.85),
    (r"(?:worked|succeeded|fixed)\s+(?:when|by|using)\s+(\w+)",             "lesson:success", 0.80),
]

_PATTERN_PATTERNS: list[tuple[str, str, float]] = [
    (r"(?:always|usually|often|typically|every\s+time)\s+(\w+)", "pat:recurring", 0.80),
    (r"(?:again|repeated|same\s+issue|same\s+problem)",          "pat:repeat", 0.70),
]

_FACT_PATTERNS: list[tuple[str, str, float]] = [
    (r"(\w+)\s+(?:uses|is\s+built\s+with|runs\s+on|is\s+configured\s+with|depends\s+on)\s+(\w+)",
     "fact:dependency", 0.85),
    (r"(?:the\s+)?(\w+)\s+(?:API|endpoint|service)\s+(?:is\s+at|lives\s+at|runs\s+at)\s+(\S+)",
     "fact:service_location", 0.90),
    (r"(?:we\s+)?(?:use|have|run)\s+(?:the\s+)?(\w+)\s+(?:for|to|in)\s+(\w+)",
     "fact:usage", 0.80),
]

# Maximum transcript length to prevent DoS via huge inputs.
_MAX_TRANSCRIPT_CHARS = 50_000


class MemoryExtractor:

    def extract(
        self,
        transcript: str,
        session_id: str = "",
        project: str = "",
        context: str = "",
    ) -> ExtractionResult:
        if len(transcript) > _MAX_TRANSCRIPT_CHARS:
            transcript = transcript[:_MAX_TRANSCRIPT_CHARS]

        memories: list[MemoryEntry] = []
        patterns_fired: dict[str, int] = {}

        for extractor_fn, pattern_list in [
            (self._extract_typed, _PREFERENCE_PATTERNS),
            (self._extract_typed, _DECISION_PATTERNS),
            (self._extract_typed, _LESSON_PATTERNS),
            (self._extract_typed, _PATTERN_PATTERNS),
            (self._extract_typed, _FACT_PATTERNS),
        ]:
            found, fired = extractor_fn(
                transcript, session_id, project, context, pattern_list
            )
            memories.extend(found)
            for k, v in fired.items():
                patterns_fired[k] = patterns_fired.get(k, 0) + v

        return ExtractionResult(
            memories=memories,
            source_session=session_id,
            count=len(memories),
            patterns_fired=patterns_fired,
        )

    def _extract_typed(
        self,
        text: str,
        session_id: str,
        project: str,
        base_context: str,
        pattern_list: list[tuple[str, str, float]],
    ) -> tuple[list[MemoryEntry], dict[str, int]]:
        hit_map: dict[str, list[tuple[str, float]]] = {}

        for pattern, label, weight in pattern_list:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                content = match.group(0).strip()
                if len(content) < 5:
                    continue
                hit_map.setdefault(content, []).append((label, weight))

        _type_prefix_map = {
            "pref":   MemoryType.PREFERENCE,
            "dec":    MemoryType.DECISION,
            "lesson": MemoryType.LESSON,
            "pat":    MemoryType.PATTERN,
            "fact":   MemoryType.FACT,
        }
        _scope_map = {
            MemoryType.FACT: MemoryScope.PROJECT,
        }

        memories: list[MemoryEntry] = []
        fired_counts: dict[str, int] = {}

        for content, hits in hit_map.items():
            first_label = hits[0][0]
            prefix = first_label.split(":")[0]
            mem_type = _type_prefix_map.get(prefix, MemoryType.FACT)
            mem_scope = _scope_map.get(mem_type, MemoryScope.PRIVATE)

            avg_weight = sum(w for _, w in hits) / len(hits)
            corroboration = min(1.0, avg_weight + 0.05 * (len(hits) - 1) ** 0.5)
            relevance = round(max(0.5, min(1.0, corroboration)), 2)

            label_str = ", ".join(lbl for lbl, _ in hits)
            pattern_annotation = f"[patterns={label_str}] "
            ctx_text = (
                pattern_annotation
                + (base_context or f"session:{session_id}")
            )

            all_labels = tuple(lbl for lbl, _ in hits)
            memories.append(
                MemoryEntry(
                    type=mem_type,
                    scope=mem_scope,
                    content=content,
                    context=ctx_text,
                    project=project,
                    tags=all_labels,
                    relevance_score=relevance,
                )
            )

            for lbl, _ in hits:
                fired_counts[lbl] = fired_counts.get(lbl, 0) + 1

        return memories, fired_counts


