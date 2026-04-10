from __future__ import annotations

from substrate import MemoryExtractor, MemoryType


class TestMemoryExtractor:
    def test_extract_preferences(self):
        ext = MemoryExtractor()
        text = "I prefer FastAPI over Flask. I always use pytest for testing."
        result = ext.extract(text, session_id="s1", project="p1")
        prefs = [m for m in result.memories if m.type == MemoryType.PREFERENCE]
        assert len(prefs) >= 1
        assert any(
            "FastAPI" in m.content or "fastapi" in m.content.lower() for m in prefs
        )

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
        contents = [m.content for m in prefs]
        assert len(contents) == len(set(contents))
