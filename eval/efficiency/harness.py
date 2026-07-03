import asyncio
import json
import logging
import time
import statistics
from typing import Any, Dict, List, Tuple
from pathlib import Path
from cognex_mcp.context import CognexContext
from cognex_mcp.tools import handle_tool_call
logger = logging.getLogger('eval.efficiency')

def estimate_tokens(text: str) -> Tuple[int, str]:
    try:
        import tiktoken
        tokenizer = tiktoken.get_encoding('cl100k_base')
        return (len(tokenizer.encode(text)), 'real (cl100k_base)')
    except ImportError:
        return (len(text) // 4, 'approx (chars/4)')

async def measure_query_strategy(query: str, project: str, gold_ids: List[str], corpus_memories: List[Dict[str, Any]], db_path: str, id_map: Dict[str, str]) -> Dict[str, Any]:
    CognexContext.reset_instance()
    CognexContext.get_instance(db_path=db_path)
    naive_context = '\n'.join([f"- {m['content']}" for m in corpus_memories])
    naive_tokens, tok_name = estimate_tokens(naive_context)
    start_time = time.perf_counter()
    min_res = await handle_tool_call('memory_get_context', {'query': query, 'project': project, 'format': 'minimal', 'limit': 5})
    latency_min = time.perf_counter() - start_time
    min_context = min_res.get('context', '')
    min_tokens, _ = estimate_tokens(min_context)
    start_time = time.perf_counter()
    med_res = await handle_tool_call('memory_get_context', {'query': query, 'project': project, 'format': 'medium', 'limit': 5})
    latency_med = time.perf_counter() - start_time
    med_context = json.dumps(med_res.get('memories', {}))
    med_tokens, _ = estimate_tokens(med_context)
    start_time = time.perf_counter()
    full_res = await handle_tool_call('memory_get_context', {'query': query, 'project': project, 'format': 'full', 'limit': 5})
    latency_full = time.perf_counter() - start_time
    full_context = json.dumps(full_res.get('memories', []))
    full_tokens, _ = estimate_tokens(full_context)
    retrieved_mems = full_res.get('memories', [])
    retrieved_ids = [m['id'] for m in retrieved_mems]
    gold_full_text = ''
    gold_found_count = 0
    for g_id in gold_ids:
        match = next((m for m in corpus_memories if m['id'] == g_id), None)
        if match:
            gold_full_text += f"\n{match['content']}"
            gold_found_count += 1
    gold_extra_tokens, _ = estimate_tokens(gold_full_text.strip())
    two_stage_gold_tokens = med_tokens + gold_extra_tokens
    top1_full_text = ''
    if retrieved_ids:
        top1_id = retrieved_ids[0]
        db_to_corpus = {v: k for k, v in id_map.items()}
        corpus_id = db_to_corpus.get(top1_id)
        if corpus_id:
            match = next((m for m in corpus_memories if m['id'] == corpus_id), None)
            if match:
                top1_full_text = match['content']
    top1_extra_tokens, _ = estimate_tokens(top1_full_text)
    two_stage_top1_tokens = med_tokens + top1_extra_tokens
    return {'naive_tokens': naive_tokens, 'single_stage_ids_tokens': min_tokens, 'single_stage_snippets_tokens': med_tokens, 'single_stage_full_tokens': full_tokens, 'two_stage_gold_tokens': two_stage_gold_tokens, 'two_stage_top1_tokens': two_stage_top1_tokens, 'latency_sec': latency_med, 'tokenizer_type': tok_name}

async def run_efficiency_suite(db_path: str, cases: List[Dict[str, Any]], corpus_memories: List[Dict[str, Any]], id_map: Dict[str, str] | None=None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    results = []
    latencies = []
    id_map = id_map or {}
    for case in cases:
        proj = case['gold_ids'][0].replace('mem_gold_', 'gold-project-')
        res = await measure_query_strategy(query=case['query'], project=proj, gold_ids=case['gold_ids'], corpus_memories=corpus_memories, db_path=db_path, id_map=id_map)
        res['case_id'] = case['case_id']
        results.append(res)
        latencies.append(res['latency_sec'])
    n = len(results)
    if n == 0:
        return ([], {})
    avg_naive = sum((r['naive_tokens'] for r in results)) / n
    avg_ids = sum((r['single_stage_ids_tokens'] for r in results)) / n
    avg_snippets = sum((r['single_stage_snippets_tokens'] for r in results)) / n
    avg_full = sum((r['single_stage_full_tokens'] for r in results)) / n
    avg_two_stage_gold = sum((r['two_stage_gold_tokens'] for r in results)) / n
    avg_two_stage_top1 = sum((r['two_stage_top1_tokens'] for r in results)) / n
    latencies.sort()
    med_latency = statistics.median(latencies)
    p95_idx = int(len(latencies) * 0.95)
    p95_latency = latencies[min(p95_idx, len(latencies) - 1)]
    from cognex_mcp.tools.dispatcher import TOOL_HANDLERS
    handoff_status = 'skipped'
    handoff_tokens = 0
    if 'handoff_create' in TOOL_HANDLERS:
        try:
            last_proj = cases[-1]['gold_ids'][0].replace('mem_gold_', 'gold-project-')
            handoff_res = await handle_tool_call('handoff_create', {'project': last_proj, 'goal_stack': []})
            handoff_str = json.dumps(handoff_res)
            handoff_tokens, _ = estimate_tokens(handoff_str)
            handoff_status = 'measured'
        except Exception as e:
            logger.warning(f'Failed to call handoff_create: {e}')
            handoff_status = 'error'
    else:
        handoff_status = 'skipped: feature pending in 0.2.0 spec'
    summary = {'avg_tokens': {'naive': int(avg_naive), 'single_stage_ids': int(avg_ids), 'single_stage_snippets': int(avg_snippets), 'single_stage_full': int(avg_full), 'two_stage_gold_ideal': int(avg_two_stage_gold), 'two_stage_top1_realistic': int(avg_two_stage_top1)}, 'latency_sec': {'median': round(med_latency, 4), 'p95': round(p95_latency, 4)}, 'handoff_manifest': {'status': handoff_status, 'token_size': handoff_tokens}}
    return (results, summary)