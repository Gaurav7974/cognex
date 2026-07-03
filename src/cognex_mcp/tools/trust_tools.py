
from typing import Any

from cognex_mcp.context import CognexContext


async def trust_query(
    tool_name: str = "",
    project: str = "",
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

    if not tool_name:
        records = ctx.trust.get_trust_summary(project=project)
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

    requires_approval = ctx.trust.requires_approval(
        tool_name=tool_name,
        project=project,
    )
    record = ctx.trust.get_trust(tool_name=tool_name, project=project)
    return {
        "tool_name": tool_name,
        "requires_approval": requires_approval,
        "trust_level": record.trust_level.value,
        "trust_score": record.trust_score,
        "approval_count": record.approval_count,
        "denial_count": record.denial_count,
        "violation_count": record.violation_count,
        "last_used": record.last_used.isoformat() if record.last_used else None,
        "first_seen": record.first_seen.isoformat(),
    }


async def trust_manage(
    action: str | None = None,
    tool_name: str = "",
    operation: str = "",
    context: str = "",
    project: str = "",
    reason: str = "",
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

    if action and action in ("approval", "denial", "violation"):
        if action == "approval":
            decision = ctx.trust.record_approval(
                tool_name=tool_name,
                operation=operation,
                context=context,
                project=project,
                reason=reason,
            )
        elif action == "denial":
            decision = ctx.trust.record_denial(
                tool_name=tool_name,
                operation=operation,
                context=context,
                project=project,
                reason=reason,
            )
        else:
            decision = ctx.trust.record_violation(
                tool_name=tool_name,
                operation=operation,
                context=context,
                project=project,
                reason=reason,
            )

        result: dict[str, Any] = {
            "id": decision.id,
            "action": action,
            "tool_name": tool_name,
            "approved": decision.approved,
            "trust_level_at_time": decision.trust_level_at_time.value,
            "timestamp": decision.timestamp.isoformat(),
        }
        if not ctx.engine.current_session:
            result["warning"] = "no active session — call cognex_start_session first"
        return result

    # No action → summary.
    records = ctx.trust.get_trust_summary(project=project)
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


async def trust_check(
    tool_name: str,
    operation: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    return await trust_query(tool_name=tool_name, project=project or "")


async def trust_record(
    action: str,
    tool_name: str,
    operation: str | None = None,
    context: str | None = None,
    project: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return await trust_manage(
        action=action,
        tool_name=tool_name,
        operation=operation or "",
        context=context or "",
        project=project or "",
        reason=reason or "",
    )


async def trust_get(
    tool_name: str,
    context: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()
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
    ctx = CognexContext.get_instance()
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
