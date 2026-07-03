from datetime import datetime, timezone
from typing import Any
from cognex.models import StateUnit
from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_content, sanitize_project, sanitize_tags
from cognex_mcp.tools.dispatcher import run_in_thread
VALID_UNIT_TYPES = {'decision', 'constraint', 'progress', 'task_state'}

async def unit_commit(content: str, rationale: str='', unit_type: str='decision', scope: str='', confidence: float=1.0, tags: list[str] | None=None, project: str='', epistemic_status: str='assumed', verification_condition: str='', depends_on: list[str] | None=None, staleness_deadline: str | None=None) -> dict[str, Any]:
    content = sanitize_content(content)
    rationale = sanitize_content(rationale)
    project = sanitize_project(project)
    tags_list = sanitize_tags(tags or [])
    if not content:
        raise ValueError('content is required and cannot be empty')
    if unit_type not in VALID_UNIT_TYPES:
        unit_type = 'decision'
    if epistemic_status not in {'verified', 'assumed', 'inferred', 'unknown'}:
        epistemic_status = 'assumed'
    confidence = max(0.0, min(1.0, float(confidence)))
    ctx = CognexContext.get_instance()
    session_id = ctx.engine.current_session or ''
    unit = StateUnit(unit_type=unit_type, content=content, rationale=rationale, scope=scope, confidence=confidence, tags=tuple(tags_list), session_id=session_id, project=project, epistemic_status=epistemic_status, verification_condition=verification_condition, depends_on=tuple(depends_on or []), staleness_deadline=datetime.fromisoformat(staleness_deadline) if staleness_deadline else None)
    await run_in_thread(ctx.unit_store.save, unit)
    node_type = 'constraint' if unit_type == 'constraint' else 'assumption' if epistemic_status == 'assumed' else 'claim'
    ctx.provenance.ensure_node(node_type=node_type, ref_table='cognitive_units', ref_id=unit.unit_id, project=project, session_id=session_id)
    ctx.audit.append(event_type='unit_commit', session_id=session_id or None, project=project, agent_id=None, payload={'unit_id': unit.unit_id, 'unit_type': unit_type, 'project': project})
    return {'unit_id': unit.unit_id, 'unit_type': unit.unit_type, 'content': unit.content, 'rationale': unit.rationale, 'scope': unit.scope, 'confidence': unit.confidence, 'epistemic_status': unit.epistemic_status, 'verification_condition': unit.verification_condition, 'depends_on': list(unit.depends_on), 'created_at': unit.created_at.isoformat()}

async def unit_checkout(project: str, scope: str | None=None, unit_type_filter: str | None=None, session_summary: str='') -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError('project is required')
    ctx = CognexContext.get_instance()
    snapshot = await run_in_thread(ctx.unit_store.export_snapshot, project, session_summary, scope)
    all_units = await run_in_thread(ctx.unit_store.get_bundle, project, scope, True)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for unit in all_units:
        grouped.setdefault(unit.epistemic_status, []).append({'unit_id': unit.unit_id, 'unit_type': unit.unit_type, 'content': unit.content[:160], 'scope': unit.scope, 'confidence': unit.confidence, 'verification_condition': unit.verification_condition})
    with ctx.unit_store._connect() as conn:
        q_rows = conn.execute("SELECT question_id, content, scope FROM open_questions WHERE project = ? AND status = 'open' ORDER BY created_at DESC LIMIT 25", (project,)).fetchall()
    snapshot['epistemic_classes'] = grouped
    snapshot['open_questions'] = [{'question_id': r['question_id'], 'content': r['content'][:160], 'scope': r['scope']} for r in q_rows]
    if unit_type_filter:
        filtered_snapshot = snapshot.copy()
        for category in ['task_states', 'decisions', 'constraints', 'progress']:
            filtered_snapshot[category] = [u for u in filtered_snapshot[category] if u.get('unit_type') == unit_type_filter]
        return filtered_snapshot
    return snapshot

