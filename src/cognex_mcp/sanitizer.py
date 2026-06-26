"""Input sanitisation for Cognex MCP tools.

Every string that enters the system from an agent passes through one of
these functions before being written to the database.  The goals are:

- **Control-character stripping:** remove bytes that cannot appear in
  well-formed UTF-8 prose (NUL, BEL, DEL, etc.) while preserving
  newline (\\x0a) and tab (\\x09) which are valid in structured content.

- **Length capping:** prevent runaway inputs from filling disk or
  causing excessive BM25 indexing work.  Limits are *type-aware*:
  short types (fact, preference, pattern) get a tighter cap than
  rich types (decision, lesson, context) which legitimately carry
  longer rationale text.

- **FTS5 safety:** strip characters that have special meaning in the
  FTS5 query parser so that raw user text cannot accidentally trigger
  syntax errors when it ends up in a MATCH expression.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Length limits
# ---------------------------------------------------------------------------

# Per memory-type content length caps (characters, not bytes).
# The key matches MemoryType.value strings.
_CONTENT_LENGTH_BY_TYPE: dict[str, int] = {
    "fact":       500,
    "preference": 500,
    "pattern":    500,
    "decision":   2000,
    "lesson":     2000,
    "context":    2000,
}

# Fallback for unknown/unspecified types.
_DEFAULT_CONTENT_LENGTH = 500

# Other field limits.
MAX_TAG_LENGTH     = 50
MAX_TAGS           = 10
MAX_PROJECT_LENGTH = 100
MAX_QUERY_LENGTH   = 200
MAX_RATIONALE_LENGTH = 2000


# ---------------------------------------------------------------------------
# Sanitisers
# ---------------------------------------------------------------------------

def sanitize_content(content: str, memory_type: str | None = None) -> str:
    """Sanitise memory content.

    Strips control characters (preserving \\n and \\t), lower-cases, and
    caps length according to the memory type.

    Args:
        content: Raw content string from the agent.
        memory_type: Optional MemoryType value string (e.g. ``"decision"``).
            When provided, the appropriate per-type length limit is applied.
            When omitted, the conservative default limit is used.

    Returns:
        The cleaned, length-capped string.
    """
    if not content:
        return ""
    # Strip C0/C1 control characters except LF (\\x0a) and HT (\\x09).
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
    limit = _CONTENT_LENGTH_BY_TYPE.get(memory_type or "", _DEFAULT_CONTENT_LENGTH)
    return content.lower()[:limit].strip()


def sanitize_rationale(rationale: str) -> str:
    """Sanitise a rationale or reasoning string (used by cognitive units).

    Applies the same control-character filter as ``sanitize_content`` but
    uses the larger rationale limit, since rationale text is structurally
    always rich prose.
    """
    if not rationale:
        return ""
    rationale = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", rationale)
    return rationale[:MAX_RATIONALE_LENGTH].strip()


def sanitize_project(project: str) -> str:
    """Sanitise a project name.

    Only alphanumerics, hyphens, underscores, and dots are allowed.
    This keeps project names safe for use as directory names, index
    key fragments, and FTS5 column values.
    """
    if not project:
        return ""
    project = re.sub(r"[^a-zA-Z0-9\-_.]", "", project)
    return project[:MAX_PROJECT_LENGTH]


def sanitize_tags(tags: list) -> list[str]:
    """Sanitise a list of tag strings.

    Normalises each tag to alphanumerics, hyphens, and underscores only,
    strips empties, and enforces the maximum tag count and per-tag length.
    """
    if not tags:
        return []
    clean: list[str] = []
    for raw_tag in tags[:MAX_TAGS]:
        tag = re.sub(r"[^a-zA-Z0-9\-_]", "", str(raw_tag))
        if tag:
            clean.append(tag[:MAX_TAG_LENGTH])
    return clean


def sanitize_query(query: str) -> str:
    """Sanitise a search query.

    Removes FTS5 special-operator characters that could cause parse errors
    when the query is embedded in a MATCH expression.  The result is safe
    to pass directly to ``_escape_fts5_query()`` in the store layer.
    """
    if not query:
        return ""
    query = re.sub(r'["*^(){}\[\]\\]', "", query)
    return query.lower()[:MAX_QUERY_LENGTH].strip()
