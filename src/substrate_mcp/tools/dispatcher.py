"""Tool dispatcher - handles routing tool calls to appropriate handlers."""

from typing import Any, Callable

from substrate_mcp.tools.core_tools import (
    substrate_start_session,
    substrate_end_session,
    substrate_process_transcript,
    substrate_report,
)
from substrate_mcp.tools.memory_tools import (
    memory_add,
    memory_search,
    memory_get_context,
    memory_decay,
)
from substrate_mcp.tools.trust_tools import (
    trust_check,
    trust_record,
    trust_get,
    trust_summary,
)
from substrate_mcp.tools.ledger_tools import (
    ledger_record,
    ledger_outcome,
    ledger_find_similar,
)
from substrate_mcp.tools.teleport_tools import (
    teleport_create_bundle,
    teleport_rehydrate,
)
from substrate_mcp.tools.swarm_tools import (
    swarm_compile_intent,
)


# Tool registry: name -> handler function
TOOL_HANDLERS: dict[str, Callable] = {
    # Core substrate tools
    "substrate_start_session": substrate_start_session,
    "substrate_end_session": substrate_end_session,
    "substrate_process_transcript": substrate_process_transcript,
    "substrate_report": substrate_report,
    # Memory tools
    "memory_add": memory_add,
    "memory_search": memory_search,
    "memory_get_context": memory_get_context,
    "memory_decay": memory_decay,
    # Trust tools
    "trust_check": trust_check,
    "trust_record": trust_record,
    "trust_get": trust_get,
    "trust_summary": trust_summary,
    # Ledger tools
    "ledger_record": ledger_record,
    "ledger_outcome": ledger_outcome,
    "ledger_find_similar": ledger_find_similar,
    # Teleport tools
    "teleport_create_bundle": teleport_create_bundle,
    "teleport_rehydrate": teleport_rehydrate,
    # Swarm tools
    "swarm_compile_intent": swarm_compile_intent,
}


async def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch tool call to appropriate handler.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Tool result

    Raises:
        ValueError: If tool not found
    """
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {tool_name}")

    handler = TOOL_HANDLERS[tool_name]
    return await handler(**arguments)
