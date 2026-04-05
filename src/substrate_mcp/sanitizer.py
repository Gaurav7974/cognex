"""Input sanitization for Cognex MCP tools."""

import re

MAX_CONTENT_LENGTH = 500
MAX_TAG_LENGTH = 50
MAX_TAGS = 10
MAX_PROJECT_LENGTH = 100
MAX_QUERY_LENGTH = 200


def sanitize_content(content: str) -> str:
    """Sanitize memory content - strip control chars, cap length."""
    if not content:
        return ""
    # Strip control characters except newline and tab
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
    # Cap length
    return content[:MAX_CONTENT_LENGTH].strip()


def sanitize_project(project: str) -> str:
    """Sanitize project name."""
    if not project:
        return ""
    # Only allow alphanumeric, hyphens, underscores, dots
    project = re.sub(r"[^a-zA-Z0-9\-_\.]", "", project)
    return project[:MAX_PROJECT_LENGTH]


def sanitize_tags(tags: list) -> list[str]:
    """Sanitize tags list."""
    if not tags:
        return []
    clean = []
    for tag in tags[:MAX_TAGS]:
        tag = str(tag)
        tag = re.sub(r"[^a-zA-Z0-9\-_]", "", tag)
        if tag:
            clean.append(tag[:MAX_TAG_LENGTH])
    return clean


def sanitize_query(query: str) -> str:
    """Sanitize search query - prevent FTS5 injection."""
    if not query:
        return ""
    # Remove FTS5 special operators that could cause issues
    query = re.sub(r'["\*\^\(\)\{\}\[\]\\]', "", query)
    return query[:MAX_QUERY_LENGTH].strip()
