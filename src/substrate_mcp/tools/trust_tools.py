"""
Trust tools - approval checking and trust management.
"""

from typing import Any

from substrate_mcp.context import SubstrateContext


async def trust_check(
    tool_name: str,
    operation: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Check if an operation requires approval."""
    ctx = SubstrateContext.get_instance()

    requires_approval = ctx.trust.requires_approval(
        tool_name=tool_name,
        operation=operation or "",
        project=project or "",
    )

    trust_record = ctx.trust.get_trust(
        tool_name=tool_name,
        project=project or "",
    )

    return {
        "requires_approval": requires_approval,
        "trust_level": trust_record.trust_level.value,
        "trust_score": trust_record.trust_score,
        "approval_count": trust_record.approval_count,
        "denial_count": trust_record.denial_count,
        "violation_count": trust_record.violation_count,
    }


async def trust_record(
    action: str,
    tool_name: str,
    operation: str | None = None,
    context: str | None = None,
    project: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Record an approval, denial, or violation."""
    if action not in ("approval", "denial", "violation"):
        raise ValueError(
            f"action must be one of: approval, denial, violation, got {action!r}"
        )

    ctx = SubstrateContext.get_instance()

    if action == "approval":
        decision = ctx.trust.record_approval(
            tool_name=tool_name,
            operation=operation or "",
            context=context or "",
            project=project or "",
            reason=reason or "",
        )
    elif action == "denial":
        decision = ctx.trust.record_denial(
            tool_name=tool_name,
            operation=operation or "",
            context=context or "",
            project=project or "",
            reason=reason or "",
        )
    else:
        decision = ctx.trust.record_violation(
            tool_name=tool_name,
            operation=operation or "",
            context=context or "",
            project=project or "",
            reason=reason or "",
        )

    return {
        "id": decision.id,
        "action": action,
        "tool_name": tool_name,
        "approved": decision.approved,
        "trust_level_at_time": decision.trust_level_at_time.value,
        "timestamp": decision.timestamp.isoformat(),
    }


async def trust_get(
    tool_name: str,
    context: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Get trust record for a tool."""
    ctx = SubstrateContext.get_instance()

    record = ctx.trust.get_trust(
        tool_name=tool_name,
        context=context or "",
        project=project or "",
    )

    return {
        "tool_name": tool_name,
        "context": context or "",
        "trust_level": record.trust_level.value,
        "trust_score": record.trust_score,
        "approval_count": record.approval_count,
        "denial_count": record.denial_count,
        "violation_count": record.violation_count,
        "last_used": record.last_used.isoformat() if record.last_used else None,
        "first_seen": record.first_seen.isoformat(),
    }


async def trust_summary(project: str | None = None) -> dict[str, Any]:
    """Get trust summary for all tools or a project."""
    ctx = SubstrateContext.get_instance()

    records = ctx.trust.get_trust_summary(project=project or "")

    return {
        "count": len(records),
        "records": [
            {
                "tool_name": r.tool_name,
                "trust_level": r.trust_level.value,
                "trust_score": r.trust_score,
                "approval_count": r.approval_count,
                "denial_count": r.denial_count,
                "violation_count": r.violation_count,
            }
            for r in records
        ],
    }
