"""LongMemEval retriever — memory search for Cognex.

Calls the cognex store directly instead of going through the MCP
dispatcher's thread pool. This avoids thread-local connection leaks
that cause lock contention during evaluation.
"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_path))

from cognex_mcp.context import CognexContext


def retrieve(question: str, project: str, top_k: int = 5) -> list[str]:
    """Retrieve top_k memories for a question.

    Searches the cognex store and extracts content strings from results.
    Returns list of content strings in relevance order.
    """
    ctx = CognexContext.get_instance()
    memories = ctx.engine.store.search(
        query=question,
        project=project,
        limit=top_k,
    )
    return [m.content for m in memories]
