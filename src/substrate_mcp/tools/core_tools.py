"""
Core substrate tools - session management and reporting.
"""

from typing import Any

from substrate_mcp.tools.dispatcher import run_in_thread


async def substrate_start_session(
    session_id: str,
    project: str = "",
) -> dict[str, Any]:
    """Start a new session in the cognitive substrate."""
    if not session_id:
        raise ValueError("session_id is required")

    ctx = SubstrateContext.get_instance()
    memories = await run_in_thread(
        ctx.substrate.start_session, session_id=session_id, project=project
    )

    return {
        "session_id": session_id,
        "project": project,
        "context_memories": [
            {
                "id": m.id,
                "content": m.content,
                "type": m.type.value,
                "tags": list(m.tags),
            }
            for m in memories
        ],
    }


async def substrate_end_session(
    summary: str = "",
    key_decisions: list[str] | None = None,
    tools_used: list[str] | None = None,
    errors: list[str] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict[str, Any]:
    """End the current session with summary and metrics."""
    ctx = SubstrateContext.get_instance()

    snapshot = ctx.substrate.end_session(
        summary=summary,
        key_decisions=tuple(key_decisions or []),
        tools_used=tuple(tools_used or []),
        errors=tuple(errors or []),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return {
        "session_id": snapshot.session_id,
        "summary": snapshot.summary,
        "key_decisions": list(snapshot.key_decisions),
        "tools_used": list(snapshot.tools_used),
        "input_tokens": snapshot.input_tokens,
        "output_tokens": snapshot.output_tokens,
        "started_at": snapshot.started_at.isoformat(),
        "ended_at": snapshot.ended_at.isoformat() if snapshot.ended_at else None,
    }


async def substrate_process_transcript(
    transcript: str,
    session_id: str | None = None,
    project: str | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Extract memories from a conversation transcript."""
    ctx = SubstrateContext.get_instance()

    result = await run_in_thread(
        ctx.substrate.process_transcript,
        transcript=transcript,
        session_id=session_id,
        project=project,
        context=context,
    )

    return {
        "extracted_count": result.count,
        "memories": [
            {"id": m.id, "content": m.content, "type": m.type.value}
            for m in result.memories
        ],
    }


async def substrate_report() -> dict[str, Any]:
    """Get substrate health and statistics report."""
    ctx = SubstrateContext.get_instance()
    report = ctx.substrate.report()

    return {
        "total_memories": report.total_memories,
        "total_sessions": report.total_sessions,
        "memories_by_type": report.memories_by_type,
        "top_projects": report.top_projects,
        "oldest_memory_age_days": report.oldest_memory_age_days,
        "newest_memory_age_days": report.newest_memory_age_days,
        "text": report.as_text(),
    }
