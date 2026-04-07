# MCP tools for pattern analysis.

from typing import Any
from substrate_mcp.context import SubstrateContext
from substrate.patterns import PatternAnalyzer


async def pattern_analyze(
    project: str | None = None, save_patterns: bool = True
) -> dict[str, Any]:
    # Analyze decision history for behavioral patterns
    ctx = SubstrateContext.get_instance()
    analyzer = PatternAnalyzer(ledger=ctx.ledger, store=ctx.substrate.store)

    stats = analyzer.get_stats(project or "")
    insights = analyzer.analyze_all(project or "")

    saved = 0
    if save_patterns and insights:
        saved = analyzer.save_patterns(insights, project or "")

    return {
        "stats": stats,
        "patterns_found": len(insights),
        "patterns_saved": saved,
        "patterns": [
            {
                "type": i.pattern_type,
                "description": i.description,
                "confidence": round(i.confidence, 2),
                "sample_size": i.sample_size,
                "details": i.details,
            }
            for i in insights
        ],
        "message": _summary(stats, insights),
    }


async def pattern_stats(project: str | None = None) -> dict[str, Any]:
    # Get decision stats for pattern analysis readiness
    ctx = SubstrateContext.get_instance()
    analyzer = PatternAnalyzer(ledger=ctx.ledger, store=ctx.substrate.store)
    stats = analyzer.get_stats(project or "")

    if stats["total"] == 0:
        rec = "No decisions recorded. Use ledger_record to track decisions."
    elif stats["with_outcomes"] == 0:
        rec = f"{stats['total']} decisions but no outcomes. Use ledger_outcome."
    elif not stats["ready"]:
        rec = f"Need {5 - stats['with_outcomes']} more outcomes for analysis."
    else:
        rec = "Ready for pattern_analyze."

    return {**stats, "recommendation": rec}


def _summary(stats: dict, insights: list) -> str:
    if stats["total"] == 0:
        return "No decisions recorded."
    if stats["with_outcomes"] == 0:
        return f"{stats['total']} decisions but no outcomes recorded."
    if not insights:
        if stats["with_outcomes"] < 5:
            return f"Need more data ({stats['with_outcomes']}/5 outcomes)."
        return "No significant patterns detected."

    lines = [i.description for i in insights[:3]]
    if len(insights) > 3:
        lines.append(f"...and {len(insights) - 3} more")
    return "Patterns:\n• " + "\n• ".join(lines)
