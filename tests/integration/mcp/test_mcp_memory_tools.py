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
async def test_memory_add_basic():
    """Test basic memory addition."""
    result = await handle_tool_call(
        "memory_add",
        {
            "content": "prefer dark mode always",
            "memory_type": "preference",
            "project": "test-project",
            "tags": ["ui"],
        },
    )
    assert "id" in result
    assert result["content"] == "prefer dark mode always"


@pytest.mark.asyncio
async def test_memory_add_with_type_and_tags():
    """Test memory addition with specific type and tags."""
    result = await handle_tool_call(
        "memory_add",
        {
            "content": "Test memory: Python is great",
            "memory_type": "fact",
            "project": "test-project",
            "tags": ["python", "test"],
        },
    )
    assert "id" in result


@pytest.mark.asyncio
async def test_memory_search_finds_added():
    await handle_tool_call(
        "memory_add",
        {"content": "prefer pytest over unittest", "project": "test-project"},
    )
    result = await handle_tool_call(
        "memory_search", {"query": "pytest", "project": "test-project"}
    )
    assert result["count"] >= 1
    assert any("pytest" in m["content"].lower() for m in result["memories"])


@pytest.mark.asyncio
async def test_memory_search_empty_db():
    """Test search on empty database."""
    result = await handle_tool_call("memory_search", {})
    assert result["count"] == 0
    assert result["memories"] == []


@pytest.mark.asyncio
async def test_memory_get_context_returns_keys():
    """Test that get_context returns expected keys."""
    await handle_tool_call("memory_add", {"content": "use black for formatting"})
    result = await handle_tool_call("memory_get_context", {"query": "formatting"})
    assert "memories" in result
    assert "count" in result


@pytest.mark.asyncio
async def test_memory_decay_runs_without_error():
    """Test that memory decay runs without error."""
    await handle_tool_call("memory_add", {"content": "test memory"})
    result = await handle_tool_call("memory_decay", {"factor": 0.95})
    assert "memories_removed" in result or "status" in result


@pytest.mark.asyncio
async def test_memory_search_with_project_filter():
    await handle_tool_call(
        "memory_add", {"content": "api project memory", "project": "api"}
    )
    await handle_tool_call(
        "memory_add", {"content": "web project memory", "project": "web"}
    )
    result = await handle_tool_call("memory_search", {"project": "api"})
    assert result["count"] >= 1
    assert all(m["project"] == "api" for m in result["memories"])
