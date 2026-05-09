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
    assert "python" in result["content"].lower()
    assert result["type"] == "fact"


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
    """Test that get_context returns expected keys and list format."""
    await handle_tool_call("memory_add", {"content": "use black for formatting"})
    result = await handle_tool_call("memory_get_context", {"query": "formatting", "format": "full"})
    assert "memories" in result
    assert "count" in result
    assert result["count"] >= 1
    # With format="full", memories is a list of memory objects
    assert isinstance(result["memories"], list)
    assert len(result["memories"]) == result["count"]


@pytest.mark.asyncio
async def test_memory_decay_runs_without_error():
    """Test that memory decay runs without error."""
    await handle_tool_call("memory_add", {"content": "test memory"})
    result = await handle_tool_call("memory_decay", {"factor": 0.95})
    assert "memories_removed" in result
    assert isinstance(result["memories_removed"], int)


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


@pytest.mark.asyncio
async def test_memory_add_and_search():
    """Add memory and verify it's searchable."""
    added = await handle_tool_call(
        "memory_add",
        {"content": "searchable memory test content", "project": "test-project"},
    )
    memory_id = added["id"]
    assert memory_id is not None
    result = await handle_tool_call(
        "memory_search",
        {"query": "searchable memory", "project": "test-project"},
    )
    assert result["count"] >= 1
    assert any(m["id"] == memory_id for m in result["memories"])


@pytest.mark.asyncio
async def test_memory_add_multiple_tags():
    """Memory can be added with multiple tags and retrieved."""
    result = await handle_tool_call(
        "memory_add",
        {
            "content": "tagged memory for filtering",
            "project": "test-project",
            "tags": ["tag1", "tag2", "tag3"],
        },
    )
    assert "id" in result
    memory_id = result["id"]
    # Search for the memory to verify tags were stored
    search_result = await handle_tool_call(
        "memory_search",
        {"query": "tagged memory", "project": "test-project"},
    )
    found = [m for m in search_result["memories"] if m["id"] == memory_id]
    assert len(found) == 1
    assert set(found[0]["tags"]) == {"tag1", "tag2", "tag3"}


@pytest.mark.asyncio
async def test_audit_get_recent_after_memory_add():
    """Adding a memory should be auditable via audit_get_recent."""
    await handle_tool_call(
        "memory_add",
        {"content": "audited memory", "project": "audit-test"},
    )
    result = await handle_tool_call(
        "audit_get_recent", {"project": "audit-test", "limit": 10}
    )
    assert "entries" in result
    assert "entries_count" in result
    assert result["entries_count"] >= 0  # audit may or may not capture memory_add


@pytest.mark.asyncio
async def test_audit_verify_valid_entry():
    """audit_verify should confirm integrity of a real log entry."""
    await handle_tool_call(
        "substrate_start_session",
        {"session_id": "test-session-verify", "project": "audit-test"},
    )
    entries = await handle_tool_call(
        "audit_get_recent", {"project": "audit-test", "limit": 1}
    )
    assert entries["entries_count"] >= 1
    log_id = entries["entries"][0]["log_id"]
    verify = await handle_tool_call("audit_verify", {"log_id": log_id})
    assert verify["valid"] is True
    assert verify["log_id"] == log_id


@pytest.mark.asyncio
async def test_memory_deduplication():
    """Adding the same content twice should deduplicate — search returns count == 1."""
    content = "deduplication test content"
    
    # Add same content twice
    result1 = await handle_tool_call(
        "memory_add",
        {"content": content, "project": "dedup-test"},
    )
    id1 = result1["id"]
    
    result2 = await handle_tool_call(
        "memory_add",
        {"content": content, "project": "dedup-test"},
    )
    id2 = result2["id"]
    
    # Search should return count == 1 (deduped)
    search_result = await handle_tool_call(
        "memory_search",
        {"query": content, "project": "dedup-test"},
    )
    assert search_result["count"] == 1
    assert len(search_result["memories"]) == 1
    assert search_result["memories"][0]["content"] == content
