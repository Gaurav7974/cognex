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

To use a specific dataset:

```bash
python run_eval.py --dataset longmemeval_50.json
python run_eval.py --dataset longmemeval_subset.json
```

Outputs:
- Summary table to stdout (R@1, R@3, R@5 by category and difficulty)
- Full results JSON saved to `../results/cognex_v<version>_<TIMESTAMP>.json`

The version in the output filename is read dynamically from the installed
Cognex package — it is never hardcoded.

## Dataset Structure

Each test case in `dataset/longmemeval_50.json`:

```json
{
  "id": "lme_001",
  "category": "single_session_user",
  "difficulty": "easy",
  "project": "eval-project",
  "setup_turns": [
    {"role": "user", "content": "I prefer FastAPI over Flask for building APIs because of the async support."},
    {"role": "assistant", "content": "Noted, I'll remember your framework preference."}
  ],
  "memory_to_store": "User prefers FastAPI over Flask for building APIs due to async support.",
  "question": "What web framework does the user prefer for building APIs?",
  "answer_keywords": ["fastapi"],
  "distractor_memories": ["User prefers Django for full-stack web development"]
}
```

- **id**: Unique identifier for test case
- **category**: Memory category (6 categories: single_session_user, single_session_assistant, knowledge_update, temporal_reasoning, multi_session, implicit_preference)
- **difficulty**: easy, medium, hard
- **project**: Cognex project name for this test
- **setup_turns**: Array of conversation turns with role/content pairs (simulates multi-turn context)
- **memory_to_store**: The "correct" memory to retrieve (always present alongside setup_turns)
- **question**: Query to retrieve the memory
- **distractor_memories**: Irrelevant memories added to increase difficulty
- **answer_keywords**: List of keywords — if any appear in retrieved memories, it's a hit

### Memory Categories

| Category | Description | Example |
|----------|-------------|---------|
| **single_session_user** | User states a preference/fact, assistant acknowledges | User prefers pytest over unittest |
| **single_session_assistant** | Assistant states a recommendation, user acknowledges | Assistant recommends FastAPI, user agrees |
| **knowledge_update** | Initial statement followed by correction/update | User prefers Redis, then corrects to PostgreSQL |
| **temporal_reasoning** | Historical vs current preferences/behaviors | User used Python 2, now uses Python 3 |
| **multi_session** | Context carries across multiple conversation turns | Multiple related user questions about same topic |
| **implicit_preference** | Preference inferred from multiple positive statements | User repeatedly mentions preferring nginx |

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

## Typical Results

Results are generated dynamically by running the eval — they are never
hardcoded. Run `python run_eval.py` to get current numbers for your
installed Cognex version.
