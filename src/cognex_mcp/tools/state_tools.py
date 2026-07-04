from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from cognex import MemoryScope, MemoryType
from cognex.models import StateUnit
from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_content, sanitize_project
from cognex_mcp.tools.dispatcher import run_in_thread


def _insert_question(store, question_id: str, content: str, project: str, scope: str, session_id: str, now: str) -> None:
    """Run on thread-pool — keeps DB writes off the async event loop."""
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO open_questions "
            "(question_id, content, project, scope, raised_in_session, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'open', ?)",
            (question_id, content, project, scope, session_id, now),
        )
        conn.commit()


def _fetch_and_resolve_question(store, question_id: str, answer_ref: str):
    """Run on thread-pool — fetch, validate, and update in one DB round-trip."""
    with store._connect() as conn:
        row = conn.execute(
            "SELECT * FROM open_questions WHERE question_id = ?", (question_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Question not found: {question_id}")
        conn.execute(
            "UPDATE open_questions SET status='answered', answer_ref=? WHERE question_id=?",
            (answer_ref, question_id),
        )
        conn.commit()
    return row


async def provenance_trace(node_or_ref_id: str, direction: str='origins', depth: int=3) -> dict[str, Any]:
    if direction not in {'origins', 'impacts'}:
        direction = 'origins'
    ctx = CognexContext.get_instance()
    return await run_in_thread(ctx.provenance.trace, node_or_ref_id, direction, depth)

async def provenance_link(from_ref: str, to_ref: str, edge_type: str, rationale: str='') -> dict[str, Any]:
    ctx = CognexContext.get_instance()
    edge_id = await run_in_thread(ctx.provenance.link, from_ref, to_ref, edge_type, rationale)
    return {'edge_id': edge_id, 'from_ref': from_ref, 'to_ref': to_ref, 'edge_type': edge_type}

async def question_raise(content: str, project: str='', scope: str='') -> dict[str, Any]:
    content = sanitize_content(content)
    project = sanitize_project(project)
    if not content:
        raise ValueError('content is required')
    ctx = CognexContext.get_instance()
    question_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    await run_in_thread(_insert_question, ctx.unit_store, question_id, content, project, scope, ctx.engine.current_session or '', now)
    ctx.provenance.ensure_node('question', 'open_questions', question_id, project, ctx.engine.current_session or '')
    return {'question_id': question_id, 'status': 'open', 'created_at': now}

async def question_resolve(question_id: str, answer_ref: str) -> dict[str, Any]:
    if not question_id or not answer_ref:
        raise ValueError('question_id and answer_ref are required')
    ctx = CognexContext.get_instance()
    row = await run_in_thread(_fetch_and_resolve_question, ctx.unit_store, question_id, answer_ref)
    q_node = ctx.provenance.ensure_node('question', 'open_questions', question_id, row['project'], row['raised_in_session'])
    answer_node = ctx.provenance.resolve_ref(answer_ref)
    edge_id = ctx.provenance.link(answer_node, q_node, 'answers', 'question resolved') if answer_node else ''
    return {'question_id': question_id, 'status': 'answered', 'answer_ref': answer_ref, 'edge_id': edge_id}

async def integrity_verify(project: str, ref_ids: list[str] | None=None) -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError('project is required')
    ctx = CognexContext.get_instance()
    result = await run_in_thread(ctx.integrity.verify, project, ref_ids)
    ctx.audit.append(event_type='integrity_root', session_id=ctx.engine.current_session, project=project, payload={'root_hash': result['root_hash'], 'record_count': result['record_count']})
    return result

async def handoff_create(project: str, goal_stack: list[str], in_flight_ops: list[str] | None=None, notes: str='', prior_baseline: str='') -> dict[str, Any]:
    project = sanitize_project(project)
    if not project:
        raise ValueError('project is required')
    ctx = CognexContext.get_instance()
    manifest = await run_in_thread(ctx.handoff.create, project, goal_stack, in_flight_ops or [], notes, prior_baseline)
    ctx.audit.append(event_type='handoff_created', session_id=ctx.engine.current_session, project=project, payload={'manifest_id': manifest['manifest_id'], 'merkle_root': manifest['merkle_root']})
    return {'manifest': manifest, 'serialized': __import__('json').dumps(manifest, separators=(',', ':'))}

async def handoff_resume(manifest_json: str | dict[str, Any]) -> dict[str, Any]:
    ctx = CognexContext.get_instance()
    briefing = await run_in_thread(ctx.handoff.resume, manifest_json)
    if briefing.get('status') == 'ready':
        ctx.audit.append(event_type='handoff_resumed', session_id=ctx.engine.current_session, project=briefing.get('project', ''), payload={'merkle_root': briefing.get('merkle_root', '')})
    return briefing

async def reconcile_resolve(conflict_id: str, resolution: str, rationale: str) -> dict[str, Any]:
    ctx = CognexContext.get_instance()
    result = await run_in_thread(ctx.reconciler.resolve, conflict_id, resolution, rationale)
    ctx.audit.append(event_type='reconcile_resolved', session_id=ctx.engine.current_session, project=None, payload={'conflict_id': conflict_id, 'resolution': resolution, 'rationale': rationale})
    return result

async def note_reasoning(kind: str, content: str, refs: list[str] | None=None, project: str='') -> dict[str, Any]:
    kind = kind.lower()
    content = sanitize_content(content)
    project = sanitize_project(project)
    refs = refs or []
    if not content:
        raise ValueError('content is required')
    ctx = CognexContext.get_instance()
    if kind == 'question':
        return await question_raise(content, project, '')
    if kind == 'rejection':
        decision = ctx.ledger.record(tool_used='note_reasoning', alternatives=(content,), reasoning='rejected during write-ahead reasoning', project=project, session_id=ctx.engine.current_session or '')
        await run_in_thread(lambda: None)
        return {'kind': kind, 'decision_id': decision.id}
    if kind == 'decision':
        decision = ctx.ledger.record(tool_used='note_reasoning', reasoning=content, project=project, session_id=ctx.engine.current_session or '')
        node = ctx.provenance.ensure_node('claim', 'decisions', decision.id, project, decision.session_id)
        for ref in refs:
            try:
                ctx.provenance.link(node, ref, 'derived_from', 'write-ahead reasoning reference')
            except ValueError:
                pass
        return {'kind': kind, 'decision_id': decision.id}
    unit_type = 'constraint' if kind == 'constraint' else 'task_state'
    status = 'assumed' if kind == 'assumption' else 'inferred'
    unit = StateUnit(unit_type=unit_type, content=content, project=project, session_id=ctx.engine.current_session or '', epistemic_status=status, depends_on=tuple(refs))
    await run_in_thread(ctx.unit_store.save, unit)
    node_type = 'constraint' if kind == 'constraint' else 'assumption'
    ctx.provenance.ensure_node(node_type, 'cognitive_units', unit.unit_id, project, unit.session_id)
    return {'kind': kind, 'unit_id': unit.unit_id, 'epistemic_status': status}