"""
Audit log tools - retrieve and verify audit entries.
"""

from typing import Any

from substrate_mcp.context import SubstrateContext


async def audit_get_recent(
    project: str,
    limit: int = 50,
) -> dict[str, Any]:
    """Get recent audit log entries for a project.
    
    Args:
        project: Project name to filter by
        limit: Max number of entries to return (default 50)
    
    Returns:
        dict with entries list containing audit log records
    """
    if not project:
        raise ValueError("project is required")
    
    limit = max(1, min(limit, 100))  # Clamp between 1 and 100
    
    ctx = SubstrateContext.get_instance()
    
    # Get recent entries from audit log
    entries = ctx.audit.get_recent(project=project, limit=limit)
    
    return {
        "project": project,
        "limit": limit,
        "entries_count": len(entries),
        "entries": entries,
    }


async def audit_verify(
    log_id: str,
) -> dict[str, Any]:
    """Verify integrity of an audit log entry.
    
    Args:
        log_id: Audit log entry ID to verify
    
    Returns:
        dict with validity status and details
    """
    if not log_id:
        raise ValueError("log_id is required")
    
    ctx = SubstrateContext.get_instance()
    
    # Verify the entry
    result = ctx.audit.verify_integrity(log_id=log_id)
    
    return {
        "log_id": log_id,
        "valid": result.get("valid", False),
        "checksum_match": result.get("checksum_match", False),
        "found": result.get("found", False),
        "message": result.get("message", ""),
    }
