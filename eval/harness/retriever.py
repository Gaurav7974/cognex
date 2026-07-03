import sys
from pathlib import Path
src_path = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(src_path))
from cognex_mcp.context import CognexContext

def retrieve(question: str, project: str, top_k: int=5) -> list[str]:
    ctx = CognexContext.get_instance()
    memories = ctx.engine.store.search(query=question, project=project, limit=top_k)
    return [m.content for m in memories]