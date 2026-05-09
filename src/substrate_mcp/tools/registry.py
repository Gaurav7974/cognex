"""
Data-driven tool registry - extracts TOOL_DEFINITIONS and provides list_all_tools().

This module provides a centralized registry of all 18 MCP tools using a data-driven
approach, replacing ~400 lines of repetitive Tool() instantiation with a clean
data structure and simple loop.
"""

from typing import Any

# MCP types import - lazy loaded to allow testing without MCP package
try:
    from mcp import types  # type: ignore[assignment]

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

    # Mock types for testing without MCP
    class MockTool:
        def __init__(
            self, name: str, description: str, inputSchema: dict[str, Any]
        ) -> None:
            self.name = name
            self.description = description
            self.inputSchema = inputSchema

    class types:  # type: ignore[no-redef]
        Tool = MockTool


# Data structure: list of tool definitions
# Each dict has: name, description, inputSchema

# TOOL CATEGORIES:
# - Session Management (4): substrate_start_session, substrate_end_session, substrate_process_transcript, substrate_report
# - Memory (4): memory_add, memory_search, memory_get_context, memory_decay
# - Trust (4): trust_check, trust_record, trust_get, trust_summary
# - Decision Ledger (3): ledger_record, ledger_outcome, ledger_find_similar
# - Teleport (2): teleport_create_bundle, teleport_rehydrate
# - Swarm Planning (1): swarm_compile_intent
# - Pattern Intelligence (2): pattern_analyze, pattern_stats
# - Cognitive Units (8): unit_commit, unit_checkout, unit_search, unit_mark_overridden, unit_verify, unit_get_relevant, unit_export_snapshot, unit_decay_stale
# - Audit (2): audit_get_recent, audit_verify
# - Cross-Agent Protocol (2): chp_transfer, chp_project
# Total: 32 tools

