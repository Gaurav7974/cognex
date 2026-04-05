"""
Measure token savings from Cognex memory retrieval.
Compares: loading full context manually vs Cognex compressed retrieval.
"""

import sys
import asyncio
import json

sys.path.insert(0, "src")


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token per 4 chars."""
    return len(text) // 4


async def run_benchmark():
    from substrate_mcp.tools import handle_tool_call

    # Add sample memories
    test_memories = [
        ("User prefers pytest over unittest", "preference"),
        ("Always use type hints in Python", "preference"),
        ("Project uses PostgreSQL 15 not MySQL", "fact"),
        ("FastAPI chosen over Flask for async support", "decision"),
        ("Deploy via Docker Compose", "fact"),
        ("Use black for formatting, line length 88", "preference"),
        ("Never use global variables", "preference"),
        ("API responses use snake_case", "preference"),
    ]

    for content, mtype in test_memories:
        await handle_tool_call(
            "memory_add",
            {"content": content, "memory_type": mtype, "project": "benchmark"},
        )

    # Method 1: Full dump (what user would paste manually)
    manual_context = "\n".join([f"- {m[0]}" for m in test_memories])
    manual_tokens = estimate_tokens(manual_context)

    # Method 2: Cognex minimal format
    result_minimal = await handle_tool_call(
        "memory_get_context",
        {
            "query": "preferences decisions",
            "project": "benchmark",
            "format": "minimal",
            "limit": 5,
        },
    )
    cognex_tokens = estimate_tokens(json.dumps(result_minimal))

    # Method 3: Cognex medium format
    result_medium = await handle_tool_call(
        "memory_get_context",
        {
            "query": "preferences decisions",
            "project": "benchmark",
            "format": "medium",
            "limit": 5,
        },
    )
    medium_tokens = estimate_tokens(json.dumps(result_medium))

    print("\n=== COGNEX BENCHMARK ===")
    print(f"Manual context paste:     {manual_tokens} tokens")
    print(f"Cognex minimal format:    {cognex_tokens} tokens")
    print(f"Cognex medium format:     {medium_tokens} tokens")
    print(f"\nSavings vs manual:")
    if manual_tokens > 0:
        minimal_saving = ((manual_tokens - cognex_tokens) / manual_tokens) * 100
        medium_saving = ((manual_tokens - medium_tokens) / manual_tokens) * 100
        print(f"  Minimal: {minimal_saving:.0f}% fewer tokens")
        print(f"  Medium:  {medium_saving:.0f}% fewer tokens")
    print("========================\n")

    return {
        "manual_tokens": manual_tokens,
        "cognex_minimal_tokens": cognex_tokens,
        "cognex_medium_tokens": medium_tokens,
    }


if __name__ == "__main__":
    results = asyncio.run(run_benchmark())
