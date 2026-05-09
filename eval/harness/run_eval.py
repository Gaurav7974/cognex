"""LongMemEval runner — orchestrate evaluation harness."""

import json
import asyncio
import tempfile
import os
import shutil
import gc
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from runner import load_case
from retriever import retrieve
from scorer import score
from substrate_mcp.context import SubstrateContext


DATASET_PATH = Path(__file__).resolve().parents[1] / "dataset" / "longmemeval_subset.json"
RESULTS_PATH = Path(__file__).resolve().parents[1] / "results"

K_VALUES = [1, 3, 5]  # compute R@1, R@3, R@5


async def run_single_case(case: dict, tmp_dir: str) -> dict:
    """Run evaluation on a single test case.
    
    Creates isolated DB, loads case, retrieves at K=1,3,5, scores,
    returns result dict with all metrics.
    """
    db_path = os.path.join(tmp_dir, f"{case['id']}.db")
    await load_case(case, db_path)

    results_per_k = {}
    for k in K_VALUES:
        retrieved = await retrieve(
            question=case["question"],
            project=case["project"],
            top_k=k
        )
        result = score(retrieved, case["answer_keywords"])
        results_per_k[f"R@{k}"] = result

    # Close context and release DB connection
    try:
        ctx = SubstrateContext.get_instance()
        if ctx:
            ctx.close()
        SubstrateContext.reset_instance()
    except Exception as e:
        print(f"Warning: Error closing context for {case['id']}: {e}")
        SubstrateContext.reset_instance()
    
    # Force garbage collection to release file handles
    gc.collect()
    
    # Give Windows time to release file locks
    await asyncio.sleep(0.05)
    
    return {
        "id": case["id"],
        "category": case["category"],
        "difficulty": case["difficulty"],
        "question": case["question"],
        "memory_to_store": case["memory_to_store"],
        "answer_keywords": case["answer_keywords"],
        "results": results_per_k
    }


async def main():
    """Main evaluation loop — load dataset, run all cases, compute summary."""
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    print(f"Running eval on {len(dataset)} cases...")
    print("-" * 60)

    all_results = []
    
    # Use standard temp directory but manage cleanup manually
    tmp_dir = tempfile.mkdtemp(prefix="cognex_eval_")
    print(f"Using temp directory: {tmp_dir}")
    
    try:
        for i, case in enumerate(dataset):
            result = await run_single_case(case, tmp_dir)
            all_results.append(result)
            hit = result["results"]["R@5"]["hit"]
            status = "[OK]" if hit else "[--]"
            print(f"{status} {case['id']} ({case['category']}, {case['difficulty']})")

        # Compute summary
        summary = compute_summary(all_results)
        print_summary(summary)
        save_results(all_results, summary)
    
    finally:
        # Manual cleanup with retry logic for Windows file locks
        print(f"\nCleaning up temp directory: {tmp_dir}")
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            # If ignore_errors didn't work, try individual file deletion
            if os.path.exists(tmp_dir):
                for f in os.listdir(tmp_dir):
                    fpath = os.path.join(tmp_dir, f)
                    try:
                        if os.path.isfile(fpath):
                            os.unlink(fpath)
                    except Exception:
                        pass
                try:
                    os.rmdir(tmp_dir)
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Could not fully clean up {tmp_dir}: {e}")


def compute_summary(results: list[dict]) -> dict:
    """Compute recall metrics overall, by category, and by difficulty."""
    total = len(results)
    summary = {"total": total, "overall": {}, "by_category": {}, "by_difficulty": {}}

    for k in K_VALUES:
        key = f"R@{k}"
        hits = sum(1 for r in results if r["results"][key]["hit"])
        summary["overall"][key] = round(hits / total * 100, 1)

    categories = defaultdict(list)
    difficulties = defaultdict(list)
    for r in results:
        categories[r["category"]].append(r)
        difficulties[r["difficulty"]].append(r)

    for cat, cases in categories.items():
        summary["by_category"][cat] = {}
        for k in K_VALUES:
            key = f"R@{k}"
            hits = sum(1 for c in cases if c["results"][key]["hit"])
            summary["by_category"][cat][key] = round(hits / len(cases) * 100, 1)

    for diff, cases in difficulties.items():
        summary["by_difficulty"][diff] = {}
        for k in K_VALUES:
            key = f"R@{k}"
            hits = sum(1 for c in cases if c["results"][key]["hit"])
            summary["by_difficulty"][diff][key] = round(hits / len(cases) * 100, 1)

    return summary


def print_summary(summary: dict):
    """Print evaluation summary in tabular format."""
    print("\n" + "=" * 60)
    print("COGNEX LONGMEMEVAL RESULTS")
    print("=" * 60)
    print(f"Total cases: {summary['total']}")
    print("\nOverall:")
    for k, v in summary["overall"].items():
        print(f"  {k}: {v}%")
    print("\nBy Category:")
    for cat, scores in summary["by_category"].items():
        r5 = scores.get("R@5", 0)
        print(f"  {cat}: R@5={r5}%")
    print("\nBy Difficulty:")
    for diff, scores in summary["by_difficulty"].items():
        r5 = scores.get("R@5", 0)
        print(f"  {diff}: R@5={r5}%")


def save_results(results: list, summary: dict):
    """Save results and summary to JSON file in results/ directory."""
    RESULTS_PATH.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = "v0.1.7"

    output = {
        "cognex_version": version,
        "timestamp": timestamp,
        "summary": summary,
        "cases": results
    }

    out_path = RESULTS_PATH / f"cognex_{version}_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
