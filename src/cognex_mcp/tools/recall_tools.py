from __future__ import annotations
from typing import Any
from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_project, sanitize_query, sanitize_tags
from cognex_mcp.tools.dispatcher import run_in_thread
MAX_RECALL_LIMIT = 50
DEFAULT_RECALL_LIMIT = 8

async def recall(query: str='', kind: str='all', detail: str='snippets', filters: dict[str, Any] | None=None, limit: int=DEFAULT_RECALL_LIMIT) -> dict[str, Any]:
    query = sanitize_query(query) if query else ''
    filters = filters or {}
    project = sanitize_project(filters.get('project', ''))
    type_filter = filters.get('type', '')
    tags = sanitize_tags(filters.get('tags', []))
    limit = min(max(1, int(limit)), MAX_RECALL_LIMIT)
    if detail not in ('ids', 'snippets', 'full'):
        detail = 'snippets'
    ctx = CognexContext.get_instance()
    results: dict[str, list[dict]] = {'memory': [], 'unit': [], 'decision': []}
    if kind in ('memory', 'all'):
        results['memory'] = await _recall_memory(ctx, query, project, type_filter, tags, detail, limit)
    if kind in ('unit', 'all'):
        results['unit'] = await _recall_unit(ctx, query, project, type_filter, detail, limit)
    if kind in ('decision', 'all'):
        results['decision'] = await _recall_decision(ctx, query, project, detail, limit)
    return _format_recall(results, kind, detail, limit)

async def _recall_memory(ctx: CognexContext, query: str, project: str, type_filter: str, tags: list[str], detail: str, limit: int) -> list[dict]:
    from cognex import MemoryType
    mem_type = None
    if type_filter:
        try:
            mem_type = MemoryType[type_filter.upper()]
        except KeyError:
            pass
    memories = await run_in_thread(ctx.engine.store.search, query=query, memory_type=mem_type, project=project, tags=tuple(tags), limit=limit)
    return _format_memories(ctx, memories, detail)

async def _recall_unit(ctx: CognexContext, query: str, project: str, type_filter: str, detail: str, limit: int) -> list[dict]:
    units = await run_in_thread(ctx.unit_store.search, query=query, project=project, unit_type=type_filter or None, limit=limit)
    return _format_units(units, detail)

async def _recall_decision(ctx: CognexContext, query: str, project: str, detail: str, limit: int) -> list[dict]:
    decisions = ctx.ledger.find_similar(context_query=query, project=project, limit=limit)
    return _format_decisions(decisions, detail)

def _format_memories(ctx: CognexContext, memories: list, detail: str) -> list[dict]:
    results: list[dict] = []
    for m in memories:
        gist = _get_gist_memory(m)
        score = m.relevance_score
        entry: dict[str, Any] = {'id': m.id, 'type': m.type.value, 'score': round(score, 4), 'date': m.created_at.isoformat()}
        if detail == 'ids':
            pass
        elif detail == 'snippets':
            entry['gist'] = gist
            entry['project'] = m.project
            entry['tags'] = list(m.tags)[:5]
        else:
            entry['content'] = m.content
            entry['context'] = m.context
            entry['scope'] = m.scope.value
            entry['project'] = m.project
            entry['tags'] = list(m.tags)
            entry['access_count'] = m.access_count
        results.append(entry)
    return results

def _format_units(units: list, detail: str) -> list[dict]:
    results: list[dict] = []
    for u in units:
        entry: dict[str, Any] = {'id': u.unit_id, 'type': u.unit_type, 'score': round(getattr(u, 'confidence', 1.0), 4), 'date': u.created_at.isoformat()}
        if detail == 'ids':
            pass
        elif detail == 'snippets':
            entry['gist'] = _truncate(u.content, 80)
        else:
            entry['content'] = u.content
            entry['rationale'] = getattr(u, 'rationale', '')
            entry['scope'] = getattr(u, 'scope', '')
        results.append(entry)
    return results

def _format_decisions(decisions: list, detail: str) -> list[dict]:
    results: list[dict] = []
    for d in decisions:
        entry: dict[str, Any] = {'id': d.id, 'type': 'decision', 'score': round(1.0 if d.outcome_success else 0.5, 4), 'date': d.timestamp.isoformat()}
        if detail == 'ids':
            pass
        elif detail == 'snippets':
            entry['gist'] = _truncate(d.reasoning or d.tool_used, 80)
        else:
            entry['tool_used'] = d.tool_used
            entry['reasoning'] = d.reasoning
            entry['context'] = d.context
            entry['outcome'] = d.outcome
            entry['outcome_success'] = d.outcome_success
        results.append(entry)
    return results

def _get_gist_memory(m) -> str:
    gist = getattr(m, 'gist', '')
    if gist:
        return gist
    return _truncate(m.content, 120)

def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + '…'

def _format_recall(results: dict[str, list[dict]], kind: str, detail: str, limit: int) -> dict[str, Any]:
    all_hits = results.get('memory', []) + results.get('unit', []) + results.get('decision', [])
    all_hits.sort(key=lambda h: h.get('score', 0), reverse=True)
    compacted = _compact_similar(all_hits)
    flattened = compacted[:limit]
    for hit in flattened:
        if detail == 'snippets' and 'tags' in hit and (len(hit.get('tags', [])) > 3):
            tags = hit['tags']
            hit['tags'] = tags[:3] + [f'+{len(tags) - 3}']
    out: dict[str, Any] = {'count': len(flattened), 'total_found': len(all_hits), 'detail': detail}
    if kind == 'all':
        out['results'] = flattened
    elif kind == 'memory':
        out['memories'] = flattened
    elif kind == 'unit':
        out['units'] = flattened
    else:
        out['decisions'] = flattened
    return out

def _compact_similar(hits: list[dict]) -> list[dict]:
    if len(hits) <= 1:
        return list(hits)
    compacted: list[dict] = []
    seen: dict[tuple[str, str], int] = {}
    for hit in hits:
        gist = hit.get('gist', '')
        key = (hit.get('type', ''), gist[:40] if gist else '')
        if key in seen and gist:
            idx = seen[key]
            sim_count = compacted[idx].setdefault('_sim', 0)
            compacted[idx]['_sim'] = sim_count + 1
            compacted[idx]['score'] = max(compacted[idx].get('score', 0), hit.get('score', 0))
        else:
            compacted.append(hit)
            seen[key] = len(compacted) - 1
    for c in compacted:
        sim = c.pop('_sim', 0)
        if sim:
            c['+similar'] = sim
    return compacted