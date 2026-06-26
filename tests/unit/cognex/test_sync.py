import pytest
import os
import asyncio
from datetime import datetime, timezone, timedelta
from cognex import MemoryEntry, MemoryType
from cognex.models import CognitiveUnit
from cognex.ledger import DecisionEntry
from cognex_mcp.context import CognexContext
from cognex_sync.delta import DeltaComputer, MergeResolver
from cognex_sync.server import SyncServer
from cognex_sync.client import SyncClient


def test_conflict_resolution_memory():
    # Resolve memory conflict: last-writer-wins by created_at.
    m1 = MemoryEntry(
        id="m1",
        content="old content",
        created_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc),
        relevance_score=1.0,
    )
    m2 = MemoryEntry(
        id="m1",
        content="new content",
        created_at=datetime(2026, 6, 26, 13, 0, 0, tzinfo=timezone.utc),
        relevance_score=1.0,
    )

    # m2 is newer
    assert MergeResolver.resolve_memory_conflict(m1, m2) == m2
    assert MergeResolver.resolve_memory_conflict(m2, m1) == m2

    # If timestamps match, higher relevance wins
    m3 = MemoryEntry(
        id="m1",
        content="content 3",
        created_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc),
        relevance_score=0.5,
    )
    m4 = MemoryEntry(
        id="m1",
        content="content 4",
        created_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc),
        relevance_score=1.5,
    )
    assert MergeResolver.resolve_memory_conflict(m3, m4) == m4


def test_conflict_resolution_unit():
    # Resolve unit conflict: higher confidence wins.
    u1 = CognitiveUnit(unit_id="u1", content="c1", confidence=0.8, override_count=1)
    u2 = CognitiveUnit(unit_id="u1", content="c2", confidence=0.9, override_count=2)
    assert MergeResolver.resolve_unit_conflict(u1, u2) == u2

    # If equal confidence, lower override_count wins
    u3 = CognitiveUnit(unit_id="u1", content="c3", confidence=0.8, override_count=2)
    u4 = CognitiveUnit(unit_id="u1", content="c4", confidence=0.8, override_count=1)
    assert MergeResolver.resolve_unit_conflict(u3, u4) == u4


def test_conflict_resolution_decision():
    # Resolve decision conflict: last-writer-wins by timestamp.
    d1 = DecisionEntry(
        id="d1",
        tool_used="t1",
        alternatives=(),
        reasoning="r1",
        context="",
        project="",
        outcome="",
        outcome_success=None,
        timestamp="2026-06-26T12:00:00Z",
        session_id="",
        tags=(),
    )
    d2 = DecisionEntry(
        id="d1",
        tool_used="t1",
        alternatives=(),
        reasoning="r2",
        context="",
        project="",
        outcome="",
        outcome_success=None,
        timestamp="2026-06-26T13:00:00Z",
        session_id="",
        tags=(),
    )
    assert MergeResolver.resolve_decision_conflict(d1, d2) == d2


@pytest.mark.asyncio
async def test_tcp_sync_loopback(tmp_path, monkeypatch):
    # Set up test environment
    monkeypatch.setenv("COGNEX_TEST_ENV", "true")

    # Reset CognexContext singleton to use tmp_path
    CognexContext.reset_instance()
    ctx = CognexContext.get_instance(
        db_path=str(tmp_path / "sync_test.db")
    )
    ctx._ensure_initialized()

    # Create server on a dynamic local port
    server = SyncServer(host="127.0.0.1", port=17474)
    await server.start()

    try:
        # Populate some data
        m = MemoryEntry(
            id="m_sync_1",
            content="Testing delta sync",
            type=MemoryType.FACT,
            project="test-proj",
            created_at=datetime.now(timezone.utc),
        )
        ctx.engine.store.save(m)

        # Connect client and pull
        client = SyncClient(host="127.0.0.1", port=17474)
        result = await client.pull_and_merge()
        assert result["status"] == "success"
        assert result["stats"]["memories"] >= 0

        # Test client push
        push_result = await client.push()
        assert push_result["status"] == "success"
        assert push_result["stats"]["memories"] >= 0

    finally:
        await server.stop()
        CognexContext.reset_instance()
