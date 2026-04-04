"""Type definitions for MCP tools."""

from enum import Enum
from typing import TypedDict


class MemoryTypeEnum(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    PATTERN = "pattern"
    CONTEXT = "context"
    LESSON = "lesson"


class ScopeEnum(str, Enum):
    PRIVATE = "private"
    PROJECT = "project"
    SHARED = "shared"


class TrustAction(str, Enum):
    APPROVAL = "approval"
    DENIAL = "denial"
    VIOLATION = "violation"


# Input types


class StartSessionInput(TypedDict, total=False):
    session_id: str
    project: str


class EndSessionInput(TypedDict, total=False):
    summary: str
    key_decisions: list[str]
    tools_used: list[str]
    errors: list[str]
    input_tokens: int
    output_tokens: int


class ProcessTranscriptInput(TypedDict, total=False):
    transcript: str
    session_id: str
    project: str
    context: str


class MemoryAddInput(TypedDict, total=False):
    content: str
    memory_type: str
    scope: str
    project: str
    tags: list[str]
    context: str


class MemorySearchInput(TypedDict, total=False):
    query: str
    memory_type: str
    project: str
    scope: str
    tags: list[str]
    limit: int


class MemoryGetContextInput(TypedDict, total=False):
    query: str
    project: str


class MemoryDecayInput(TypedDict, total=False):
    factor: float


class TrustCheckInput(TypedDict, total=False):
    tool_name: str
    operation: str
    project: str


class TrustRecordInput(TypedDict, total=False):
    action: str
    tool_name: str
    operation: str
    context: str
    project: str
    reason: str


class TrustGetInput(TypedDict, total=False):
    tool_name: str
    context: str
    project: str


class TrustSummaryInput(TypedDict, total=False):
    project: str


class LedgerRecordInput(TypedDict, total=False):
    tool_used: str
    alternatives: list[str]
    reasoning: str
    context: str
    project: str
    session_id: str
    tags: list[str]


class LedgerOutcomeInput(TypedDict, total=False):
    decision_id: str
    outcome: str
    success: bool


class LedgerFindSimilarInput(TypedDict, total=False):
    query: str
    project: str
    limit: int


class TeleportCreateBundleInput(TypedDict, total=False):
    source_host: str
    target_host: str
    pending_tasks: list[str]
    last_action: str
    model_name: str
    tool_claims: list[str]


class TeleportRehydrateInput(TypedDict, total=False):
    bundle_json: str


class SwarmCompileIntentInput(TypedDict, total=False):
    intent: str
    project: str
