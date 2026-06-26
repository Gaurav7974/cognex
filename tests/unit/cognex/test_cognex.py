from __future__ import annotations

from cognex import MemoryType


class TestCognexEngine:
    def test_start_session_empty(self, engine):
        memories = engine.start_session("s1", project="api")
        assert len(memories) == 0

    def test_process_transcript(self, engine):
        engine.start_session("s1", project="api")
        transcript = "I prefer FastAPI. We use PostgreSQL."
        result = engine.process_transcript(transcript, project="api")
        assert result.count > 0

    def test_session_continuity(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript(
            "I prefer FastAPI over Flask. We use PostgreSQL for the database.",
            project="api",
        )
        engine.end_session(summary="Set up API project")

        memories = engine.start_session("s2", project="api")
        assert len(memories) > 0
        contents = " ".join(m.content.lower() for m in memories)
        assert "fastapi" in contents or "postgresql" in contents

    def test_add_memory_manual(self, engine):
        engine.add_memory(
            content="User likes dark mode",
            memory_type=MemoryType.PREFERENCE,
            tags=("ui",),
        )
        assert engine.store.count() == 1

    def test_get_context_with_query(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript("I prefer FastAPI", project="api")
        context = engine.get_context("FastAPI", project="api")
        assert len(context) > 0

    def test_find_similar_decisions(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript("We chose Stripe instead of PayPal", project="api")
        similar = engine.find_similar_decisions("payment provider")
        assert isinstance(similar, list)

    def test_report(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript("I prefer FastAPI", project="api")
        engine.end_session(summary="test")
        report = engine.report()
        assert report.total_memories > 0
        assert report.total_sessions == 1
        assert len(report.top_projects) > 0

    def test_decay_memories(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript("I prefer FastAPI", project="api")
        count_before = engine.store.count()
        engine.decay_memories(factor=0.001)
        count_after = engine.store.count()
        assert count_after <= count_before

    def test_multiple_projects(self, engine):
        engine.start_session("s1", project="api")
        engine.process_transcript("I prefer FastAPI", project="api")
        engine.end_session()

        engine.start_session("s2", project="web")
        engine.process_transcript("I prefer React", project="web")
        engine.end_session()

        report = engine.report()
        assert report.total_memories >= 2
        assert len(report.top_projects) >= 2
