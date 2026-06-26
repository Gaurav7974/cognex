"""Intent-to-Swarm Compiler — natural language → decompose → spawn → synthesize."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentRole(enum.Enum):
    EXPLORER = "explorer"       # Researches, maps the landscape
    PLANNER = "planner"         # Designs the approach
    BUILDER = "builder"         # Implements/creates
    VERIFIER = "verifier"       # Checks correctness
    FIXER = "fixer"            # Repairs what's broken


@dataclass(frozen=True)
class SubTask:
    """A decomposed piece of the original intent."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    description: str = ""
    role: AgentRole = AgentRole.BUILDER
    depends_on: tuple[str, ...] = ()  # SubTask IDs this depends on
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_ready(self) -> bool:
        """Can this task start? (all dependencies done)"""
        return self.status == TaskStatus.PENDING and all(
            # In practice, check a task registry
            True for _ in self.depends_on
        )


@dataclass(frozen=True)
class SwarmPlan:
    """The decomposed plan for an intent."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    original_intent: str = ""
    subtasks: tuple[SubTask, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    project: str = ""

    @property
    def is_complete(self) -> bool:
        return all(t.status == TaskStatus.COMPLETED for t in self.subtasks)

    @property
    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.subtasks)

    @property
    def progress(self) -> str:
        done = sum(1 for t in self.subtasks if t.status == TaskStatus.COMPLETED)
        total = len(self.subtasks)
        return f"{done}/{total} tasks complete"

    def as_text(self) -> str:
        lines = [
            f"Swarm Plan: {self.original_intent}",
            f"Plan ID: {self.plan_id}",
            f"Progress: {self.progress}",
            "",
        ]
        for i, t in enumerate(self.subtasks, 1):
            status_icon = {
                TaskStatus.COMPLETED: "[x]",
                TaskStatus.RUNNING: "[~]",
                TaskStatus.FAILED: "[!]",
                TaskStatus.BLOCKED: "[-]",
                TaskStatus.PENDING: "[ ]",
            }[t.status]
            lines.append(f"  {i}. {status_icon} [{t.role.value}] {t.description}")
            if t.depends_on:
                lines.append(f"     Depends on: {', '.join(t.depends_on)}")
            if t.result:
                lines.append(f"     Result: {t.result[:80]}")
            if t.error:
                lines.append(f"     Error: {t.error[:80]}")
        return "\n".join(lines)


class IntentCompiler:
    """Compiles natural language intent into a swarm plan.

    Uses pattern matching as the base layer. In production, this would
    be backed by an LLM call for intelligent decomposition.

    Usage:
        compiler = IntentCompiler()
        plan = compiler.compile("Build a REST API with authentication")
        print(plan.as_text())
        # Shows decomposed tasks with roles and dependencies
    """

    # Intent patterns and their decomposition templates
    _PATTERNS = [
        {
            "keywords": ["build", "create", "make", "develop", "implement"],
            "context_keywords": ["api", "endpoint", "service", "server", "rest", "graphql"],
            "decompose": lambda intent: [
                SubTask(description="Map existing codebase structure and dependencies", role=AgentRole.EXPLORER),
                SubTask(description="Design API architecture and endpoint structure", role=AgentRole.PLANNER, depends_on=("task-1",)),
                SubTask(description="Implement core API endpoints", role=AgentRole.BUILDER, depends_on=("task-2",)),
                SubTask(description="Add authentication and authorization", role=AgentRole.BUILDER, depends_on=("task-3",)),
                SubTask(description="Write tests for all endpoints", role=AgentRole.VERIFIER, depends_on=("task-3", "task-4",)),
                SubTask(description="Review and fix any issues found in testing", role=AgentRole.FIXER, depends_on=("task-5",)),
            ],
        },
        {
            "keywords": ["migrate", "move", "convert", "upgrade", "refactor"],
            "context_keywords": [],
            "decompose": lambda intent: [
                SubTask(description="Analyze current system and identify migration scope", role=AgentRole.EXPLORER),
                SubTask(description="Create migration plan with rollback strategy", role=AgentRole.PLANNER, depends_on=("task-1",)),
                SubTask(description="Execute migration in phases", role=AgentRole.BUILDER, depends_on=("task-2",)),
                SubTask(description="Verify migration correctness and data integrity", role=AgentRole.VERIFIER, depends_on=("task-3",)),
                SubTask(description="Fix any migration issues", role=AgentRole.FIXER, depends_on=("task-4",)),
            ],
        },
        {
            "keywords": ["fix", "debug", "repair", "solve", "troubleshoot"],
            "context_keywords": [],
            "decompose": lambda intent: [
                SubTask(description="Investigate the issue and reproduce it", role=AgentRole.EXPLORER),
                SubTask(description="Identify root cause", role=AgentRole.PLANNER, depends_on=("task-1",)),
                SubTask(description="Implement the fix", role=AgentRole.BUILDER, depends_on=("task-2",)),
                SubTask(description="Verify the fix works and doesn't break anything", role=AgentRole.VERIFIER, depends_on=("task-3",)),
                SubTask(description="Address any remaining issues", role=AgentRole.FIXER, depends_on=("task-4",)),
            ],
        },
        {
            "keywords": ["test", "verify", "check", "audit", "review"],
            "context_keywords": [],
            "decompose": lambda intent: [
                SubTask(description="Identify what needs to be tested", role=AgentRole.EXPLORER),
                SubTask(description="Write comprehensive tests", role=AgentRole.BUILDER, depends_on=("task-1",)),
                SubTask(description="Run tests and analyze results", role=AgentRole.VERIFIER, depends_on=("task-2",)),
                SubTask(description="Fix failing tests", role=AgentRole.FIXER, depends_on=("task-3",)),
            ],
        },
        {
            "keywords": ["deploy", "ship", "release", "publish", "launch"],
            "context_keywords": [],
            "decompose": lambda intent: [
                SubTask(description="Check deployment prerequisites and configuration", role=AgentRole.EXPLORER),
                SubTask(description="Build and prepare deployment artifacts", role=AgentRole.BUILDER, depends_on=("task-1",)),
                SubTask(description="Execute deployment", role=AgentRole.BUILDER, depends_on=("task-2",)),
                SubTask(description="Verify deployment is healthy", role=AgentRole.VERIFIER, depends_on=("task-3",)),
            ],
        },
    ]

    def compile(self, intent: str, project: str = "") -> SwarmPlan:
        """Compile natural language intent into a swarm plan."""
        intent_lower = intent.lower()

        # Try each pattern
        best_match = None
        best_score = 0

        for pattern in self._PATTERNS:
            score = 0
            # Keyword matches
            for kw in pattern["keywords"]:
                if kw in intent_lower:
                    score += 2
            # Context keyword matches
            for kw in pattern.get("context_keywords", []):
                if kw in intent_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = pattern

        # Decompose
        if best_match and best_score > 0:
            subtasks = best_match["decompose"](intent)
        else:
            # Generic decomposition for unknown intents
            subtasks = [
                SubTask(description="Understand the request and gather context", role=AgentRole.EXPLORER),
                SubTask(description="Plan the approach", role=AgentRole.PLANNER, depends_on=("task-1",)),
                SubTask(description="Execute the plan", role=AgentRole.BUILDER, depends_on=("task-2",)),
                SubTask(description="Verify the result", role=AgentRole.VERIFIER, depends_on=("task-3",)),
            ]

        # Assign task IDs
        numbered = []
        for i, t in enumerate(subtasks, 1):
            numbered.append(SubTask(
                id=f"task-{i}", description=t.description,
                role=t.role, depends_on=t.depends_on,
            ))

        return SwarmPlan(
            original_intent=intent,
            subtasks=tuple(numbered),
            project=project,
        )

    def suggest_role(self, intent: str) -> AgentRole:
        """Suggest which agent role is best for a given intent."""
        intent_lower = intent.lower()
        if any(w in intent_lower for w in ["explore", "find", "search", "map", "discover"]):
            return AgentRole.EXPLORER
        if any(w in intent_lower for w in ["plan", "design", "architect", "strategy"]):
            return AgentRole.PLANNER
        if any(w in intent_lower for w in ["build", "create", "write", "implement", "code"]):
            return AgentRole.BUILDER
        if any(w in intent_lower for w in ["test", "verify", "check", "review", "audit"]):
            return AgentRole.VERIFIER
        if any(w in intent_lower for w in ["fix", "repair", "debug", "patch"]):
            return AgentRole.FIXER
        return AgentRole.BUILDER
