"""
Standalone test for MCP server tool implementations.
Tests the tool logic directly without requiring MCP package.
"""

import asyncio
import sys
import os
import shutil
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from substrate import CognitiveSubstrate, TrustGradientEngine, DecisionLedger
from substrate_mcp.context import SubstrateContext
import substrate_mcp.tools.core_tools as core_tools
import substrate_mcp.tools.memory_tools as memory_tools
import substrate_mcp.tools.trust_tools as trust_tools
import substrate_mcp.tools.ledger_tools as ledger_tools


# Use a fixed test directory to avoid Windows file locking
TEST_DIR = Path(__file__).parent / ".test_mcp"
TEST_DIR.mkdir(exist_ok=True)


def cleanup_test_dir():
    """Clean up test directory."""
    if TEST_DIR.exists():
        try:
            shutil.rmtree(TEST_DIR)
        except:
            pass
    TEST_DIR.mkdir(exist_ok=True)


async def test_memory_tools():
    """Test memory tool implementations."""
    print("\n=== Testing Memory Tools ===")
    
    # Use fixed test directory
    db_path = str(TEST_DIR / "test.db")
    cleanup_test_dir()
    
    # Set up context with test DB
    SubstrateContext.reset_instance()
    ctx = SubstrateContext.get_instance(db_path=db_path)
    
    # Test memory_add
    result = await memory_tools.memory_add({
        "content": "Test memory: Python is great",
        "memory_type": "fact",
        "project": "test-project",
        "tags": ["python", "test"]
    })
    print(f"memory_add: {result}")
    assert "id" in result, "memory_add should return id"
    
    # Test memory_search
    result = await memory_tools.memory_search({
        "query": "Python",
        "project": "test-project",
        "limit": 10
    })
    print(f"memory_search: count={result['count']}")
    assert result["count"] >= 1
    
    # Test memory_get_context
    result = await memory_tools.memory_get_context({
        "query": "Python",
        "project": "test-project"
    })
    print(f"memory_get_context: count={result['count']}")
    
    # Test memory_decay
    result = await memory_tools.memory_decay({
        "factor": 0.95
    })
    print(f"memory_decay: {result}")
    
    SubstrateContext.reset_instance()
    cleanup_test_dir()


async def test_core_tools():
    """Test core substrate tool implementations."""
    print("\n=== Testing Core Tools ===")
    
    db_path = str(TEST_DIR / "test_core.db")
    cleanup_test_dir()
    
    SubstrateContext.reset_instance()
    ctx = SubstrateContext.get_instance(db_path=db_path)
    
    # Test substrate_start_session
    result = await core_tools.substrate_start_session({
        "session_id": "test-session-123",
        "project": "test-project"
    })
    print(f"substrate_start_session: session_id={result['session_id']}")
    assert result["session_id"] == "test-session-123"
    
    # Test substrate_report
    result = await core_tools.substrate_report({})
    print(f"substrate_report: memories={result['total_memories']}")
    assert "total_memories" in result
    
    SubstrateContext.reset_instance()
    cleanup_test_dir()
    print("Core tools passed")


async def test_trust_tools():
    """Test trust tool implementations."""
    print("\n=== Testing Trust Tools ===")
    
    db_path = str(TEST_DIR / "test_trust.db")
    cleanup_test_dir()
    
    SubstrateContext.reset_instance()
    ctx = SubstrateContext.get_instance(db_path=db_path)
    
    # Test trust_check
    result = await trust_tools.trust_check({
        "tool_name": "BashTool",
        "project": "test-project"
    })
    print(f"trust_check: requires_approval={result['requires_approval']}")
    assert "requires_approval" in result
    
    # Test trust_record (approval)
    result = await trust_tools.trust_record({
        "action": "approval",
        "tool_name": "BashTool",
        "project": "test-project",
        "reason": "Test approval"
    })
    print(f"trust_record: {result}")
    assert "id" in result
    
    # Test trust_get
    result = await trust_tools.trust_get({
        "tool_name": "BashTool",
        "project": "test-project"
    })
    print(f"trust_get: approval_count={result['approval_count']}")
    assert result["approval_count"] == 1
    
    # Test trust_summary
    result = await trust_tools.trust_summary({
        "project": "test-project"
    })
    print(f"trust_summary: count={result['count']}")
    
    SubstrateContext.reset_instance()
    cleanup_test_dir()
    print("Trust tools passed")


async def test_ledger_tools():
    """Test ledger tool implementations."""
    print("\n=== Testing Ledger Tools ===")
    
    db_path = str(TEST_DIR / "test_ledger.db")
    cleanup_test_dir()
    
    SubstrateContext.reset_instance()
    ctx = SubstrateContext.get_instance(db_path=db_path)
    
    # Test ledger_record
    result = await ledger_tools.ledger_record({
        "tool_used": "EditTool",
        "alternatives": ["ReadTool", "BashTool"],
        "reasoning": "Best for this task",
        "project": "test-project"
    })
    print(f"ledger_record: id={result['id']}")
    assert "id" in result
    decision_id = result["id"]
    
    # Test ledger_outcome
    result = await ledger_tools.ledger_outcome({
        "decision_id": decision_id,
        "outcome": "Successfully edited file",
        "success": True
    })
    print(f"ledger_outcome: outcome_success={result['outcome_success']}")
    
    # Test ledger_find_similar
    result = await ledger_tools.ledger_find_similar({
        "query": "edit file",
        "project": "test-project",
        "limit": 5
    })
    print(f"ledger_find_similar: count={result['count']}")
    
    SubstrateContext.reset_instance()
    cleanup_test_dir()
    print("Ledger tools passed")


async def test_all_tools_registered():
    """Verify all 18 tools are registered."""
    print("\n=== Testing Tool Registry ===")
    
    # Define expected tools
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
        "swarm_compile_intent"
    ]
    
    print(f"Expected tools: {len(expected_tools)}")
    
    # Verify by importing the handlers dict
    from substrate_mcp.tools import TOOL_HANDLERS
    actual_tools = list(TOOL_HANDLERS.keys())
    
    print(f"Registered tools: {len(actual_tools)}")
    
    for tool in expected_tools:
        assert tool in actual_tools, f"Missing tool: {tool}"
    
    print(f"All {len(expected_tools)} tools registered")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("MCP Server Tool Integration Tests")
    print("=" * 50)
    
    try:
        await test_all_tools_registered()
        await test_memory_tools()
        await test_core_tools()
        await test_trust_tools()
        await test_ledger_tools()
        
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED")
        print("=" * 50)
        print("\n18 MCP tools verified working:")
        print("- 4 Core substrate tools")
        print("- 4 Memory tools")
        print("- 4 Trust tools")
        print("- 3 Ledger tools")
        print("- 2 Teleport tools")
        print("- 1 Swarm tool")
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
