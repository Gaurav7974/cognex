"""Tests for Trust, Ledger, Teleport, and Swarm components."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from substrate import (
    TrustGradientEngine, TrustRecord, TrustLevel, PermissionDecision,
    DecisionLedger, DecisionEntry,
    TeleportProtocol, TeleportBundle,
    IntentCompiler, SwarmPlan, SubTask, AgentRole, TaskStatus,
)


# ── Trust Gradient Engine Tests ───────────────────────────────

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
        assert record.trust_level == TrustLevel.UNKNOWN  # Need 5 for OBSERVED

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
        assert rate == pytest.approx(2/3, abs=0.01)

    def test_trust_summary(self, engine):
        engine.record_approval("ToolA", project="api")
        engine.record_approval("ToolB", project="api")
        summary = engine.get_trust_summary(project="api")
        assert len(summary) == 2


# ── Decision Ledger Tests ─────────────────────────────────────

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
        ledger.record(tool_used="BashTool", context="migrating database configs", project="api")
        ledger.record(tool_used="FileEditTool", context="updating readme", project="api")
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


# ── Teleport Protocol Tests ───────────────────────────────────

class TestTeleportBundle:
    def test_serialize_deserialize(self):
        bundle = TeleportBundle(
            session_id="s1", project="api",
            memory_ids=("m1", "m2", "m3"),
            pending_tasks=("task1", "task2"),
            last_action="running tests",
        )
        serialized = bundle.serialize()
        restored = TeleportBundle.deserialize(serialized)
        assert restored.session_id == bundle.session_id
        assert restored.memory_ids == bundle.memory_ids
        assert restored.pending_tasks == bundle.pending_tasks

    def test_sign_and_verify(self):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        assert bundle.verify() is True

    def test_tampered_bundle_fails_verify(self):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        # Tamper with the data
        tampered = TeleportBundle(
            bundle_id=bundle.bundle_id, version=bundle.version,
            created_at=bundle.created_at, source_host=bundle.source_host,
            target_host=bundle.target_host, session_id="TAMPERED",
            project=bundle.project, memory_ids=bundle.memory_ids,
            session_summary=bundle.session_summary,
            trust_records=bundle.trust_records,
            decision_ids=bundle.decision_ids,
            workspace_context=bundle.workspace_context,
            pending_tasks=bundle.pending_tasks,
            last_action=bundle.last_action,
            model_name=bundle.model_name,
            tool_claims=bundle.tool_claims,
            signature=bundle.signature,
        )
        assert tampered.verify() is False

    def test_unsigned_bundle_fails_verify(self):
        bundle = TeleportBundle(session_id="s1")
        assert bundle.verify() is False

    def test_save_and_load_file(self, tmp_path):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        path = bundle.save_to_file(tmp_path / "teleport.json")
        loaded = TeleportBundle.load_from_file(path)
        assert loaded.session_id == bundle.session_id
        assert loaded.verify() is True


class TestTeleportProtocol:
    def test_create_bundle(self, tmp_path):
        from substrate import CognitiveSubstrate
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")

        protocol = TeleportProtocol()
        bundle = protocol.create_bundle(
            substrate=substrate,
            source_host="laptop",
            target_host="server",
            pending_tasks=("finish API", "add tests"),
            last_action="reading config",
        )
        assert bundle.session_id == "s1"
        assert bundle.project == "api"
        assert len(bundle.memory_ids) > 0
        assert bundle.verify() is True

    def test_rehydrate_success(self, tmp_path):
        from substrate import CognitiveSubstrate
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        substrate.start_session("s1", project="api")

        protocol = TeleportProtocol()
        bundle = protocol.create_bundle(
            substrate=substrate, source_host="laptop", target_host="server",
        )
        # Create new substrate for target
        target_substrate = CognitiveSubstrate(db_path=tmp_path / "target.db")
        report = protocol.rehydrate(bundle, target_substrate)
        assert report["status"] == "success"
        assert report["bundle_id"] == bundle.bundle_id

    def test_rehydrate_invalid_bundle(self, tmp_path):
        from substrate import CognitiveSubstrate
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        protocol = TeleportProtocol()
        # Create an invalid bundle (no signature)
        bundle = TeleportBundle(session_id="s1")
        report = protocol.rehydrate(bundle, substrate)
        assert report["status"] == "failed"


# ── Intent Compiler Tests ─────────────────────────────────────

class TestIntentCompiler:
    @pytest.fixture
    def compiler(self):
        return IntentCompiler()

    def test_compile_api_build(self, compiler):
        plan = compiler.compile("Build a REST API with authentication")
        assert len(plan.subtasks) >= 4
        assert any(t.role == AgentRole.EXPLORER for t in plan.subtasks)
        assert any(t.role == AgentRole.PLANNER for t in plan.subtasks)
        assert any(t.role == AgentRole.BUILDER for t in plan.subtasks)
        assert any(t.role == AgentRole.VERIFIER for t in plan.subtasks)

    def test_compile_migration(self, compiler):
        plan = compiler.compile("Migrate from Flask to FastAPI")
        assert len(plan.subtasks) >= 4
        assert any("migration" in t.description.lower() or "analyze" in t.description.lower()
                   for t in plan.subtasks)

    def test_compile_debug(self, compiler):
        plan = compiler.compile("Fix the database connection error")
        assert len(plan.subtasks) >= 3
        assert any(t.role == AgentRole.EXPLORER for t in plan.subtasks)
        assert any(t.role == AgentRole.FIXER for t in plan.subtasks)

    def test_compile_test(self, compiler):
        plan = compiler.compile("Test the authentication module")
        assert len(plan.subtasks) >= 3
        assert any(t.role == AgentRole.VERIFIER for t in plan.subtasks)

    def test_compile_deploy(self, compiler):
        plan = compiler.compile("Deploy to production")
        assert len(plan.subtasks) >= 3
        assert any("deployment" in t.description.lower() or "deploy" in t.description.lower()
                   for t in plan.subtasks)

    def test_compile_unknown(self, compiler):
        plan = compiler.compile("Do something weird and unusual")
        # Falls back to generic decomposition
        assert len(plan.subtasks) >= 3

    def test_suggest_role(self, compiler):
        assert compiler.suggest_role("explore the codebase") == AgentRole.EXPLORER
        assert compiler.suggest_role("plan the architecture") == AgentRole.PLANNER
        assert compiler.suggest_role("build the API") == AgentRole.BUILDER
        assert compiler.suggest_role("test the endpoints") == AgentRole.VERIFIER
        assert compiler.suggest_role("fix the bug") == AgentRole.FIXER

    def test_plan_progress(self, compiler):
        plan = compiler.compile("Build a REST API")
        assert plan.progress == "0/6 tasks complete"
        assert plan.is_complete is False
        assert plan.has_failures is False

    def test_plan_as_text(self, compiler):
        plan = compiler.compile("Build a REST API")
        text = plan.as_text()
        assert "Swarm Plan" in text
        assert "explorer" in text.lower() or "builder" in text.lower()

    def test_subtask_dependencies(self, compiler):
        plan = compiler.compile("Build a REST API")
        # Later tasks should depend on earlier ones
        later_tasks = [t for t in plan.subtasks if t.depends_on]
        assert len(later_tasks) > 0
