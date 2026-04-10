from __future__ import annotations

import pytest

from substrate import AgentRole, IntentCompiler


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
        assert any(
            "migration" in t.description.lower() or "analyze" in t.description.lower()
            for t in plan.subtasks
        )

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
        assert any(
            "deployment" in t.description.lower() or "deploy" in t.description.lower()
            for t in plan.subtasks
        )

    def test_compile_unknown(self, compiler):
        plan = compiler.compile("Do something weird and unusual")
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
        later_tasks = [t for t in plan.subtasks if t.depends_on]
        assert len(later_tasks) > 0
