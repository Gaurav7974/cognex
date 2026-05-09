# Cognex LongMemEval Benchmark

## What This Tests

50 test cases across 6 memory categories inspired by the LongMemEval
benchmark (ICLR 2025). Tests whether Cognex can retrieve the correct
memory when queried.

## Metric

**Context Recall@K** — did the correct memory appear in the top K
retrieved results? Measured at K=1, K=3, K=5.

Scores reported as percentages (e.g., R@5 = 85% means the correct 
memory appeared in the top 5 results for 85% of test cases).

## What This Does NOT Test

- **Answer generation quality** — no LLM judge, no text generation
- **Semantic/paraphrase recall** — BM25 keyword search only, no embeddings yet
- **Answer reranking** — only measures if correct memory was retrieved
- **Multi-hop reasoning** — single-memory retrieval only

This is a **retrieval benchmark**, not an answer quality benchmark.

## How To Run

```bash
cd eval/harness
python run_eval.py
```

Outputs:
- Summary table to stdout (R@1, R@3, R@5 by category and difficulty)
- Full results JSON saved to `../results/cognex_v0.1.7_TIMESTAMP.json`

## Dataset Structure

Each test case in `dataset/longmemeval_subset.json`:

```json
{
  "id": "cat_001",
  "category": "fact_recall",
  "difficulty": "easy",
  "project": "eval",
  "question": "What did I say about database optimization?",
  "memory_to_store": "Always index frequently-queried columns and use query explain plans.",
  "distractor_memories": [
    "Use connection pooling to improve database performance.",
    "Consider sharding for horizontal scaling."
  ],
  "answer_keywords": ["index", "query explain"]
}
```

- **id**: Unique identifier for test case
- **category**: Memory category (fact_recall, preference_application, decision_consistency, etc.)
- **difficulty**: easy, medium, hard
- **project**: Cognex project name for this test
- **question**: Query to retrieve the memory
- **memory_to_store**: The "correct" memory to retrieve
- **distractor_memories**: Irrelevant memories added to increase difficulty
- **answer_keywords**: List of keywords — if any appear in retrieved memories, it's a hit

## Honest Caveats

- **BM25/FTS5 keyword search only** — no vector embeddings
- **Scores will be lower than competitors** using embeddings (this is expected)
- **This is a baseline** — v0.2.0 will add semantic search with embeddings
- **Results are self-reported**, not independently verified
- **No distraction penalty** — distractors are just noise, not adversarial

## Interpretation

- **R@1 = 80%**: The correct memory is the #1 result 80% of the time
- **R@3 = 90%**: The correct memory appears somewhere in top 3 results 90% of the time
- **R@5 = 95%**: The correct memory appears somewhere in top 5 results 95% of the time

Higher is better. R@5 > R@3 > R@1 always (monotonic).

## Typical Results (BM25 Baseline)

Expected range for keyword-only BM25:
- R@1: 60–75%
- R@3: 75–85%
- R@5: 80–90%

(Actual results depend on keyword specificity and FTS5 BM25 quality.)
