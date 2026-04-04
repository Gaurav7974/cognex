"""Tool registry - imports all tool implementations and provides dispatcher."""

from substrate_mcp.tools.registry import list_all_tools
from substrate_mcp.tools.dispatcher import handle_tool_call

# Re-export individual tool implementations for direct import
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

__all__ = [
    "list_all_tools",
    "handle_tool_call",
    # Core tools
    "substrate_start_session",
    "substrate_end_session",
    "substrate_process_transcript",
    "substrate_report",
    # Memory tools
    "memory_add",
    "memory_search",
    "memory_get_context",
    "memory_decay",
    # Trust tools
    "trust_check",
    "trust_record",
    "trust_get",
    "trust_summary",
    # Ledger tools
    "ledger_record",
    "ledger_outcome",
    "ledger_find_similar",
    # Teleport tools
    "teleport_create_bundle",
    "teleport_rehydrate",
    # Swarm tools
    "swarm_compile_intent",
]
