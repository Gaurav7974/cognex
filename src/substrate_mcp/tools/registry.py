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
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # Core substrate tools (4)
    {
        "name": "substrate_start_session",
        "description": "Start a new session in the cognitive substrate and return relevant memories",
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
        "description": "End the current session with summary and metrics",
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
        "description": "Extract memories from a conversation transcript",
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
        "description": "Get substrate health and statistics report",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # Memory tools (4)
    {
        "name": "memory_add",
        "description": "Add a memory to the cognitive substrate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content"},
                "memory_type": {
                    "type": "string",
                    "description": "Type: fact, preference, decision, pattern, context, lesson",
                    "default": "fact",
                },
                "scope": {
                    "type": "string",
                    "description": "Scope: private, project, shared",
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
        "description": "Search memories with filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "memory_type": {"type": "string", "description": "Filter by type"},
                "project": {"type": "string", "description": "Filter by project"},
                "scope": {"type": "string", "description": "Filter by scope"},
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
        "description": "Get relevant context memories for a query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query"},
                "project": {"type": "string", "description": "Project name"},
            },
        },
    },
    {
        "name": "memory_decay",
        "description": "Apply aging/decay to all memories",
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
        "description": "Check if an operation requires approval",
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
        "description": "Record an approval, denial, or violation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: approval, denial, violation",
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
        "description": "Get trust record for a tool",
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
        "description": "Get trust summary for all tools or a project",
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
        "description": "Record a decision in the ledger",
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
        "description": "Record outcome for a decision",
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
        "description": "Find similar past decisions",
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
        "description": "Create a teleport bundle for state transfer",
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
        "description": "Rehydrate substrate state from a bundle",
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
        "description": "Compile natural language intent into a swarm plan",
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
        "description": "Analyze decision history and discover behavioral patterns (e.g., 'you fail more in evening', 'BashTool fails 40% for you'). Patterns are saved as memories.",
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
        "description": "Get statistics about decision history to check if pattern analysis is possible",
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
