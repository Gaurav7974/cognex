from __future__ import annotations

import pytest

from substrate import TrustGradientEngine, TrustLevel


class TestTrustGradientEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        return TrustGradientEngine(db_path=tmp_path / "trust.db")

    def test_unknown_requires_approval(self, engine):
        assert engine.requires_approval("BashTool") is True

    def test_record_approval(self, engine):
        engine.record_approval("FileReadTool", "read config.py", project="api")
        record = engine.get_trust("FileReadTool", project="api")
        assert record.approval_count == 1
        assert record.trust_level == TrustLevel.UNKNOWN

    def test_trust_builds_with_approvals(self, engine):
        for i in range(5):
            engine.record_approval("FileReadTool", f"op {i}", project="api")
        record = engine.get_trust("FileReadTool", project="api")
        assert record.trust_level == TrustLevel.OBSERVED
        assert not record.requires_approval

    def test_denial_reduces_trust(self, engine):
        for i in range(5):
            engine.record_approval("BashTool", f"op {i}", project="api")
        engine.record_denial("BashTool", "rm -rf /", project="api")
        record = engine.get_trust("BashTool", project="api")
        assert record.denial_count == 1

    def test_violation_blocks(self, engine):
        engine.record_violation("BashTool", "deleted wrong file", project="api")
        record = engine.get_trust("BashTool", project="api")
        assert record.trust_level == TrustLevel.BLOCKED
        assert record.requires_approval is True

    def test_trust_score(self, engine):
        for i in range(8):
            engine.record_approval("Tool", f"op {i}")
        engine.record_denial("Tool", "bad op")
        record = engine.get_trust("Tool")
        assert 0.0 <= record.trust_score <= 1.0

    def test_get_recent_decisions(self, engine):
        engine.record_approval("Tool", "op1")
        engine.record_denial("Tool", "op2")
        decisions = engine.get_recent_decisions(limit=10)
        assert len(decisions) == 2

    def test_approval_rate(self, engine):
        engine.record_approval("Tool", "op1")
        engine.record_approval("Tool", "op2")
        engine.record_denial("Tool", "op3")
        rate = engine.approval_rate(tool_name="Tool")
        assert rate == pytest.approx(2 / 3, abs=0.01)

    def test_trust_summary(self, engine):
        engine.record_approval("ToolA", project="api")
        engine.record_approval("ToolB", project="api")
        summary = engine.get_trust_summary(project="api")
        assert len(summary) == 2
