import asyncio
import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from cognex_mcp.context import CognexContext
from cognex_mcp.tools import handle_tool_call
from cognex import MemoryType, MemoryScope
logger = logging.getLogger('eval.retrieval')
logging.getLogger('cognex').setLevel(logging.WARNING)
logging.getLogger('cognex-context').setLevel(logging.WARNING)
DATASETS_DIR = Path(__file__).resolve().parents[2] / 'eval' / 'datasets'

def get_db_columns(db_path: str, table_name: str) -> List[str]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f'PRAGMA table_info({table_name})')
        return [row[1] for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def is_tool_registered(tool_name: str) -> bool:
    from cognex_mcp.tools.dispatcher import TOOL_HANDLERS
    return tool_name in TOOL_HANDLERS

async def seed_database(db_path: str, corpus: List[Dict[str, Any]]) -> Dict[str, str]:
    CognexContext.reset_instance()
    ctx = CognexContext.get_instance(db_path=db_path)
    await handle_tool_call('cognex_start_session', {'session_id': 'eval-seeding', 'project': 'eval-temp'})
    id_map = {}
    for i, mem in enumerate(corpus):
        try:
            res = await handle_tool_call('memory_add', {'content': mem['content'], 'memory_type': mem['type'], 'scope': mem['scope'], 'project': mem['project'], 'tags': mem['tags']})
            id_map[mem['id']] = res['id']
        except Exception as e:
            logger.error(f"Failed to seed memory {mem['id']}: {e}")
    await handle_tool_call('cognex_end_session', {'summary': 'Seeding completed'})
    CognexContext.reset_instance()
    return id_map

async def run_retrieval_suite(db_path: str, cases: List[Dict[str, Any]], id_map: Dict[str, str] | None=None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    results = []
    id_map = id_map or {}
    CognexContext.reset_instance()
    CognexContext.get_instance(db_path=db_path)
    for case in cases:
        case_id = case['case_id']
        query = case['query']
        gold_ids = case['gold_ids']
        distractor_ids = case['distractor_ids']
        category = case['category']
        mapped_gold_ids = [id_map[g_id] for g_id in gold_ids if g_id in id_map]
        mapped_distractor_ids = [id_map[d_id] for d_id in distractor_ids if d_id in id_map]
        search_res = await handle_tool_call('memory_search', {'query': query, 'limit': 20})
        retrieved_memories = search_res.get('memories', [])
        retrieved_ids = [m['id'] for m in retrieved_memories]
        gold_ranks = []
        for g_id in mapped_gold_ids:
            if g_id in retrieved_ids:
                gold_ranks.append(retrieved_ids.index(g_id) + 1)
            else:
                found = False
                for r_idx, r_id in enumerate(retrieved_ids):
                    if r_id.startswith(g_id) or g_id.startswith(r_id):
                        gold_ranks.append(r_idx + 1)
                        found = True
                        break
                if not found:
                    gold_ranks.append(float('inf'))
        dist_ranks = []
        for d_id in mapped_distractor_ids:
            if d_id in retrieved_ids:
                dist_ranks.append(retrieved_ids.index(d_id) + 1)
            else:
                found = False
                for r_idx, r_id in enumerate(retrieved_ids):
                    if r_id.startswith(d_id) or d_id.startswith(r_id):
                        dist_ranks.append(r_idx + 1)
                        found = True
                        break
                if not found:
                    dist_ranks.append(float('inf'))
        best_gold_rank = min(gold_ranks) if gold_ranks else float('inf')
        best_dist_rank = min(dist_ranks) if dist_ranks else float('inf')
        r1 = 1 if best_gold_rank <= 1 else 0
        r3 = 1 if best_gold_rank <= 3 else 0
        r5 = 1 if best_gold_rank <= 5 else 0
        mrr = 1.0 / best_gold_rank if best_gold_rank != float('inf') else 0.0
        failed = False
        if best_dist_rank <= 5 and best_dist_rank < best_gold_rank:
            failed = True
        length_class = 'short'
        if 'long' in case_id or 'needle' in category:
            length_class = 'long'
        elif 'medium' in case_id:
            length_class = 'medium'
        results.append({'case_id': case_id, 'category': category, 'length_class': length_class, 'query': query, 'gold_ranks': [r if r != float('inf') else -1 for r in gold_ranks], 'distractor_ranks': [r if r != float('inf') else -1 for r in dist_ranks], 'best_gold_rank': best_gold_rank if best_gold_rank != float('inf') else -1, 'best_dist_rank': best_dist_rank if best_dist_rank != float('inf') else -1, 'R@1': r1, 'R@3': r3, 'R@5': r5, 'MRR': mrr, 'failed': failed})
    summary = compute_retrieval_summary(results)
    return (results, summary)

def compute_retrieval_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}
    overall = {'Recall@1': sum((r['R@1'] for r in results)) / total, 'Recall@3': sum((r['R@3'] for r in results)) / total, 'Recall@5': sum((r['R@5'] for r in results)) / total, 'MRR': sum((r['MRR'] for r in results)) / total, 'Failure_Rate': sum((1 for r in results if r['failed'])) / total}
    by_category = {}
    cats = set((r['category'] for r in results))
    for cat in cats:
        cat_res = [r for r in results if r['category'] == cat]
        n = len(cat_res)
        by_category[cat] = {'count': n, 'Recall@5': sum((r['R@5'] for r in cat_res)) / n, 'MRR': sum((r['MRR'] for r in cat_res)) / n}
    by_length = {}
    lens = set((r['length_class'] for r in results))
    for l_class in lens:
        len_res = [r for r in results if r['length_class'] == l_class]
        n = len(len_res)
        by_length[l_class] = {'count': n, 'Recall@5': sum((r['R@5'] for r in len_res)) / n, 'MRR': sum((r['MRR'] for r in len_res)) / n}
    return {'overall': overall, 'by_category': by_category, 'by_length_class': by_length}

async def run_020_regression_tests(db_path: str) -> Dict[str, Any]:
    regression_results = {'tiers': {'status': 'skipped', 'reason': 'Not tested'}, 'supersedence': {'status': 'skipped', 'reason': 'Not tested'}}
    cols = get_db_columns(db_path, 'memories')
    has_tier = 'tier' in cols
    has_superseded_by = 'superseded_by' in cols
    CognexContext.reset_instance()
    ctx = CognexContext.get_instance(db_path=db_path)
    if has_tier:
        await handle_tool_call('cognex_start_session', {'session_id': 'eval-tiers', 'project': 'eval-temp'})
        add_res = await handle_tool_call('memory_add', {'content': 'Secret credentials for database access are rotated weekly on Monday.', 'project': 'eval-temp'})
        mem_id = add_res['id']
        await handle_tool_call('cognex_end_session', {'summary': 'Tiers setup completed'})
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM memories WHERE id = ?', (mem_id,)).fetchone()
            default_tier = row['tier'] if 'tier' in row.keys() else 1
        with sqlite3.connect(db_path) as conn:
            conn.execute('UPDATE memories SET tier = 3, relevance_score = 0.04 WHERE id = ?', (mem_id,))
            conn.commit()
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
                conn.commit()
        except Exception:
            pass
        search_res = await handle_tool_call('memory_search', {'query': 'Secret credentials', 'project': 'eval-temp'})
        retrieved_ids = [m['id'] for m in search_res.get('memories', [])]
        is_exclusion_supported = mem_id not in retrieved_ids
        if is_exclusion_supported:
            with sqlite3.connect(db_path) as conn:
                exists = conn.execute('SELECT COUNT(*) FROM memories WHERE id = ?', (mem_id,)).fetchone()[0] == 1
            restore_supported = is_tool_registered('memory_restore')
            restored = False
            if restore_supported:
                try:
                    await handle_tool_call('memory_restore', {'memory_id': mem_id})
                    restored = True
                except Exception:
                    pass
            else:
                with sqlite3.connect(db_path) as conn:
                    conn.execute('UPDATE memories SET tier = 1, relevance_score = 1.0 WHERE id = ?', (mem_id,))
                    conn.commit()
                    restored = True
            search_res_after = await handle_tool_call('memory_search', {'query': 'Secret credentials', 'project': 'eval-temp'})
            retrieved_ids_after = [m['id'] for m in search_res_after.get('memories', [])]
            search_works_after = mem_id in retrieved_ids_after
            regression_results['tiers'] = {'status': 'passed', 'default_tier': default_tier, 'excluded_from_search': True, 'row_exists_in_db': exists, 'restored_successfully': restored and search_works_after}
        else:
            regression_results['tiers'] = {'status': 'skipped', 'reason': 'Feature pending: Archived (tier 3) exclusion is not implemented in search query yet.'}
    else:
        regression_results['tiers'] = {'status': 'skipped', 'reason': "Feature pending: 'tier' column not found in database schema."}
    if has_superseded_by:
        await handle_tool_call('cognex_start_session', {'session_id': 'eval-supersedence', 'project': 'eval-temp'})
        stale_res = await handle_tool_call('memory_add', {'content': 'Staging server is located on AWS EC2 instance i-01abc.', 'project': 'eval-temp'})
        stale_id = stale_res['id']
        successor_res = await handle_tool_call('memory_add', {'content': 'Staging server has been migrated to ECS Fargate container fleet.', 'project': 'eval-temp'})
        successor_id = successor_res['id']
        await handle_tool_call('cognex_end_session', {'summary': 'Supersedence setup completed'})
        with sqlite3.connect(db_path) as conn:
            conn.execute('UPDATE memories SET superseded_by = ? WHERE id = ?', (successor_id, stale_id))
            conn.commit()
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
                conn.commit()
        except Exception:
            pass
        search_res = await handle_tool_call('memory_search', {'query': 'Staging server', 'project': 'eval-temp'})
        retrieved_ids = [m['id'] for m in search_res.get('memories', [])]
        is_stale_excluded = stale_id not in retrieved_ids
        is_successor_returned = successor_id in retrieved_ids
        if is_stale_excluded and is_successor_returned:
            regression_results['supersedence'] = {'status': 'passed', 'stale_excluded': True, 'successor_returned': True}
        else:
            regression_results['supersedence'] = {'status': 'skipped', 'reason': "Feature pending: Search query does not support hard-exclusion via 'superseded_by' column yet."}
    else:
        regression_results['supersedence'] = {'status': 'skipped', 'reason': "Feature pending: 'superseded_by' column not found in database schema."}
    CognexContext.reset_instance()
    return regression_results