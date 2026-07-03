
from typing import Any

from cognex_mcp.context import CognexContext


async def audit_get_recent(
    project: str,
    limit: int = 50,
) -> dict[str, Any]:
    if not project:
        raise ValueError("project is required")

    limit = max(1, min(limit, 100))
    ctx = CognexContext.get_instance()
    entries = ctx.audit.get_recent(project=project, limit=limit)

    return {
        "project":        project,
        "limit":          limit,
        "entries_count":  len(entries),
        "entries":        entries,
    }


async def audit_verify(
    log_id: str,
) -> dict[str, Any]:
    if not log_id:
        raise ValueError("log_id is required")

    ctx = CognexContext.get_instance()
    result = ctx.audit.verify_integrity(log_id=log_id)
    return result


async def audit_verify_chain(
    project: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    limit = max(1, min(limit, 10_000))
    ctx = CognexContext.get_instance()
    return ctx.audit.verify_chain(project=project or None, limit=limit)
