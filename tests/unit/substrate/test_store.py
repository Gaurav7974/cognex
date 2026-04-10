from __future__ import annotations

from substrate import MemoryEntry, MemoryScope, MemoryStore, MemoryType, SessionSnapshot


class TestMemoryEntry:
    def test_create_default(self):
        m = MemoryEntry(content="test")
        assert m.content == "test"
        assert m.type == MemoryType.FACT
        assert m.scope == MemoryScope.PRIVATE
        assert m.relevance_score == 1.0
        assert m.access_count == 0

    def test_touch_boosts_relevance(self):
        m = MemoryEntry(content="test", relevance_score=1.0)
        touched = m.touch()
        assert touched.relevance_score > m.relevance_score
        assert touched.access_count == 1
        assert touched.last_accessed is not None

    def test_decay_reduces_relevance(self):
        m = MemoryEntry(content="test", relevance_score=1.0)
        decayed = m.decay(0.9)
        assert decayed.relevance_score == 0.9

    def test_relevance_caps_at_2(self):
        m = MemoryEntry(content="test", relevance_score=1.95)
        touched = m.touch()
        assert touched.relevance_score <= 2.0

    def test_serialization_roundtrip(self):
        m = MemoryEntry(
            content="test",
            type=MemoryType.PREFERENCE,
            project="my-api",
            tags=("pref", "test"),
        )
        d = m.as_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.id == m.id
        assert restored.content == m.content
        assert restored.type == m.type
        assert restored.tags == m.tags

    def test_id_is_unique(self):
        m1 = MemoryEntry(content="a")
        m2 = MemoryEntry(content="b")
        assert m1.id != m2.id


class TestMemoryStore:
    def test_save_and_get(self, store):
        m = MemoryEntry(content="FastAPI is preferred", type=MemoryType.PREFERENCE)
        store.save(m)
        found = store.get(m.id)
        assert found is not None
        assert found.content == "FastAPI is preferred"
        assert found.access_count == 1

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent") is None

    def test_delete(self, store):
        m = MemoryEntry(content="delete me")
        store.save(m)
        assert store.delete(m.id) is True
        assert store.get(m.id) is None

    def test_delete_missing(self, store):
        assert store.delete("nonexistent") is False

    def test_count(self, store):
        assert store.count() == 0
        store.save(MemoryEntry(content="a"))
        store.save(MemoryEntry(content="b"))
        assert store.count() == 2

    def test_save_many(self, store):
        memories = [MemoryEntry(content=f"item {i}") for i in range(5)]
        count = store.save_many(memories)
        assert count == 5
        assert store.count() == 5

    def test_search_by_type(self, store):
        store.save(MemoryEntry(content="fact", type=MemoryType.FACT))
        store.save(MemoryEntry(content="pref", type=MemoryType.PREFERENCE))
        facts = store.search(memory_type=MemoryType.FACT)
        assert len(facts) == 1
        assert facts[0].content == "fact"

    def test_search_by_project(self, store):
        store.save(MemoryEntry(content="a", project="proj1"))
        store.save(MemoryEntry(content="b", project="proj2"))
        results = store.search(project="proj1")
        assert len(results) == 1
        assert results[0].content == "a"

    def test_search_by_query(self, store):
        store.save(MemoryEntry(content="I prefer pytest"))
        store.save(MemoryEntry(content="I use unittest"))
        results = store.search(query="pytest")
        assert len(results) >= 1
        assert "pytest" in results[0].content

    def test_search_by_tags(self, store):
        store.save(MemoryEntry(content="a", tags=("important",)))
        store.save(MemoryEntry(content="b", tags=("trivial",)))
        results = store.search(tags=("important",))
        assert len(results) >= 1
        assert results[0].content == "a"

    def test_search_respects_limit(self, store):
        for i in range(20):
            store.save(MemoryEntry(content=f"item {i}"))
        results = store.search(limit=5)
        assert len(results) == 5

    def test_search_by_min_relevance(self, store):
        store.save(MemoryEntry(content="high", relevance_score=1.5))
        store.save(MemoryEntry(content="low", relevance_score=0.1))
        results = store.search(min_relevance=1.0)
        assert all(r.relevance_score >= 1.0 for r in results)

    def test_decay_all(self, store):
        store.save(MemoryEntry(content="a", relevance_score=1.0))
        store.save(MemoryEntry(content="b", relevance_score=1.0))
        store.decay_all(0.5)
        results = store.search(limit=10)
        for r in results:
            assert r.relevance_score <= 0.5

    def test_get_recent(self, store):
        store.save(MemoryEntry(content="first"))
        store.save(MemoryEntry(content="second"))
        recent = store.get_recent(limit=1)
        assert len(recent) == 1

    def test_get_by_project(self, store):
        store.save(MemoryEntry(content="a", project="x"))
        store.save(MemoryEntry(content="b", project="x"))
        store.save(MemoryEntry(content="c", project="y"))
        results = store.get_by_project("x")
        assert len(results) == 2

    def test_save_and_get_session(self, store):
        s = SessionSnapshot(session_id="s1", project="p1", summary="did stuff")
        store.save_session(s)
        found = store.get_session("s1")
        assert found is not None
        assert found.project == "p1"
        assert found.summary == "did stuff"

    def test_get_missing_session(self, store):
        assert store.get_session("nonexistent") is None

    def test_get_sessions(self, store):
        store.save_session(SessionSnapshot(session_id="s1", project="p"))
        store.save_session(SessionSnapshot(session_id="s2", project="p"))
        sessions = store.get_sessions(project="p")
        assert len(sessions) == 2

    def test_session_roundtrip(self, store):
        s = SessionSnapshot(
            session_id="s3",
            project="api",
            summary="Built REST API",
            key_decisions=("chose FastAPI", "chose PostgreSQL"),
            tools_used=("FileReadTool", "BashTool"),
            errors_encountered=("timeout on /health"),
            input_tokens=100,
            output_tokens=200,
            memory_ids_extracted=("m1", "m2"),
        )
        store.save_session(s)
        found = store.get_session("s3")
        assert found.key_decisions == ("chose FastAPI", "chose PostgreSQL")
        assert found.tools_used == ("FileReadTool", "BashTool")
        assert found.memory_ids_extracted == ("m1", "m2")
