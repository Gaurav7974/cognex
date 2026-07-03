
from typing import Any

from cognex_mcp.context import CognexContext
from cognex_mcp.tools.dispatcher import run_in_thread


async def cognex_start_session(
    session_id: str,
    project: str = "",
) -> dict[str, Any]:
    if not session_id:
        raise ValueError("session_id is required")

    ctx = CognexContext.get_instance()
    memories = await run_in_thread(
        ctx.engine.start_session, session_id=session_id, project=project
    )

    # Audit log (direct call - AuditLog is thread-safe)
    ctx.audit.append(
        event_type="session_start",
        session_id=session_id,
        project=project,
        agent_id=None,
        payload={"project": project, "session_id": session_id},
    )

    # Session arc integration (P3.2)
    from cognex.arcs import SessionArcManager
    arc_info = await run_in_thread(
        SessionArcManager.get_active_arc, project=project, store=ctx.engine.store
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
        "active_arc": arc_info,
    }


async def cognex_end_session(
    summary: str = "",
    key_decisions: list[str] | None = None,
    tools_used: list[str] | None = None,
    errors: list[str] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

    snapshot = ctx.engine.end_session(
        summary=summary,
        key_decisions=tuple(key_decisions or []),
        tools_used=tuple(tools_used or []),
        errors=tuple(errors or []),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    # Audit log (direct call - AuditLog is thread-safe)
    ctx.audit.append(
        event_type="session_end",
        session_id=snapshot.session_id,
        project=snapshot.project,
        agent_id=None,
        payload={"session_id": snapshot.session_id, "summary": summary},
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


async def cognex_process_transcript(
    transcript: str,
    session_id: str | None = None,
    project: str | None = None,
    context: str = "",
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

    result = await run_in_thread(
        ctx.engine.process_transcript,
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


async def cognex_report() -> dict[str, Any]:
    ctx = CognexContext.get_instance()
    report = ctx.engine.report()

    return {
        "total_memories": report.total_memories,
        "total_sessions": report.total_sessions,
        "memories_by_type": report.memories_by_type,
        "top_projects": report.top_projects,
        "oldest_memory_age_days": report.oldest_memory_age_days,
        "newest_memory_age_days": report.newest_memory_age_days,
        "text": report.as_text(),
    }
