from unittest.mock import MagicMock, patch
import pytest
from cognex.models import MemoryEntry, MemoryType
from cognex.retriever import MemoryRetriever
from cognex.store import MemoryStore

@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / 'test.db'
    store = MemoryStore(db_path=db_file)
    yield store
    store.close()

def test_find_relevant_hybrid_fallback(store):
    retriever = MemoryRetriever(store)
    m1 = MemoryEntry(content='pytest preferences', project='proj1', type=MemoryType.PREFERENCE)
    m2 = MemoryEntry(content='other facts', project='proj1', type=MemoryType.FACT)
    store.save(m1)
    store.save(m2)
    with patch('cognex.embeddings.EmbeddingEngine.AVAILABLE', False):
        results = retriever.find_relevant_hybrid(query='pytest', project='proj1', limit=10)
        assert len(results) >= 1
        assert results[0].content == 'pytest preferences'

def test_find_relevant_hybrid_rrf(store):
    retriever = MemoryRetriever(store)
    m1 = MemoryEntry(id='mem1', content='pytest preferences', project='proj1', type=MemoryType.PREFERENCE)
    m2 = MemoryEntry(id='mem2', content='unittest preferences', project='proj1', type=MemoryType.PREFERENCE)
    m3 = MemoryEntry(id='mem3', content='lessons on testing', project='proj1', type=MemoryType.LESSON)
    store.save(m1)
    store.save(m2)
    store.save(m3)
    with patch('cognex.embeddings.EmbeddingEngine.AVAILABLE', True), patch.object(store, 'search', return_value=[m1, m2]), patch.object(store, 'search_semantic', return_value=[(0.9, m2), (0.8, m3)]):
        results = retriever.find_relevant_hybrid(query='testing', project='proj1', limit=3)
        assert len(results) == 3
        assert results[0].id == 'mem2'
        assert results[1].id == 'mem1'
        assert results[2].id == 'mem3'