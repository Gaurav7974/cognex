import asyncio
import shutil
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.ledger_tools as ledger_tools


TEST_DIR = Path(__file__).parent / ".test_mcp_ledger"
TEST_DIR.mkdir(exist_ok=True)


def cleanup_test_dir():
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR)
        except Exception:
            pass
    TEST_DIR.mkdir(exist_ok=True)


async def test_ledger_tools():
    db_path = str(TEST_DIR / "test_ledger.db")
    cleanup_test_dir()

    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=db_path)

    result = await ledger_tools.ledger_record(
        {
            "tool_used": "EditTool",
            "alternatives": ["ReadTool", "BashTool"],
            "reasoning": "Best for this task",
            "project": "test-project",
        }
    )
    assert "id" in result
    decision_id = result["id"]

    await ledger_tools.ledger_outcome(
        {
            "decision_id": decision_id,
            "outcome": "Successfully edited file",
            "success": True,
        }
    )

    await ledger_tools.ledger_find_similar(
        {
            "query": "edit file",
            "project": "test-project",
            "limit": 5,
        }
    )

    SubstrateContext.reset_instance()
    cleanup_test_dir()


if __name__ == "__main__":
    asyncio.run(test_ledger_tools())
