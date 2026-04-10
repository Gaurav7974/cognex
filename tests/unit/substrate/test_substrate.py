from __future__ import annotations

from substrate import MemoryType


class TestCognitiveSubstrate:
    def test_start_session_empty(self, substrate):
        memories = substrate.start_session("s1", project="api")
        assert len(memories) == 0

    def test_process_transcript(self, substrate):
        substrate.start_session("s1", project="api")
        transcript = "I prefer FastAPI. We use PostgreSQL."
        result = substrate.process_transcript(transcript, project="api")
        assert result.count > 0

    def test_session_continuity(self, substrate):
        substrate.start_session("s1", project="api")
        substrate.process_transcript(
            "I prefer FastAPI over Flask. We use PostgreSQL for the database.",
            project="api",
        )
        substrate.end_session(summary="Set up API project")

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
        substrate.decay_memories(factor=0.001)
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
