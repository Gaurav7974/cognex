"""LongMemEval retriever — memory search for Cognex."""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.tools.dispatcher import handle_tool_call


async def retrieve(question: str, project: str, top_k: int = 5) -> list[str]:
    """Retrieve top_k memories for a question.
    
    Calls memory_search and extracts content strings from results.
    Returns list of content strings in relevance order.
    """
    result = await handle_tool_call("memory_search", {
        "query": question,
        "project": project,
        "limit": top_k
    })
    memories = result.get("memories", [])
    return [m["content"] for m in memories]
