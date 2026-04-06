"""Memory tools - add, search, get context, decay."""

from typing import Any

from substrate import MemoryType, MemoryScope
from substrate_mcp.context import SubstrateContext
from substrate_mcp.sanitizer import (
    sanitize_content,
    sanitize_project,
    sanitize_tags,
    sanitize_query,
)
from substrate_mcp.tools.dispatcher import run_in_thread

# Hard limits - never exceed these
MAX_SEARCH_LIMIT = 50
MAX_CONTEXT_LIMIT = 10
MAX_DECAY_FACTOR_HIGH = 1.0
MAX_DECAY_FACTOR_LOW = 0.0


async def memory_add(
    content: str,
    memory_type: str = "fact",
    scope: str = "private",
    project: str = "",
    tags: list[str] | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Add a memory to the cognitive substrate."""
    # Sanitize inputs
    content = sanitize_content(content)
    project = sanitize_project(project)
    tags_list = sanitize_tags(tags or [])
    context = sanitize_content(context)

    if not content:
        raise ValueError("content is required and cannot be empty")

    ctx = SubstrateContext.get_instance()

    tags_tuple = tuple(tags_list)

    # Convert string to enum
    try:
        mem_type = MemoryType[memory_type.upper()]
    except KeyError:
        mem_type = MemoryType.FACT

    try:
        mem_scope = MemoryScope[scope.upper()]
    except KeyError:
        mem_scope = MemoryScope.PRIVATE

    entry = ctx.substrate.add_memory(
        content=content,
        memory_type=mem_type,
        scope=mem_scope,
        project=project,
        tags=tags_tuple,
        context=context,
    )

    return {
        "id": entry.id,
        "content": entry.content,
        "type": entry.type.value,
        "scope": entry.scope.value,
        "created_at": entry.created_at.isoformat(),
    }


async def memory_search(
    query: str | None = None,
    memory_type: str | None = None,
    project: str = "",
    scope: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search memories with filters."""
    # Sanitize inputs
    query = sanitize_query(query or "")
    project = sanitize_project(project)
    tags_list = sanitize_tags(tags or [])

    # Apply hard limit
    limit = min(int(limit), MAX_SEARCH_LIMIT)

    ctx = SubstrateContext.get_instance()

    tags_tuple = tuple(tags_list)

    # Convert string to enum
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType[memory_type.upper()]
        except KeyError:
            pass

    mem_scope = None
    if scope:
        try:
            mem_scope = MemoryScope[scope.upper()]
        except KeyError:
            pass

    memories = await run_in_thread(
        ctx.substrate.store.search,
        query=query,
        memory_type=mem_type,
        project=project,
        scope=mem_scope,
        tags=tags_tuple,
        limit=limit,
    )

    return {
        "count": len(memories),
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "type": m.type.value,
                "scope": m.scope.value,
                "project": m.project,
                "tags": list(m.tags),
                "relevance": m.relevance_score,
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ],
    }


async def memory_get_context(
    query: str | None = None,
    project: str = "",
    limit: int = 5,
    format: str = "medium",
) -> dict[str, Any]:
    """Get relevant context memories for a query.

    Args:
        query: Search query for finding relevant memories
        project: Filter to specific project
        limit: Max memories to return (capped at 10)
        format: Output format - 'minimal', 'medium', or 'full'
    """
    # Sanitize inputs
    query = sanitize_query(query or "")
    project = sanitize_project(project)

    # Apply hard limit
    limit = min(int(limit), MAX_CONTEXT_LIMIT)

    ctx = SubstrateContext.get_instance()

    memories = await run_in_thread(
        ctx.substrate.get_context, query=query, project=project, limit=limit
    )

    # Strip common filler prefixes to compress content
    FILLER_PREFIXES = [
        "User always ",
        "User prefers ",
        "User ",
        "Always ",
        "Never ",
        "All ",
        "The ",
        "Must ",
        "Should ",
    ]

    def strip_filler(text: str) -> str:
        for prefix in FILLER_PREFIXES:
            if text.startswith(prefix):
                return text[len(prefix) :]
        return text

    type_short_map = {
        "preference": "pref",
        "decision": "dec",
        "pattern": "pat",
        "fact": "fact",
        "lesson": "lesson",
    }

    if format == "minimal":
        # Group by type, merge into single dense lines
        groups: dict[str, list[str]] = {}
        for m in memories:
            ts = type_short_map.get(m.type.value or "fact", "fact")
            content = strip_filler(m.content)
            # Truncate to keyword-length phrase
            words = content.split()[:6]
            phrase = " ".join(words)
            groups.setdefault(ts, []).append(phrase)

        lines: list[str] = []
        for ts, phrases in groups.items():
            lines.append(f"[{ts}] {'; '.join(phrases)}")
        return {"context": "\n".join(lines), "count": len(memories)}

    elif format == "medium":
        # Group by type, return compact dict — no score, no id, no timestamps
        groups: dict[str, list[str]] = {}
        for m in memories:
            ts = type_short_map.get(m.type.value or "fact", "fact")
            content = strip_filler(m.content)
            groups.setdefault(ts, []).append(content)

        return {"memories": groups, "count": len(memories)}

    else:  # full
        return {
            "memories": [
                {
                    "content": m.content,
                    "type": m.type.value,
                    "score": round(m.relevance_score, 2),
                    "tags": list(m.tags),
                    "id": m.id,
                }
                for m in memories
            ],
            "count": len(memories),
        }


async def memory_decay(
    factor: float = 0.95,
) -> dict[str, Any]:
    """Apply aging/decay to all memories."""
    ctx = SubstrateContext.get_instance()

    if not isinstance(factor, (int, float)):
        raise ValueError(
            f"factor must be a number between 0 and 1, got {type(factor).__name__}"
        )

    factor = float(factor)
    if not (MAX_DECAY_FACTOR_LOW <= factor <= MAX_DECAY_FACTOR_HIGH):
        raise ValueError(f"factor must be between 0 and 1, got {factor}")

    removed_count = ctx.substrate.decay_memories(factor=factor)

    return {"decay_factor": factor, "memories_removed": removed_count}
