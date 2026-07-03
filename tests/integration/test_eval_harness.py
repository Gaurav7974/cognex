import pytest
import tempfile
import os
import shutil
import asyncio
import sys
from pathlib import Path
eval_dir = str(Path(__file__).resolve().parents[2] / 'eval')
if eval_dir not in sys.path:
    sys.path.insert(0, eval_dir)
from retrieval.harness import seed_database, run_retrieval_suite, run_020_regression_tests
from efficiency.harness import run_efficiency_suite

@pytest.mark.asyncio
async def test_eval_harness_lifecycle():
    mock_corpus = [{'id': 'mem_gold_001', 'type': 'preference', 'scope': 'private', 'project': 'project-alpha', 'tags': ['security'], 'content': 'User prefers using black formatter for Python code in project-alpha.'}, {'id': 'mem_dist_001_near_dup', 'type': 'preference', 'scope': 'private', 'project': 'project-alpha', 'tags': ['security'], 'content': 'Black is the preferred Python formatter for coding style in project-alpha.'}, {'id': 'mem_dist_001_wrong_proj', 'type': 'preference', 'scope': 'private', 'project': 'project-beta', 'tags': ['security'], 'content': 'User prefers using black formatter for Python code in project-beta.'}, {'id': 'mem_gold_002', 'type': 'fact', 'scope': 'private', 'project': 'project-alpha', 'tags': ['database'], 'content': 'The production database for project-alpha runs on PostgreSQL 15 on port 5432.'}, {'id': 'mem_filler_001', 'type': 'lesson', 'scope': 'private', 'project': 'project-gamma', 'tags': ['logging'], 'content': 'Add CORS middleware before router endpoints in config.'}]
    mock_cases = [{'case_id': 'case_001', 'query': 'What python formatting tool is preferred in project-alpha?', 'gold_ids': ['mem_gold_001'], 'distractor_ids': ['mem_dist_001_near_dup', 'mem_dist_001_wrong_proj'], 'category': 'distractor_preference'}, {'case_id': 'case_002', 'query': 'What database port does project-alpha use?', 'gold_ids': ['mem_gold_002'], 'distractor_ids': [], 'category': 'distractor_fact'}]
    tmp_dir = tempfile.mkdtemp(prefix='cognex_eval_test_')
    db_path = os.path.join(tmp_dir, 'test_eval.db')
    try:
        await seed_database(db_path, mock_corpus)
        cases_results, retrieval_summary = await run_retrieval_suite(db_path, mock_cases)
        assert len(cases_results) == 2
        assert 'overall' in retrieval_summary
        assert 'Recall@1' in retrieval_summary['overall']
        assert 'Recall@5' in retrieval_summary['overall']
        assert 'MRR' in retrieval_summary['overall']
        assert 'by_category' in retrieval_summary
        assert 'by_length_class' in retrieval_summary
        case_1 = next((c for c in cases_results if c['case_id'] == 'case_001'))
        assert 'R@1' in case_1
        assert 'R@5' in case_1
        assert 'MRR' in case_1
        eff_results, efficiency_summary = await run_efficiency_suite(db_path, mock_cases, mock_corpus)
        assert len(eff_results) == 2
        assert 'avg_tokens' in efficiency_summary
        assert 'naive' in efficiency_summary['avg_tokens']
        assert 'single_stage_snippets' in efficiency_summary['avg_tokens']
        assert 'two_stage_gold_ideal' in efficiency_summary['avg_tokens']
        assert 'latency_sec' in efficiency_summary
        assert 'handoff_manifest' in efficiency_summary
        regress_res = await run_020_regression_tests(db_path)
        assert 'tiers' in regress_res
        assert 'supersedence' in regress_res
        assert 'status' in regress_res['tiers']
        assert 'status' in regress_res['supersedence']
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)