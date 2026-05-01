import pytest
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
from substrate_mcp.tools.dispatcher import handle_tool_call


@pytest.fixture(autouse=True)
def fresh_context(tmp_path):
    """Create a fresh context for each test."""
    SubstrateContext.reset_instance()
    db = str(tmp_path / "substrate.db")
    SubstrateContext.get_instance(db_path=db, project="test-project")
    yield
    SubstrateContext.reset_instance()


@pytest.mark.asyncio
async def test_start_session_returns_session_id():
    """Test that start_session returns the correct session_id."""
    result = await handle_tool_call(
        "substrate_start_session", {"session_id": "sess-001", "project": "test-project"}
    )
    assert result["session_id"] == "sess-001"


@pytest.mark.asyncio
async def test_end_session_graceful_without_start():
    """Test that end_session handles missing session gracefully."""
    result = await handle_tool_call("substrate_end_session", {})
    assert "session_id" in result or "message" in result


@pytest.mark.asyncio
async def test_report_returns_expected_keys():
    """Test that report returns expected keys."""
    result = await handle_tool_call("substrate_report", {})
    assert "total_memories" in result
    assert "total_sessions" in result
    assert result["total_memories"] >= 0


@pytest.mark.asyncio
async def test_report_counts_increase_after_add():
    """Test that memory count increases after adding memory."""
    before = await handle_tool_call("substrate_report", {})
    baseline = before["total_memories"]

    for i in range(3):
        await handle_tool_call(
            "memory_add", {"content": f"memory {i}", "project": "test-project"}
        )

    after = await handle_tool_call("substrate_report", {})
    assert after["total_memories"] == baseline + 3


@pytest.mark.asyncio
async def test_start_session_with_no_prior_memories():
    """Test starting a new session with fresh context."""
    result = await handle_tool_call(
        "substrate_start_session",
        {"session_id": "fresh-001", "project": "test-project"},
    )
    assert result["session_id"] == "fresh-001"
    assert "context_memories" in result or "memories" in result or "message" in result
