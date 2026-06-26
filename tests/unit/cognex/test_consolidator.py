import pytest
from datetime import datetime, timezone, timedelta
from cognex import MemoryEntry, MemoryType
from cognex.consolidator import MemoryConsolidator


def test_consolidate_episodic_memories(engine):
    # Add 5 memories with same project and tag to trigger consolidation
    for i in range(5):
        engine.store.save(
            MemoryEntry(
                id=f"m_{i}",
                content=f"This is memory number {i}. It describes some facts.",
                type=MemoryType.FACT,
                project="api",
                tags=("fastapi",),
                relevance_score=1.0,
            )
        )

    # Add 2 memories with a different tag (won't meet min_cluster_size=5)
    for i in range(2):
        engine.store.save(
            MemoryEntry(
                id=f"other_{i}",
                content=f"Other memory {i}.",
                type=MemoryType.FACT,
                project="api",
                tags=("react",),
                relevance_score=1.0,
            )
        )

    # Consolidate
    clusters = MemoryConsolidator.consolidate(
        engine.store, project="api", min_cluster_size=5
    )
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["project"] == "api"
    assert "fastapi" in cluster["theme"]
    # Check that episodic memories relevance score was halved (and then touched by get() -> 0.5 + 0.1 = 0.6)
    for i in range(5):
        m = engine.store.get(f"m_{i}")
        assert abs(m.relevance_score - 0.6) < 1e-5

    # Check other memories were not decayed or clustered (get() touches them -> 1.0 + 0.1 = 1.1)
    for i in range(2):
        m = engine.store.get(f"other_{i}")
        assert abs(m.relevance_score - 1.1) < 1e-5


def test_promote_cluster_to_schema(engine):
    # Add 5 memories and consolidate
    for i in range(5):
        engine.store.save(
            MemoryEntry(
                id=f"m_{i}",
                content=f"Facts {i}.",
                type=MemoryType.FACT,
                project="api",
                tags=("fastapi",),
            )
        )
    clusters = MemoryConsolidator.consolidate(
        engine.store, project="api", min_cluster_size=5
    )
    cluster_id = clusters[0]["cluster_id"]

    # Try to promote without force (should fail since it's not 30 days old yet)
    schema = MemoryConsolidator.promote_cluster_to_schema(
        cluster_id, engine.store, force=False
    )
    assert schema is None

    # Promote with force=True
    schema = MemoryConsolidator.promote_cluster_to_schema(
        cluster_id, engine.store, force=True
    )
    assert schema is not None
    assert schema["project"] == "api"
    assert "Procedural Schema" in schema["name"]
    # Verify all parts of episodic memories are summarized
    for i in range(5):
        assert f"Facts {i}." in schema["description"]
