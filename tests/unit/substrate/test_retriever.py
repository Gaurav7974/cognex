from __future__ import annotations

from substrate import MemoryEntry, MemoryRetriever, MemoryType


class TestMemoryRetriever:
    def test_find_relevant_by_query(self, store):
        store.save(MemoryEntry(content="FastAPI is great", project="api"))
        store.save(MemoryEntry(content="React is popular", project="web"))
        retriever = MemoryRetriever(store)
        results = retriever.find_relevant(query="FastAPI", project="api")
        assert len(results) >= 1
        assert "FastAPI" in results[0].content

    def test_find_relevant_by_project(self, store):
        store.save(MemoryEntry(content="api memory", project="api"))
        store.save(MemoryEntry(content="web memory", project="web"))
        retriever = MemoryRetriever(store)
        results = retriever.find_relevant(query="memory", project="api")
        assert all(m.project == "api" for m in results)

    def test_get_session_context(self, store):
        store.save(
            MemoryEntry(
                content="prefers pytest",
                type=MemoryType.PREFERENCE,
                project="api",
                relevance_score=1.5,
            )
        )
        store.save(
            MemoryEntry(
                content="memory limit issue",
                type=MemoryType.LESSON,
                project="api",
                relevance_score=1.2,
            )
        )
        retriever = MemoryRetriever(store)
        context = retriever.get_session_context(project="api")
        assert len(context) > 0

    def test_find_similar_decisions(self, store):
        store.save(
            MemoryEntry(
                content="We chose FastAPI instead of Flask for the framework",
                type=MemoryType.DECISION,
                project="api",
            )
        )
        retriever = MemoryRetriever(store)
        results = retriever.find_similar_decisions(
            "FastAPI Flask framework", project="api"
        )
        assert len(results) >= 1

    def test_retrieval_touches_memories(self, store):
        m = MemoryEntry(content="test", relevance_score=1.0)
        store.save(m)
        retriever = MemoryRetriever(store)
        retriever.find_relevant(query="test")
        found = store.get(m.id)
        assert found.access_count >= 1
