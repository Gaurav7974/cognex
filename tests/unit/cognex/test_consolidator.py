import pytest
from datetime import datetime, timezone, timedelta
from cognex import MemoryEntry, MemoryType
from cognex.consolidator import MemoryConsolidator

def test_consolidate_episodic_memories(engine):
    for i in range(5):
        engine.store.save(MemoryEntry(id=f'm_{i}', content=f'This is memory number {i}. It describes some facts.', type=MemoryType.FACT, project='api', tags=('fastapi',), relevance_score=1.0))
    for i in range(2):
        engine.store.save(MemoryEntry(id=f'other_{i}', content=f'Other memory {i}.', type=MemoryType.FACT, project='api', tags=('react',), relevance_score=1.0))
    clusters = MemoryConsolidator.consolidate(engine.store, project='api', min_cluster_size=5)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster['project'] == 'api'
    assert 'fastapi' in cluster['theme']
    for i in range(5):
        m = engine.store.get(f'm_{i}')
        assert abs(m.relevance_score - 0.6) < 1e-05
    for i in range(2):
        m = engine.store.get(f'other_{i}')
        assert abs(m.relevance_score - 1.1) < 1e-05

def test_promote_cluster_to_schema(engine):
    for i in range(5):
        engine.store.save(MemoryEntry(id=f'm_{i}', content=f'Facts {i}.', type=MemoryType.FACT, project='api', tags=('fastapi',)))
    clusters = MemoryConsolidator.consolidate(engine.store, project='api', min_cluster_size=5)
    cluster_id = clusters[0]['cluster_id']
    schema = MemoryConsolidator.promote_cluster_to_schema(cluster_id, engine.store, force=False)
    assert schema is None
    schema = MemoryConsolidator.promote_cluster_to_schema(cluster_id, engine.store, force=True)
    assert schema is not None
    assert schema['project'] == 'api'
    assert 'Procedural Schema' in schema['name']
    for i in range(5):
        assert f'Facts {i}.' in schema['description']