import asyncio
import shutil
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.memory_tools as memory_tools


TEST_DIR = Path(__file__).parent / ".test_mcp_memory"
TEST_DIR.mkdir(exist_ok=True)


def cleanup_test_dir():
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR)
        except Exception:
            pass
    TEST_DIR.mkdir(exist_ok=True)


async def test_memory_tools():
    db_path = str(TEST_DIR / "test.db")
    cleanup_test_dir()

    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=db_path)

    result = await memory_tools.memory_add(
        {
            "content": "Test memory: Python is great",
            "memory_type": "fact",
            "project": "test-project",
            "tags": ["python", "test"],
        }
    )
    assert "id" in result

    result = await memory_tools.memory_search(
        {
            "query": "Python",
            "project": "test-project",
            "limit": 10,
        }
    )
    assert result["count"] >= 1

    await memory_tools.memory_get_context(
        {
            "query": "Python",
            "project": "test-project",
        }
    )

    await memory_tools.memory_decay({"factor": 0.95})

    SubstrateContext.reset_instance()
    cleanup_test_dir()


if __name__ == "__main__":
    asyncio.run(test_memory_tools())
