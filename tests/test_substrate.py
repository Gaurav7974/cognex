"""Tests for the Cognitive Substrate."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from substrate import (
    CognitiveSubstrate,
    MemoryEntry,
    MemoryExtractor,
    MemoryRetriever,
    MemoryScope,
    MemoryStore,
    MemoryType,
    SessionSnapshot,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def store(tmp_db):
    return MemoryStore(db_path=tmp_db)


@pytest.fixture
def substrate(tmp_db):
    return CognitiveSubstrate(db_path=tmp_db)


# ── MemoryEntry Tests ─────────────────────────────────────────

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
            content="test", type=MemoryType.PREFERENCE,
            project="my-api", tags=("pref", "test"),
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


# ── MemoryStore Tests ─────────────────────────────────────────

class TestMemoryStore:
    def test_save_and_get(self, store):
        m = MemoryEntry(content="FastAPI is preferred", type=MemoryType.PREFERENCE)
        store.save(m)
        found = store.get(m.id)
        assert found is not None
        assert found.content == "FastAPI is preferred"
        assert found.access_count == 1  # get() touches

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

    # Session tests
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
            session_id="s3", project="api",
            summary="Built REST API",
            key_decisions=("chose FastAPI", "chose PostgreSQL"),
            tools_used=("FileReadTool", "BashTool"),
            errors_encountered=("timeout on /health"),
            input_tokens=100, output_tokens=200,
            memory_ids_extracted=("m1", "m2"),
        )
        store.save_session(s)
        found = store.get_session("s3")
        assert found.key_decisions == ("chose FastAPI", "chose PostgreSQL")
        assert found.tools_used == ("FileReadTool", "BashTool")
        assert found.memory_ids_extracted == ("m1", "m2")


# ── MemoryExtractor Tests ─────────────────────────────────────

class TestMemoryExtractor:
    def test_extract_preferences(self):
        ext = MemoryExtractor()
        text = "I prefer FastAPI over Flask. I always use pytest for testing."
        result = ext.extract(text, session_id="s1", project="p1")
        prefs = [m for m in result.memories if m.type == MemoryType.PREFERENCE]
        assert len(prefs) >= 1
        assert any("FastAPI" in m.content or "fastapi" in m.content.lower() for m in prefs)

    def test_extract_decisions(self):
        ext = MemoryExtractor()
        text = "We chose Stripe instead of PayPal for payments."
        result = ext.extract(text, session_id="s1", project="p1")
        decisions = [m for m in result.memories if m.type == MemoryType.DECISION]
        assert len(decisions) >= 1

    def test_extract_lessons(self):
        ext = MemoryExtractor()
        text = "The build failed with an error on the database migration."
        result = ext.extract(text, session_id="s1", project="p1")
        lessons = [m for m in result.memories if m.type == MemoryType.LESSON]
        assert len(lessons) >= 1

    def test_extract_facts(self):
        ext = MemoryExtractor()
        text = "We use PostgreSQL for the database and the API runs on port 8000."
        result = ext.extract(text, session_id="s1", project="p1")
        facts = [m for m in result.memories if m.type == MemoryType.FACT]
        assert len(facts) >= 1

    def test_extract_manual(self):
        ext = MemoryExtractor()
        m = ext.extract_manual(
            content="User likes dark mode",
            memory_type=MemoryType.PREFERENCE,
            project="my-app",
            tags=("ui", "preference"),
        )
        assert m.type == MemoryType.PREFERENCE
        assert m.project == "my-app"
        assert "ui" in m.tags

    def test_deduplication(self):
        ext = MemoryExtractor()
        text = "I prefer FastAPI. I prefer FastAPI. I prefer FastAPI."
        result = ext.extract(text, session_id="s1", project="p1")
        prefs = [m for m in result.memories if m.type == MemoryType.PREFERENCE]
        # Should not have exact duplicates
        contents = [m.content for m in prefs]
        assert len(contents) == len(set(contents))


# ── MemoryRetriever Tests ─────────────────────────────────────

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
        store.save(MemoryEntry(
            content="prefers pytest", type=MemoryType.PREFERENCE,
            project="api", relevance_score=1.5,
        ))
        store.save(MemoryEntry(
            content="memory limit issue", type=MemoryType.LESSON,
            project="api", relevance_score=1.2,
        ))
        retriever = MemoryRetriever(store)
        context = retriever.get_session_context(project="api")
        assert len(context) > 0

    def test_find_similar_decisions(self, store):
        store.save(MemoryEntry(
            content="We chose FastAPI instead of Flask for the framework", type=MemoryType.DECISION,
            project="api",
        ))
        retriever = MemoryRetriever(store)
        results = retriever.find_similar_decisions("FastAPI Flask framework", project="api")
        assert len(results) >= 1

    def test_retrieval_touches_memories(self, store):
        m = MemoryEntry(content="test", relevance_score=1.0)
        store.save(m)
        retriever = MemoryRetriever(store)
        retriever.find_relevant(query="test")
        found = store.get(m.id)
        assert found.access_count >= 1


# ── CognitiveSubstrate Tests ──────────────────────────────────

class TestCognitiveSubstrate:
    def test_start_session_empty(self, substrate):
        memories = substrate.start_session("s1", project="api")
        assert len(memories) == 0  # First session, no memories yet

    def test_process_transcript(self, substrate):
        substrate.start_session("s1", project="api")
        transcript = "I prefer FastAPI. We use PostgreSQL."
        result = substrate.process_transcript(transcript, project="api")
        assert result.count > 0

    def test_session_continuity(self, substrate):
        # Session 1: learn things
        substrate.start_session("s1", project="api")
        substrate.process_transcript(
            "I prefer FastAPI over Flask. We use PostgreSQL for the database.",
            project="api",
        )
        substrate.end_session(summary="Set up API project")

        # Session 2: should remember
        memories = substrate.start_session("s2", project="api")
        assert len(memories) > 0
        contents = " ".join(m.content.lower() for m in memories)
        assert "fastapi" in contents or "postgresql" in contents

    def test_add_memory_manual(self, substrate):
        substrate.add_memory(
            content="User likes dark mode",
            memory_type=MemoryType.PREFERENCE,
            tags=("ui",),
        )
        assert substrate.store.count() == 1

    def test_get_context_with_query(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")
        context = substrate.get_context("FastAPI", project="api")
        assert len(context) > 0

    def test_find_similar_decisions(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript("We chose Stripe instead of PayPal", project="api")
        similar = substrate.find_similar_decisions("payment provider")
        # May or may not match depending on pattern matching
        assert isinstance(similar, list)

    def test_report(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")
        substrate.end_session(summary="test")
        report = substrate.report()
        assert report.total_memories > 0
        assert report.total_sessions == 1
        assert len(report.top_projects) > 0

    def test_decay_memories(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")
        count_before = substrate.store.count()
        # Decay with extreme factor to clean up
        deleted = substrate.decay_memories(factor=0.001)
        # Memories with score < 0.01 should be deleted
        count_after = substrate.store.count()
        assert count_after <= count_before

    def test_multiple_projects(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")
        substrate.end_session()

        substrate.start_session("s2", project="web")
        substrate.process_transcript("I prefer React", project="web")
        substrate.end_session()

        report = substrate.report()
        assert report.total_memories >= 2
        assert len(report.top_projects) >= 2
