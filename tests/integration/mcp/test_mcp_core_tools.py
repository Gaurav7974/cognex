import asyncio
import shutil
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.core_tools as core_tools


TEST_DIR = Path(__file__).parent / ".test_mcp_core"
TEST_DIR.mkdir(exist_ok=True)


def cleanup_test_dir():
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR)
        except Exception:
            pass
    TEST_DIR.mkdir(exist_ok=True)


async def test_core_tools():
    db_path = str(TEST_DIR / "test_core.db")
    cleanup_test_dir()

    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=db_path)

    result = await core_tools.substrate_start_session(
        {
            "session_id": "test-session-123",
            "project": "test-project",
        }
    )
    assert result["session_id"] == "test-session-123"

    result = await core_tools.substrate_report({})
    assert "total_memories" in result

    SubstrateContext.reset_instance()
    cleanup_test_dir()


if __name__ == "__main__":
    asyncio.run(test_core_tools())
