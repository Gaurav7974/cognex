import asyncio
import shutil
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.trust_tools as trust_tools


TEST_DIR = Path(__file__).parent / ".test_mcp_trust"
TEST_DIR.mkdir(exist_ok=True)


def cleanup_test_dir():
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR)
        except Exception:
            pass
    TEST_DIR.mkdir(exist_ok=True)


async def test_trust_tools():
    db_path = str(TEST_DIR / "test_trust.db")
    cleanup_test_dir()

    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=db_path)

    result = await trust_tools.trust_check(
        tool_name="BashTool",
        project="test-project",
    )
    assert "requires_approval" in result

    result = await trust_tools.trust_record(
        action="approval",
        tool_name="BashTool",
        project="test-project",
        reason="Test approval",
    )
    assert "id" in result

    result = await trust_tools.trust_get(
        tool_name="BashTool",
        project="test-project",
    )
    assert result["approval_count"] == 1

    await trust_tools.trust_summary(project="test-project")

    SubstrateContext.reset_instance()
    cleanup_test_dir()


if __name__ == "__main__":
    asyncio.run(test_trust_tools())
