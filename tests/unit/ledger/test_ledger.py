from __future__ import annotations

import pytest

from substrate import DecisionEntry, DecisionLedger


class TestDecisionLedger:
    @pytest.fixture
    def ledger(self, tmp_path):
        return DecisionLedger(db_path=tmp_path / "decisions.db")

    def test_record_decision(self, ledger):
        entry = ledger.record(
            tool_used="BashTool",
            alternatives=["FileEditTool"],
            reasoning="Faster for bulk operations",
            context="Migrating configs",
            project="api",
        )
        assert entry.tool_used == "BashTool"
        assert len(entry.alternatives) == 1

    def test_record_outcome(self, ledger):
        entry = ledger.record(tool_used="BashTool", context="test")
        updated = ledger.record_outcome(entry.id, outcome="Worked great", success=True)
        assert updated is not None
        assert updated.outcome_success is True
        assert updated.outcome == "Worked great"

    def test_find_similar(self, ledger):
        ledger.record(
            tool_used="BashTool", context="migrating database configs", project="api"
        )
        ledger.record(
            tool_used="FileEditTool", context="updating readme", project="api"
        )
        similar = ledger.find_similar("migrating configs", project="api")
        assert len(similar) >= 1
        assert "BashTool" in similar[0].tool_used

    def test_get_successful(self, ledger):
        e1 = ledger.record(tool_used="ToolA", context="test")
        ledger.record_outcome(e1.id, "worked", success=True)
        e2 = ledger.record(tool_used="ToolB", context="test")
        ledger.record_outcome(e2.id, "failed", success=False)
        successful = ledger.get_successful()
        assert len(successful) == 1
        assert successful[0].tool_used == "ToolA"

    def test_get_failed(self, ledger):
        e = ledger.record(tool_used="ToolA", context="test")
        ledger.record_outcome(e.id, "broke things", success=False)
        failed = ledger.get_failed()
        assert len(failed) == 1

    def test_as_narrative(self, ledger):
        entry = DecisionEntry(
            tool_used="BashTool",
            alternatives=["FileEditTool", "PluginTool"],
            reasoning="it was faster",
            outcome="worked perfectly",
            outcome_success=True,
        )
        narrative = entry.as_narrative()
        assert "BashTool" in narrative
        assert "FileEditTool" in narrative
        assert "faster" in narrative

    def test_get_all(self, ledger):
        ledger.record(tool_used="A")
        ledger.record(tool_used="B")
        ledger.record(tool_used="C")
        assert ledger.count() == 3
