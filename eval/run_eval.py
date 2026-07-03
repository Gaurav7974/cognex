import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from retrieval.harness import seed_database, run_retrieval_suite, run_020_regression_tests
from efficiency.harness import run_efficiency_suite, estimate_tokens
logger = logging.getLogger('eval.runner')
EVAL_DIR = Path(__file__).resolve().parent
DATASETS_DIR = EVAL_DIR / 'datasets'
RESULTS_DIR = EVAL_DIR / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def get_git_sha() -> str:
    import subprocess
    try:
        res = subprocess.run(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return 'unknown'

def get_cognex_version() -> str:
    try:
        import cognex
        return getattr(cognex, '__version__', '0.2.0')
    except ImportError:
        return '0.2.0'

def save_results(output_data: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    version = output_data['provenance']['cognex_version']
    filename = f'run_{version}_{timestamp}.json'
    filepath = output_dir / filename
    with open(filepath, 'w') as f:
        json.dump(output_data, f, indent=2)
    return filepath

def print_retrieval_table(summary: Dict[str, Any]):
    print('\n' + '=' * 45)
    print('      COGNEX RETRIEVAL ACCURACY REPORT')
    print('=' * 45)
    overall = summary.get('overall', {})
    print(f"{'Metric':<25} | {'Value':>10}")
    print('-' * 45)
    for k, v in overall.items():
        if 'Rate' in k or 'Recall' in k:
            print(f'{k:<25} | {v * 100:>9.1f}%')
        else:
            print(f'{k:<25} | {v:>10.3f}')
    print('-' * 45)
    print('\nBy Length Class:')
    for l_class, metrics in summary.get('by_length_class', {}).items():
        r5 = metrics['Recall@5'] * 100
        mrr = metrics['MRR']
        print(f"  {l_class:<10}: Recall@5={r5:>5.1f}%, MRR={mrr:>5.3f} (n={metrics['count']})")
    print('\nBy Distractor Category:')
    for cat, metrics in summary.get('by_category', {}).items():
        r5 = metrics['Recall@5'] * 100
        mrr = metrics['MRR']
        print(f"  {cat:<22}: Recall@5={r5:>5.1f}%, MRR={mrr:>5.3f} (n={metrics['count']})")
    print('=' * 45 + '\n')

def print_efficiency_table(summary: Dict[str, Any]):
    print('\n' + '=' * 65)
    print('               COGNEX TOKEN EFFICIENCY REPORT')
    print('=' * 65)
    print(f"{'Strategy':<30} | {'Avg Tokens':>12} | {'Savings':>10}")
    print('-' * 65)
    avg_tokens = summary.get('avg_tokens', {})
    naive = avg_tokens.get('naive', 1)
    for k, tokens in avg_tokens.items():
        savings = (naive - tokens) / naive * 100 if naive > 0 else 0.0
        label = k.replace('_', ' ').title()
        print(f'{label:<30} | {tokens:>12} | {savings:>9.1f}%')
    print('-' * 65)
    lat = summary.get('latency_sec', {})
    print(f"Latency: Median {lat.get('median', 0.0):.4f}s, p95 {lat.get('p95', 0.0):.4f}s")
    handoff = summary.get('handoff_manifest', {})
    status = handoff.get('status', 'unknown')
    size = handoff.get('token_size', 0)
    print(f'Handoff Manifest Token Size: {size} ({status})')
    print('=' * 65 + '\n')

async def run_suite(args) -> int:
    cases_path = DATASETS_DIR / 'cases_v1.json'
    if not cases_path.exists():
        print(f'Error: Dataset cases file not found at {cases_path}')
        return 1
    with open(cases_path) as f:
        cases = json.load(f)
    if args.quick:
        args.corpus = '500'
        cases = cases[:25]
        print(f'Running in --quick mode (using 25 test cases)')
    corpus_path = DATASETS_DIR / f'corpus_v1_{args.corpus}.json'
    if not corpus_path.exists():
        print(f'Error: Corpus file not found at {corpus_path}')
        return 1
    with open(corpus_path) as f:
        corpus = json.load(f)
    print(f'Starting evaluation suite: {args.suite}')
    print(f'Corpus size: {len(corpus)} memories')
    print(f'Test cases count: {len(cases)}')
    tmp_dir = tempfile.mkdtemp(prefix='cognex_eval_')
    db_path = os.path.join(tmp_dir, 'eval_temp.db')
    try:
        print('Seeding temporary database (this runs chunking & gists)...')
        id_map = await seed_database(db_path, corpus)
        print('Database seeding completed.')
        output_results = {'provenance': {'dataset_version': 'v1', 'cognex_version': get_cognex_version(), 'git_sha': get_git_sha(), 'tokenizer': estimate_tokens('test')[1], 'random_seed': 42}, 'timestamp': datetime.utcnow().isoformat(), 'suite_run': args.suite, 'corpus_scale': int(args.corpus), 'quick_mode': args.quick}
        retrieval_summary = {}
        if args.suite in ['retrieval', 'all']:
            print('Executing retrieval accuracy cases...')
            case_results, retrieval_summary = await run_retrieval_suite(db_path, cases, id_map)
            print_retrieval_table(retrieval_summary)
            print('Running 0.2.0 regression tests...')
            regress_res = await run_020_regression_tests(db_path)
            output_results['retrieval'] = {'summary': retrieval_summary, 'cases': case_results, 'regression_tests': regress_res}
        efficiency_summary = {}
        if args.suite in ['efficiency', 'all']:
            print('Executing token efficiency cases...')
            eff_results, efficiency_summary = await run_efficiency_suite(db_path, cases, corpus, id_map)
            print_efficiency_table(efficiency_summary)
            output_results['efficiency'] = {'summary': efficiency_summary, 'cases': eff_results}
        if args.suite == 'all':
            recall_5 = retrieval_summary.get('overall', {}).get('Recall@5', 0.0)
            avg_tokens = efficiency_summary.get('avg_tokens', {})
            tokens_per_correct = {}
            if recall_5 > 0:
                for strat, tokens in avg_tokens.items():
                    tokens_per_correct[strat] = int(tokens / recall_5)
            else:
                for strat in avg_tokens.keys():
                    tokens_per_correct[strat] = -1
            output_results['tokens_per_correct_retrieval'] = tokens_per_correct
            print('=' * 60)
            print('         TOKENS-PER-CORRECT-RETRIEVAL (Recall@5 Combined)')
            print('=' * 60)
            print(f"{'Strategy':<30} | {'Tokens/Correct Retrieval':>25}")
            print('-' * 60)
            for strat, val in tokens_per_correct.items():
                label = strat.replace('_', ' ').title()
                val_str = f'{val}' if val != -1 else 'N/A (Recall@5 = 0)'
                print(f'{label:<30} | {val_str:>25}')
            print('=' * 60 + '\n')
        out_dir = Path(args.output) if args.output else RESULTS_DIR
        filepath = save_results(output_results, out_dir)
        print(f'Full results saved to: {filepath}')
        if args.suite in ['retrieval', 'all']:
            recall_5_val = retrieval_summary.get('overall', {}).get('Recall@5', 0.0)
            floor = float(args.recall_floor)
            if recall_5_val < floor:
                print(f'WARNING: Recall@5 ({recall_5_val:.2f}) fell below the configured floor ({floor:.2f})!')
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return 0

def compare_runs(file_a: str, file_b: str) -> int:
    path_a = Path(file_a)
    path_b = Path(file_b)
    if not path_a.exists() or not path_b.exists():
        print(f'Error: One or both results files do not exist.')
        return 1
    with open(path_a) as f:
        run_a = json.load(f)
    with open(path_b) as f:
        run_b = json.load(f)
    print('\n' + '=' * 65)
    print(f'            COGNEX RUN METRIC COMPARISON')
    print(f'Run A: {path_a.name}')
    print(f'Run B: {path_b.name}')
    print('=' * 65)
    print(f"{'Metric':<30} | {'Run A':>10} | {'Run B':>10} | {'Diff':>10}")
    print('-' * 65)
    regressions_detected = False
    if 'retrieval' in run_a and 'retrieval' in run_b:
        sum_a = run_a['retrieval']['summary']['overall']
        sum_b = run_b['retrieval']['summary']['overall']
        for metric in ['Recall@1', 'Recall@3', 'Recall@5', 'MRR']:
            val_a = sum_a.get(metric, 0.0)
            val_b = sum_b.get(metric, 0.0)
            diff = val_b - val_a
            if 'Recall' in metric:
                a_str = f'{val_a * 100:.1f}%'
                b_str = f'{val_b * 100:.1f}%'
                diff_str = f'{diff * 100:+.1f}%'
            else:
                a_str = f'{val_a:.3f}'
                b_str = f'{val_b:.3f}'
                diff_str = f'{diff:+.3f}'
            print(f'{metric:<30} | {a_str:>10} | {b_str:>10} | {diff_str:>10}')
            if diff < -0.01:
                regressions_detected = True
    if 'efficiency' in run_a and 'efficiency' in run_b:
        sum_a = run_a['efficiency']['summary']['avg_tokens']
        sum_b = run_b['efficiency']['summary']['avg_tokens']
        print('-' * 65)
        for metric, val_a in sum_a.items():
            val_b = sum_b.get(metric, 0)
            diff = val_b - val_a
            label = metric.replace('_', ' ').title()
            print(f'{label:<30} | {val_a:>10} | {val_b:>10} | {diff:>+10}')
            if diff > 50:
                regressions_detected = True
    print('=' * 65)
    if regressions_detected:
        print('\n[WARNING] Performance regression detected between Run A and Run B!')
        return 2
    else:
        print('\nNo significant performance regression detected.')
        return 0

def main():
    parser = argparse.ArgumentParser(description='Cognex Unified Evaluation Suite')
    subparsers = parser.add_subparsers(dest='command', required=True)
    run_parser = subparsers.add_parser('run', help='Run evaluation suite')
    run_parser.add_argument('--suite', choices=['retrieval', 'efficiency', 'all'], default='all', help='Evaluation suite to execute')
    run_parser.add_argument('--corpus', choices=['500', '2000', '5000'], default='500', help='Corpus scale to run against')
    run_parser.add_argument('--output', type=str, default=None, help='Directory to save results')
    run_parser.add_argument('--quick', action='store_true', help='Run quick CI smoke check (500 corpus, 25-case subset)')
    run_parser.add_argument('--recall-floor', type=float, default=0.85, help='Recall@5 floor warning threshold (default: 0.85)')
    compare_parser = subparsers.add_parser('compare', help='Compare two results files')
    compare_parser.add_argument('file_a', help='First results JSON file')
    compare_parser.add_argument('file_b', help='Second results JSON file')
    args = parser.parse_args()
    src_path = str(Path(__file__).resolve().parents[1] / 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if args.command == 'run':
        sys.exit(asyncio.run(run_suite(args)))
    elif args.command == 'compare':
        sys.exit(compare_runs(args.file_a, args.file_b))
if __name__ == '__main__':
    main()