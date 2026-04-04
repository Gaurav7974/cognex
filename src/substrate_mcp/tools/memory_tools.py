"""Memory tools - add, search, get context, decay."""

from typing import Any

from substrate import MemoryType, MemoryScope
from substrate_mcp.context import SubstrateContext


async def memory_add(
    content: str,
    memory_type: str = "fact",
    scope: str = "private",
    project: str = "",
    tags: list[str] | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Add a memory to the cognitive substrate."""
    if not content:
        raise ValueError("content is required")

    ctx = SubstrateContext.get_instance()

    tags_tuple = tuple(tags or [])

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
    ctx = SubstrateContext.get_instance()

    tags_tuple = tuple(tags or [])

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

    memories = ctx.substrate.store.search(
        query=query or "",
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
) -> dict[str, Any]:
    """Get relevant context memories for a query."""
    ctx = SubstrateContext.get_instance()

    memories = ctx.substrate.get_context(query=query or "", project=project)

    return {
        "count": len(memories),
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "type": m.type.value,
                "tags": list(m.tags),
            }
            for m in memories
        ],
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

    if factor < 0 or factor > 1:
        raise ValueError(f"factor must be between 0 and 1, got {factor}")

    removed_count = ctx.substrate.decay_memories(factor=factor)

    return {"decay_factor": factor, "memories_removed": removed_count}