# QUICK START:
# 1. Always start with substrate_start_session to initialize memory context
# 2. Use memory_add to save things the user wants remembered
# 3. Use memory_get_context to retrieve relevant context before decisions
# 4. Use ledger_record before making important choices
# 5. Use unit_commit to capture structured cognitive state
# 6. Use teleport_create_bundle to transfer state between machines
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # Core substrate tools (4)
    {
        "name": "substrate_start_session",
        "description": "Start a new session in the cognitive substrate and return relevant memories. Use when: beginning a new work session, task, or conversation. This initializes session tracking and retrieves context from past sessions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Unique session identifier",
                },
                "project": {
                    "type": "string",
                    "description": "Project name",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "substrate_end_session",
        "description": "End the current session with summary and metrics. Use when: finishing a work session, task, or conversation. This saves session insights, records key decisions, and tracks performance metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Session summary"},
                "key_decisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key decisions made",
                },
                "tools_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tools used",
                },
                "errors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Errors encountered",
                },
                "input_tokens": {
                    "type": "integer",
                    "description": "Input token count",
                    "default": 0,
                },
                "output_tokens": {
                    "type": "integer",
                    "description": "Output token count",
                    "default": 0,
                },
            },
        },
    },
    {
        "name": "substrate_process_transcript",
        "description": "Extract memories from a conversation transcript. Use when: reviewing past conversations to capture important insights, decisions, or preferences mentioned by the user that should be remembered for future sessions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "transcript": {
                    "type": "string",
                    "description": "Conversation text",
                },
                "session_id": {"type": "string", "description": "Session ID"},
                "project": {"type": "string", "description": "Project name"},
                "context": {"type": "string", "description": "Additional context"},
            },
            "required": ["transcript"],
        },
    },
    {
        "name": "substrate_report",
        "description": "Get substrate health and statistics report. Use when: checking memory bank status, monitoring database health, or verifying how many memories and decisions have been stored.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # Memory tools (4)
    {
        "name": "memory_add",
        "description": "Add a memory to the cognitive substrate. Use when: user says 'remember', wants to save a preference, preference, decision, insight, pattern, or any knowledge they want preserved across sessions. Memories are searchable and persistent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content"},
                "memory_type": {
                    "type": "string",
                    "description": "Type: fact, preference, decision, pattern, context, lesson",
                    "enum": ["fact", "preference", "decision", "pattern", "context", "lesson"],
                    "default": "fact",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope: private, project, shared",
                    "enum": ["private", "project", "shared"],
                    "default": "private",
                },
                "project": {"type": "string", "description": "Project name"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags",
                },
                "context": {"type": "string", "description": "Additional context"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_search",
        "description": "Search memories with filters. Use when: looking for specific information, preferences, or decisions from past sessions. Can filter by type (fact/preference/decision/pattern/context/lesson), project, scope, or tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "memory_type": {
                    "type": "string",
                    "description": "Filter by type",
                    "enum": ["fact", "preference", "decision", "pattern", "context", "lesson"],
                },
                "project": {"type": "string", "description": "Filter by project"},
                "scope": {
                    "type": "string",
                    "description": "Filter by scope",
                    "enum": ["private", "project", "shared"],
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "memory_get_context",
        "description": "Get relevant context memories for a query. Use when: starting work on a task, needing background context, or retrieving information relevant to the current goal. Returns scored, prioritized memories with minimal/medium/full detail levels.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query"},
                "project": {"type": "string", "description": "Project name"},
                "limit": {
                    "type": "integer",
                    "description": "Max memories to return",
                    "default": 5,
                },
                "format": {
                    "type": "string",
                    "description": "Output format: minimal, medium, or full",
                    "enum": ["minimal", "medium", "full"],
                    "default": "medium",
                },
            },
        },
    },
    {
        "name": "memory_decay",
        "description": "Apply aging/decay to all memories. Use when: cleaning up old memories, maintaining database health, or ensuring older information decays in relevance while newer information remains prominent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "factor": {
                    "type": "number",
                    "description": "Decay factor",
                    "default": 0.95,
                }
            },
        },
    },
    # Trust tools (4)
    {
        "name": "trust_check",
        "description": "Check if an operation requires approval. Use when: planning to execute a potentially sensitive tool (delete, update, deploy), checking if the operation has already been approved based on trust history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "Tool name"},
                "operation": {"type": "string", "description": "Operation"},
                "project": {"type": "string", "description": "Project name"},
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "trust_record",
        "description": "Record an approval, denial, or violation. Use when: user approves/denies a tool operation (approval/denial), or to flag security violations. Builds trust history to inform future approvals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: approval, denial, violation",
                    "enum": ["approval", "denial", "violation"],
                },
                "tool_name": {"type": "string", "description": "Tool name"},
                "operation": {"type": "string", "description": "Operation"},
                "context": {"type": "string", "description": "Context"},
                "project": {"type": "string", "description": "Project name"},
                "reason": {"type": "string", "description": "Reason"},
            },
            "required": ["action", "tool_name"],
        },
    },
    {
        "name": "trust_get",
        "description": "Get trust record for a tool. Use when: reviewing approval history for a specific tool, checking which operations have been approved/denied for a given tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "Tool name"},
                "context": {"type": "string", "description": "Context"},
                "project": {"type": "string", "description": "Project name"},
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "trust_summary",
        "description": "Get trust summary for all tools or a project. Use when: reviewing overall trust posture, checking approval counts across all tools, or generating trust reports for a specific project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"}
            },
        },
    },
    # Ledger tools (3)
    {
        "name": "ledger_record",
        "description": "Record a decision in the ledger. Use when: making a significant technical decision (e.g., 'FastAPI vs Flask', 'SQL vs NoSQL'). Tracks the decision, alternatives considered, reasoning, and outcome for future reference.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_used": {"type": "string", "description": "Tool used"},
                "alternatives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alternatives considered",
                },
                "reasoning": {"type": "string", "description": "Reasoning"},
                "context": {"type": "string", "description": "Context"},
                "project": {"type": "string", "description": "Project name"},
                "session_id": {"type": "string", "description": "Session ID"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags",
                },
            },
            "required": ["tool_used"],
        },
    },
    {
        "name": "ledger_outcome",
        "description": "Record outcome for a decision. Use when: a decision you previously logged has been executed and you want to capture results. Connects decision to outcome for pattern learning and retrospectives.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision_id": {"type": "string", "description": "Decision ID"},
                "outcome": {"type": "string", "description": "Outcome description"},
                "success": {"type": "boolean", "description": "Success flag"},
            },
            "required": ["decision_id", "outcome"],
        },
    },
    {
        "name": "ledger_find_similar",
        "description": "Find similar past decisions. Use when: facing a new decision and wanting to learn from similar past decisions, reviewing what worked before in analogous situations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Context query"},
                "project": {"type": "string", "description": "Project name"},
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    # Teleport tools (2)
    {
        "name": "teleport_create_bundle",
        "description": "Create teleport bundle for state transfer between sessions. Use when: transferring full agent state to another machine or session. Captures pending tasks, tool claims, and context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_host": {"type": "string", "description": "Source host"},
                "target_host": {"type": "string", "description": "Target host"},
                "pending_tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pending tasks",
                },
                "last_action": {"type": "string", "description": "Last action"},
                "model_name": {"type": "string", "description": "Model name"},
                "tool_claims": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool claims",
                },
            },
        },
    },
    {
        "name": "teleport_rehydrate",
        "description": "Rehydrate substrate state from a teleport bundle. Use when: restoring agent state from a bundle created on another machine. Reverses teleport_create_bundle to resume work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bundle_json": {
                    "type": "string",
                    "description": "Bundle JSON string",
                }
            },
            "required": ["bundle_json"],
        },
    },
    # Swarm tools (1)
    {
        "name": "swarm_compile_intent",
        "description": "Compile natural language intent into a swarm plan. Use when: translating a high-level goal into a structured execution plan for agent swarms. Returns actionable task breakdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Natural language intent",
                },
                "project": {"type": "string", "description": "Project name"},
            },
            "required": ["intent"],
        },
    },
    # Pattern tools (2)
    {
        "name": "pattern_analyze",
        "description": "Analyze decision history and discover behavioral patterns. Use when: looking for trends in past decisions (e.g., 'when do I fail', 'which tools succeed most'). Saves patterns as memories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name to filter analysis",
                },
                "save_patterns": {
                    "type": "boolean",
                    "description": "Whether to save discovered patterns as memories",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "pattern_stats",
        "description": "Get statistics about decision history. Use when: checking if enough data exists for pattern analysis, or reviewing decision counts by tool/outcome.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name to filter stats",
                },
            },
        },
    },
    # Unit tools (5)
    {
        "name": "unit_commit",
        "description": "Create a Cognitive Unit capturing decision/constraint/progress state. Use when: documenting a structured decision, constraint, or progress checkpoint. Stores what was decided, why, scope, and confidence level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The what - what was decided/done",
                },
                "rationale": {
                    "type": "string",
                    "description": "The why - reasoning behind",
                },
                "unit_type": {
                    "type": "string",
                    "description": "Type: decision, constraint, progress, task_state",
                    "enum": ["decision", "constraint", "progress", "task_state"],
                    "default": "decision",
                },
                "scope": {
                    "type": "string",
                    "description": "Project/module/subsystem scope",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence 0.0-1.0",
                    "default": 1.0,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags",
                },
                "project": {"type": "string", "description": "Project name"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "unit_checkout",
        "description": "Get cognitive bundle (decisions, constraints, progress) for a project. Use when: preparing to work on a task or retrieving full state snapshot for a scope. Returns structured JSON for handoff.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "scope": {"type": "string", "description": "Scope filter (optional)"},
                "unit_type_filter": {
                    "type": "string",
                    "description": "Filter by unit_type",
                    "enum": ["decision", "constraint", "progress", "task_state"],
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "unit_search",
        "description": "Search Cognitive Units by query and type filter. Use when: finding past decisions, constraints, or progress entries matching a topic. Returns scored results ranked by relevance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "project": {"type": "string", "description": "Filter by project"},
                "unit_type_filter": {
                    "type": "string",
                    "description": "Filter by unit_type",
                    "enum": ["decision", "constraint", "progress", "task_state"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "unit_mark_overridden",
        "description": "Mark a unit as contradicted - decays confidence by 0.2",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string", "description": "Unit ID"},
            },
            "required": ["unit_id"],
        },
    },
    {
        "name": "unit_verify",
        "description": "Confirm a unit still holds - updates last_verified",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string", "description": "Unit ID"},
            },
            "required": ["unit_id"],
        },
    },
    # CHP Tools (2)
    {
        "name": "chp_transfer",
        "description": "Transfer Cognitive Unit data via entanglement channel. Use when: sending unit data to another agent after establishing entanglement. Completes the cross-agent state transfer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entanglement_key": {
                    "type": "string",
                    "description": "Entanglement key from chp_entangle",
                },
                "unit_data": {
                    "type": "object",
                    "description": "Serialized unit data with content, rationale, unit_type, scope, confidence",
                    "properties": {
                        "content": {"type": "string", "description": "Unit content"},
                        "rationale": {"type": "string", "description": "Reasoning"},
                        "unit_type": {
                            "type": "string",
                            "enum": ["decision", "constraint", "progress", "task_state"],
                        },
                        "scope": {"type": "string", "description": "Scope"},
                        "confidence": {"type": "number", "description": "0.0-1.0"},
                    },
                },
            },
            "required": ["entanglement_key", "unit_data"],
        },
    },
    {
        "name": "chp_project",
        "description": "Create holographic 3D projection of Cognitive Unit for inspection. Use when: visualizing or sharing a Cognitive Unit across agents. Makes unit state transparent and portable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unit": {
                    "type": "object",
                    "description": "Cognitive Unit dict with content, rationale, unit_type, scope, confidence",
                    "properties": {
                        "content": {"type": "string", "description": "Unit content"},
                        "rationale": {"type": "string", "description": "Reasoning"},
                        "unit_type": {
                            "type": "string",
                            "enum": ["decision", "constraint", "progress", "task_state"],
                        },
                        "scope": {"type": "string", "description": "Scope"},
                        "confidence": {"type": "number", "description": "0.0-1.0"},
                    },
                },
            },
            "required": ["unit"],
        },
    },
    # New Phase 2 Unit Tools (3)
    {
        "name": "unit_get_relevant",
        "description": "Get relevant cognitive units with FTS search and scoring",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "project": {"type": "string", "description": "Project name"},
                "task_context": {
                    "type": "string",
                    "description": "Task context for scope boosting",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 10,
                },
            },
            "required": ["query", "project"],
        },
    },
    {
        "name": "unit_export_snapshot",
        "description": "Export full cognitive snapshot for project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "session_summary": {"type": "string", "description": "Session summary"},
                "scope": {"type": "string", "description": "Scope filter"},
            },
            "required": ["project", "session_summary"],
        },
    },
    {
        "name": "unit_decay_stale",
        "description": "Mark stale units as overridden and decay their confidence",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "threshold": {
                    "type": "number",
                    "description": "Staleness threshold",
                    "default": 0.8,
                },
            },
            "required": ["project"],
        },
    },
    # Audit Log Tools (2) - NEW in Phase 3a
    {
        "name": "audit_get_recent",
        "description": "Get recent audit log entries for a project. Returns list of audit events with timestamps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name to filter by"},
                "limit": {
                    "type": "integer",
                    "description": "Max number of entries to return",
                    "default": 50,
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "audit_verify",
        "description": "Verify integrity of an audit log entry by recomputing its checksum.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_id": {"type": "string", "description": "Audit log entry ID to verify"},
            },
            "required": ["log_id"],
        },
    },
]


def list_all_tools() -> list[types.Tool]:
    """Return all available MCP tools.

    Returns a list of Tool objects created from TOOL_DEFINITIONS.
    This provides a data-driven approach to tool registration, replacing
    the previous ~400 lines of repetitive Tool() instantiation.

    Returns:
        List of 18 Tool objects representing all available MCP tools
    """
    return [types.Tool(**tool_def) for tool_def in TOOL_DEFINITIONS]