async def unit_search(query: str | None=None, project: str='', unit_type_filter: str | None=None, limit: int=20) -> dict[str, Any]:
    from cognex_mcp.sanitizer import sanitize_query
    query = sanitize_query(query or '')
    project = sanitize_project(project)
    limit = min(int(limit), 50)
    ctx = CognexContext.get_instance()
    units = await run_in_thread(ctx.unit_store.search, query=query, project=project, unit_type=unit_type_filter, limit=limit)
    return {'count': len(units), 'units': [{'unit_id': u.unit_id, 'unit_type': u.unit_type, 'content': u.content, 'rationale': u.rationale, 'scope': u.scope, 'confidence': u.confidence, 'created_at': u.created_at.isoformat()} for u in units]}

async def unit_mark_overridden(unit_id: str) -> dict[str, Any]:
    if not unit_id:
        raise ValueError('unit_id is required')
    ctx = CognexContext.get_instance()
    unit = await run_in_thread(ctx.unit_store.get, unit_id)
    if not unit:
        raise ValueError(f'Unit not found: {unit_id}')
    await run_in_thread(ctx.unit_store.mark_overridden, unit_id)
    ctx.audit.append(event_type='unit_overridden', session_id=ctx.engine.current_session, project=unit.project, agent_id=None, payload={'unit_id': unit_id, 'reason': 'contradicted'})
    return {'unit_id': unit_id, 'status': 'overridden', 'message': f'Unit {unit_id} marked as overridden, confidence decayed by 0.2'}

async def unit_verify(unit_id: str, staleness_deadline: str | None=None) -> dict[str, Any]:
    if not unit_id:
        raise ValueError('unit_id is required')
    ctx = CognexContext.get_instance()
    unit = await run_in_thread(ctx.unit_store.get, unit_id)
    if not unit:
        raise ValueError(f'Unit not found: {unit_id}')
    await run_in_thread(ctx.unit_store.verify, unit_id, staleness_deadline)
    return {'unit_id': unit_id, 'status': 'verified', 'last_verified': datetime.now(timezone.utc).isoformat(), 'staleness_deadline': staleness_deadline}

async def unit_get_relevant(query: str, project: str, task_context: str='', limit: int=10) -> dict[str, Any]:
    from cognex_mcp.sanitizer import sanitize_query
    query = sanitize_query(query)
    project = sanitize_project(project)
    if not query or not project:
        raise ValueError('query and project are required')
    limit = min(int(limit), 50)
    ctx = CognexContext.get_instance()
    units = await run_in_thread(ctx.unit_store.get_relevant_units, query=query, project=project, task_context=task_context, limit=limit)
    return {'count': len(units), 'units': [{'unit_id': u.unit_id, 'unit_type': u.unit_type, 'content': u.content, 'rationale': u.rationale, 'scope': u.scope, 'confidence': u.confidence, 'staleness': ctx.unit_store.check_staleness(u.unit_id), 'relevance_score': getattr(u, '_relevance_score', 0)} for u in units]}

async def unit_export_snapshot(project: str, session_summary: str, scope: str | None=None) -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError('project is required')
    ctx = CognexContext.get_instance()
    snapshot = await run_in_thread(ctx.unit_store.export_snapshot, project, session_summary, scope)
    return snapshot

async def unit_decay_stale(project: str, threshold: float=0.8) -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError('project is required')
    threshold = max(0.0, min(1.0, float(threshold)))
    ctx = CognexContext.get_instance()
    all_units = await run_in_thread(ctx.unit_store.get_bundle, project, None, True)
    affected_units = []
    for u in all_units:
        if ctx.unit_store.check_staleness(u.unit_id) > threshold:
            affected_units.append(u.unit_id)
    count = await run_in_thread(ctx.unit_store.decay_stale_units, project, threshold)
    return {'decayed_count': count, 'affected_unit_ids': affected_units}