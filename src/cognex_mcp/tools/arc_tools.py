
from typing import Any

from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_project
from cognex_mcp.tools.dispatcher import run_in_thread


async def arc_start(
    project: str,
) -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError("project is required")

    ctx = CognexContext.get_instance()
    from cognex.arcs import SessionArcManager

    # We use a dummy or empty session_id to find or create the arc
    arc = await run_in_thread(
        SessionArcManager.get_or_create_arc,
        session_id="",
        project=project,
        store=ctx.engine.store,
    )

    return {
        "status": "success",
        "arc": arc,
    }


async def arc_close(
    arc_id: str,
) -> dict[str, Any]:
    if not arc_id:
        raise ValueError("arc_id is required")

    ctx = CognexContext.get_instance()
    from cognex.arcs import SessionArcManager

    success = await run_in_thread(
        SessionArcManager.close_arc,
        arc_id=arc_id,
        store=ctx.engine.store,
    )

    if not success:
        return {
            "status": "error",
            "message": f"Arc not found or already closed: {arc_id}",
        }

    # Fetch closed arc to show summary
    with ctx.engine.store._connect() as conn:
        try:
            row = conn.execute(
                "SELECT arc_summary FROM session_arcs WHERE arc_id = ?", (arc_id,)
            ).fetchone()
            summary = row["arc_summary"] if row else ""
        except Exception:
            summary = ""

    return {
        "status": "success",
        "arc_id": arc_id,
        "summary": summary,
    }


async def arc_get_context(
    project: str,
) -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError("project is required")

    ctx = CognexContext.get_instance()
    from cognex.arcs import SessionArcManager

    arc = await run_in_thread(
        SessionArcManager.get_active_arc,
        project=project,
        store=ctx.engine.store,
    )

    if not arc:
        return {
            "status": "success",
            "message": f"No active arc found for project '{project}'",
        }

    summary = await run_in_thread(
        SessionArcManager.summarize_arc,
        arc_id=arc["arc_id"],
        store=ctx.engine.store,
    )

    return {
        "status": "success",
        "arc": arc,
        "narrative_context": summary,
    }
