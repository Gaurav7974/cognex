# Cognitive Unit tools - commit, checkout, search, mark overridden, verify.

from datetime import datetime, timezone
from typing import Any

from substrate.models import CognitiveUnit
from substrate_mcp.context import SubstrateContext
from substrate_mcp.sanitizer import (
    sanitize_content,
    sanitize_project,
    sanitize_tags,
)
from substrate_mcp.tools.dispatcher import run_in_thread

# Valid unit types
VALID_UNIT_TYPES = {"decision", "constraint", "progress", "task_state"}


async def unit_commit(
    content: str,
    rationale: str = "",
    unit_type: str = "decision",
    scope: str = "",
    confidence: float = 1.0,
    tags: list[str] | None = None,
    project: str = "",
) -> dict[str, Any]:
    # Create and save a CognitiveUnit.
    # Sanitize inputs
    content = sanitize_content(content)
    rationale = sanitize_content(rationale)
    project = sanitize_project(project)
    tags_list = sanitize_tags(tags or [])

    if not content:
        raise ValueError("content is required and cannot be empty")

    # Validate unit_type
    if unit_type not in VALID_UNIT_TYPES:
        unit_type = "decision"

    # Clamp confidence
    confidence = max(0.0, min(1.0, float(confidence)))

    ctx = SubstrateContext.get_instance()

    # Get session_id from substrate if available
    session_id = ctx.substrate.current_session or ""

    unit = CognitiveUnit(
        unit_type=unit_type,
        content=content,
        rationale=rationale,
        scope=scope,
        confidence=confidence,
        tags=tuple(tags_list),
        session_id=session_id,
        project=project,
    )

    # Save in thread pool
    await run_in_thread(ctx.unit_store.save, unit)

    return {
        "unit_id": unit.unit_id,
        "unit_type": unit.unit_type,
        "content": unit.content,
        "rationale": unit.rationale,
        "scope": unit.scope,
        "confidence": unit.confidence,
        "created_at": unit.created_at.isoformat(),
    }


async def unit_checkout(
    project: str,
    scope: str | None = None,
    unit_type_filter: str | None = None,
    session_summary: str = "",
) -> dict[str, Any]:
    # Get cognitive bundle for a project/scope as structured JSON snapshot.
    project = sanitize_project(project)

    if not project:
        raise ValueError("project is required")

    ctx = SubstrateContext.get_instance()

    # Get snapshot in thread pool
    snapshot = await run_in_thread(
        ctx.unit_store.export_snapshot, project, session_summary, scope
    )

    # Filter by unit_type if specified (legacy compatibility)
    if unit_type_filter:
        # Only keep units of the specified type across categories
        filtered_snapshot = snapshot.copy()
        for category in ["task_states", "decisions", "constraints", "progress"]:
            filtered_snapshot[category] = [
                u
                for u in filtered_snapshot[category]
                if u.get("unit_type") == unit_type_filter
            ]
        return filtered_snapshot

    return snapshot


async def unit_search(
    query: str | None = None,
    project: str = "",
    unit_type_filter: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    # FTS search over cognitive units.
    from substrate_mcp.sanitizer import sanitize_query

    query = sanitize_query(query or "")
    project = sanitize_project(project)

    # Apply hard limit
    limit = min(int(limit), 50)

    ctx = SubstrateContext.get_instance()

    # Search in thread pool
    units = await run_in_thread(
        ctx.unit_store.search,
        query=query,
        project=project,
        unit_type=unit_type_filter,
        limit=limit,
    )

    return {
        "count": len(units),
        "units": [
            {
                "unit_id": u.unit_id,
                "unit_type": u.unit_type,
                "content": u.content,
                "rationale": u.rationale,
                "scope": u.scope,
                "confidence": u.confidence,
                "created_at": u.created_at.isoformat(),
            }
            for u in units
        ],
    }


async def unit_mark_overridden(unit_id: str) -> dict[str, Any]:
    # Mark a unit as contradicted and decay confidence by 0.2.
    if not unit_id:
        raise ValueError("unit_id is required")

    ctx = SubstrateContext.get_instance()

    # Check if unit exists
    unit = await run_in_thread(ctx.unit_store.get, unit_id)
    if not unit:
        raise ValueError(f"Unit not found: {unit_id}")

    # Mark overridden in thread pool
    await run_in_thread(ctx.unit_store.mark_overridden, unit_id)

    return {
        "unit_id": unit_id,
        "status": "overridden",
        "message": f"Unit {unit_id} marked as overridden, confidence decayed by 0.2",
    }


async def unit_verify(unit_id: str) -> dict[str, Any]:
    # Confirm a unit still holds and update last_verified.
    if not unit_id:
        raise ValueError("unit_id is required")

    ctx = SubstrateContext.get_instance()

    # Check if unit exists
    unit = await run_in_thread(ctx.unit_store.get, unit_id)
    if not unit:
        raise ValueError(f"Unit not found: {unit_id}")

    # Verify in thread pool
    await run_in_thread(ctx.unit_store.verify, unit_id)

    return {
        "unit_id": unit_id,
        "status": "verified",
        "last_verified": datetime.now(timezone.utc).isoformat(),
    }


async def unit_get_relevant(
    query: str,
    project: str,
    task_context: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    # Get relevant units with FTS search and scoring.
    from substrate_mcp.sanitizer import sanitize_query

    query = sanitize_query(query)
    project = sanitize_project(project)

    if not query or not project:
        raise ValueError("query and project are required")

    # Apply hard limit
    limit = min(int(limit), 50)

    ctx = SubstrateContext.get_instance()

    # Get relevant units in thread pool
    units = await run_in_thread(
        ctx.unit_store.get_relevant_units,
        query=query,
        project=project,
        task_context=task_context,
        limit=limit,
    )

    return {
        "count": len(units),
        "units": [
            {
                "unit_id": u.unit_id,
                "unit_type": u.unit_type,
                "content": u.content,
                "rationale": u.rationale,
                "scope": u.scope,
                "confidence": u.confidence,
                "staleness": ctx.unit_store.check_staleness(u.unit_id),
                "relevance_score": getattr(u, "_relevance_score", 0),
            }
            for u in units
        ],
    }


async def unit_export_snapshot(
    project: str,
    session_summary: str,
    scope: str | None = None,
) -> dict[str, Any]:
    # Export full cognitive snapshot.
    project = sanitize_project(project)

    if not project:
        raise ValueError("project is required")

    ctx = SubstrateContext.get_instance()

    # Get snapshot in thread pool
    snapshot = await run_in_thread(
        ctx.unit_store.export_snapshot, project, session_summary, scope
    )

    return snapshot


async def unit_decay_stale(
    project: str,
    threshold: float = 0.8,
) -> dict[str, Any]:
    # Decay stale units above threshold.
    project = sanitize_project(project)

    if not project:
        raise ValueError("project is required")

    threshold = max(0.0, min(1.0, float(threshold)))

    ctx = SubstrateContext.get_instance()

    # Get affected units first
    all_units = await run_in_thread(ctx.unit_store.get_bundle, project, None, True)
    affected_units = []
    for u in all_units:
        if ctx.unit_store.check_staleness(u.unit_id) > threshold:
            affected_units.append(u.unit_id)

    # Decay them
    count = await run_in_thread(ctx.unit_store.decay_stale_units, project, threshold)

    return {
        "decayed_count": count,
        "affected_unit_ids": affected_units,
    }
