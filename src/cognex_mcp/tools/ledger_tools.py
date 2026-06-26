"""
Ledger tools - decision recording and outcome tracking.
"""

from typing import Any

from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_query


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

    ctx = CognexContext.get_instance()

    entry = ctx.ledger.record(
        tool_used=tool_used,
        alternatives=tuple(alternatives or []),
        reasoning=reasoning or "",
        context=context or "",
        project=project or "",
        session_id=session_id or "",
        tags=tuple(tags or []),
    )

    result = {
        "decision_id": entry.id,
        "tool_used": entry.tool_used,
        "alternatives": list(entry.alternatives),
        "reasoning": entry.reasoning,
        "timestamp": entry.timestamp.isoformat(),
    }

    # Warn if no active session
    if not ctx.engine.current_session:
        result["warning"] = "no active session — call cognex_start_session first"

    return result


async def ledger_outcome(
    decision_id: str,
    outcome: str,
    success: bool | None = None,
) -> dict[str, Any]:
    """Record outcome for a decision."""
    ctx = CognexContext.get_instance()

    entry = ctx.ledger.record_outcome(
        decision_id=decision_id,
        outcome=outcome,
        success=success,
    )

    if entry is None:
        raise ValueError(f"Decision not found: {decision_id}")

    # Trigger outcome feedback (P2.3)
    if success is not None:
        from cognex.feedback import OutcomeFeedback
        OutcomeFeedback.apply_outcome_feedback(
            session_id=entry.session_id,
            success=success,
            store=ctx.engine.store,
            ledger=ctx.ledger,
            audit=ctx.audit,
        )

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
    """Find similar past decisions.

    Sanitizes the query to prevent LIKE injection and wildcard abuse
    (e.g., "100%" matching every record).
    """
    # Sanitize query to prevent injection
    query = sanitize_query(query)
    if not query:
        raise ValueError("query is required and cannot be empty")

    ctx = CognexContext.get_instance()

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
