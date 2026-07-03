from __future__ import annotations
import pytest
from cognex.ledger import DecisionLedger
from cognex.patterns import PatternAnalyzer
from cognex.store import MemoryStore

class TestPatternAnalyzer:

    @pytest.fixture
    def ledger(self, tmp_path):
        return DecisionLedger(db_path=tmp_path / 'decisions.db')

    @pytest.fixture
    def store(self, tmp_path):
        return MemoryStore(db_path=tmp_path / 'memories.db')

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
        for i in range(10):
            entry = ledger.record(tool_used='ReliableTool', context='task {}'.format(i))
            ledger.record_outcome(entry.id, 'success', success=True)
        for i in range(10):
            entry = ledger.record(tool_used='FlakyTool', context='task {}'.format(i))
            success = i < 2
            ledger.record_outcome(entry.id, 'result', success=success)
        insights = analyzer.analyze_all()
        tool_insights = [i for i in insights if i.pattern_type == 'tool_failure']
        assert len(tool_insights) > 0
        flaky_insight = next((i for i in tool_insights if 'FlakyTool' in i.description), None)
        assert flaky_insight is not None
        assert 'fails' in flaky_insight.description