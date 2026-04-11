from __future__ import annotations

import pytest

from substrate.ledger import DecisionLedger
from substrate.patterns import PatternAnalyzer
from substrate.store import MemoryStore


class TestPatternAnalyzer:
    @pytest.fixture
    def ledger(self, tmp_path):
        return DecisionLedger(db_path=tmp_path / "decisions.db")

    @pytest.fixture
    def store(self, tmp_path):
        return MemoryStore(db_path=tmp_path / "memories.db")

    @pytest.fixture
    def analyzer(self, ledger, store):
        return PatternAnalyzer(ledger, store)

    def test_instantiation(self, analyzer):
        assert analyzer.ledger is not None
        assert analyzer.store is not None
        assert analyzer.MIN_SAMPLES == 5
        assert analyzer.SIGNIFICANT_RATIO == 1.5

    def test_empty_decision_history(self, analyzer):
        insights = analyzer.analyze_all()
        assert insights == []

    def test_tool_pattern_detection(self, ledger, analyzer):
        # Create decisions for tools with different success rates
        # High success tool
        for i in range(10):
            entry = ledger.record(tool_used="ReliableTool", context="task {}".format(i))
            ledger.record_outcome(entry.id, "success", success=True)

        # Low success tool
        for i in range(10):
            entry = ledger.record(tool_used="FlakyTool", context="task {}".format(i))
            success = i < 2  # Only 2 successes out of 10
            ledger.record_outcome(entry.id, "result", success=success)

        insights = analyzer.analyze_all()

        # Should detect tool patterns
        tool_insights = [i for i in insights if i.pattern_type == "tool_failure"]
        assert len(tool_insights) > 0

        flaky_insight = next(
            (i for i in tool_insights if "FlakyTool" in i.description), None
        )
        assert flaky_insight is not None
        assert "fails" in flaky_insight.description
