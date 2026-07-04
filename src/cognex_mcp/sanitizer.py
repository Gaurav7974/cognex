
from __future__ import annotations

import re

# Length limits

# Per memory-type content length caps (characters, not bytes).
# The key matches MemoryType.value strings.
_CONTENT_LENGTH_BY_TYPE: dict[str, int] = {
    "fact":       20000,
    "preference": 20000,
    "pattern":    20000,
    "decision":   20000,
    "lesson":     20000,
    "context":    20000,
}

# Fallback for unknown/unspecified types.
_DEFAULT_CONTENT_LENGTH = 20000

# Other field limits.
MAX_TAG_LENGTH     = 50
MAX_TAGS           = 10
MAX_PROJECT_LENGTH = 100
MAX_QUERY_LENGTH   = 200
MAX_RATIONALE_LENGTH = 2000


# Sanitisers

def sanitize_content(content: str, memory_type: str | None = None) -> str:
    if not content:
        return ""
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
    limit = _CONTENT_LENGTH_BY_TYPE.get(memory_type or "", _DEFAULT_CONTENT_LENGTH)
    return content[:limit].strip()


def sanitize_rationale(rationale: str) -> str:
    if not rationale:
        return ""
    rationale = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", rationale)
    return rationale[:MAX_RATIONALE_LENGTH].strip()


def sanitize_project(project: str) -> str:
    if not project:
        return ""
    project = re.sub(r"[^a-zA-Z0-9\-_.]", "", project)
    return project[:MAX_PROJECT_LENGTH]


def sanitize_tags(tags) -> list[str]:
    """Accept list or comma-separated string (some harnesses send either)."""
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    clean: list[str] = []
    for raw_tag in tags[:MAX_TAGS]:
        tag = re.sub(r"[^a-zA-Z0-9\-_]", "", str(raw_tag))
        if tag:
            clean.append(tag[:MAX_TAG_LENGTH])
    return clean


def sanitize_query(query: str) -> str:
    if not query:
        return ""
    query = re.sub(r'["*^(){}\[\]\\]', "", query)
    return query.lower()[:MAX_QUERY_LENGTH].strip()
