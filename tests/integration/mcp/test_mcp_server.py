import asyncio
import shutil
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.core_tools as core_tools
import substrate_mcp.tools.ledger_tools as ledger_tools
import substrate_mcp.tools.memory_tools as memory_tools
import substrate_mcp.tools.trust_tools as trust_tools


TEST_DIR = Path(__file__).parent / ".test_mcp"
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


async def test_trust_tools():
    db_path = str(TEST_DIR / "test_trust.db")
    cleanup_test_dir()

    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=db_path)

    result = await trust_tools.trust_check(
        {
            "tool_name": "BashTool",
            "project": "test-project",
        }
    )
    assert "requires_approval" in result

    result = await trust_tools.trust_record(
        {
            "action": "approval",
            "tool_name": "BashTool",
            "project": "test-project",
            "reason": "Test approval",
        }
    )
    assert "id" in result

    result = await trust_tools.trust_get(
        {
            "tool_name": "BashTool",
            "project": "test-project",
        }
    )
    assert result["approval_count"] == 1

    await trust_tools.trust_summary({"project": "test-project"})

    SubstrateContext.reset_instance()
    cleanup_test_dir()


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


async def test_all_tools_registered():
    expected_tools = [
        "substrate_start_session",
        "substrate_end_session",
        "substrate_process_transcript",
        "substrate_report",
        "memory_add",
        "memory_search",
        "memory_get_context",
        "memory_decay",
        "trust_check",
        "trust_record",
        "trust_get",
        "trust_summary",
        "ledger_record",
        "ledger_outcome",
        "ledger_find_similar",
        "teleport_create_bundle",
        "teleport_rehydrate",
        "swarm_compile_intent",
    ]

    from substrate_mcp.tools import TOOL_HANDLERS

    actual_tools = list(TOOL_HANDLERS.keys())
    for tool in expected_tools:
        assert tool in actual_tools, f"Missing tool: {tool}"


async def main():
    try:
        await test_all_tools_registered()
        await test_memory_tools()
        await test_core_tools()
        await test_trust_tools()
        await test_ledger_tools()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
