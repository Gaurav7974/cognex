"""
Ledger tools - decision recording and outcome tracking.
"""

from typing import Any

from substrate_mcp.context import SubstrateContext


async def ledger_record(
    tool_used: str,
    alternatives: list[str] | None = None,
    reasoning: str | None = None,
    context: str | None = None,
    project: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Record a decision in the ledger."""
    if not tool_used:
        raise ValueError("tool_used is required")

    ctx = SubstrateContext.get_instance()

    entry = ctx.ledger.record(
        tool_used=tool_used,
        alternatives=tuple(alternatives or []),
        reasoning=reasoning or "",
        context=context or "",
        project=project or "",
        session_id=session_id or "",
        tags=tuple(tags or []),
    )

    return {
        "decision_id": entry.id,
        "tool_used": entry.tool_used,
        "alternatives": list(entry.alternatives),
        "reasoning": entry.reasoning,
        "timestamp": entry.timestamp.isoformat(),
    }


async def ledger_outcome(
    decision_id: str,
    outcome: str,
    success: bool | None = None,
) -> dict[str, Any]:
    """Record outcome for a decision."""
    ctx = SubstrateContext.get_instance()

    entry = ctx.ledger.record_outcome(
        decision_id=decision_id,
        outcome=outcome,
        success=success,
    )

    if entry is None:
        raise ValueError(f"Decision not found: {decision_id}")

    return {
        "id": entry.id,
        "outcome": entry.outcome,
        "outcome_success": entry.outcome_success,
        "timestamp": entry.timestamp.isoformat(),
    }


async def ledger_find_similar(
    query: str,
    project: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Find similar past decisions."""
    ctx = SubstrateContext.get_instance()

    decisions = ctx.ledger.find_similar(
        context_query=query,
        project=project or "",
        limit=limit,
    )

    return {
        "count": len(decisions),
        "decisions": [
            {
                "id": d.id,
                "tool_used": d.tool_used,
                "reasoning": d.reasoning,
                "context": d.context,
                "outcome": d.outcome,
                "outcome_success": d.outcome_success,
                "timestamp": d.timestamp.isoformat(),
            }
            for d in decisions
        ],
    }
