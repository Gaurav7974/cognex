"""Audit log tools — retrieve and verify audit entries."""

from typing import Any

from cognex_mcp.context import CognexContext


async def audit_get_recent(
    project: str,
    limit: int = 50,
) -> dict[str, Any]:
    """Get recent audit log entries for a project.

    Args:
        project: Project name to filter by.
        limit: Max number of entries to return (1–100).

    Returns:
        Dict with ``entries`` list containing audit log records.
    """
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
    """Verify the checksum integrity of a single audit log entry.

    Args:
        log_id: Audit log entry ID to verify.

    Returns:
        Dict with ``valid`` (bool) and diagnostic fields.
    """
    if not log_id:
        raise ValueError("log_id is required")

    ctx = CognexContext.get_instance()
    result = ctx.audit.verify_integrity(log_id=log_id)
    return result


async def audit_verify_chain(
    project: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    """Walk the full audit log hash chain and verify every link.

    Checks that:
    1. Each entry's checksum is correct (covers content + prev_checksum).
    2. Each entry's prev_checksum matches the previous entry's checksum.

    A broken link indicates that a log entry was deleted or modified,
    which constitutes tampering with the audit trail.

    Args:
        project: Optional project filter.  Empty string checks all entries.
        limit:   Maximum entries to scan (default 200).

    Returns:
        Dict with:
        - ``valid``           (bool) — True iff the entire scanned chain is intact.
        - ``entries_checked`` (int)  — Number of entries verified.
        - ``first_broken_at`` (str | None) — log_id of the first broken link.
        - ``broken_entries``  (list[str]) — All broken log_ids.
    """
    limit = max(1, min(limit, 10_000))
    ctx = CognexContext.get_instance()
    return ctx.audit.verify_chain(project=project or None, limit=limit)
