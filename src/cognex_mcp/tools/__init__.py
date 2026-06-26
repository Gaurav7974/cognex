"""Tool registry - imports all tool implementations and provides dispatcher."""

from cognex_mcp.tools.registry import list_all_tools
from cognex_mcp.tools.dispatcher import handle_tool_call, run_in_thread

# Re-export individual tool implementations for direct import
from cognex_mcp.tools.core_tools import (
    cognex_start_session,
    cognex_end_session,
    cognex_process_transcript,
    cognex_report,
)
from cognex_mcp.tools.memory_tools import (
    memory_add,
    memory_search,
    memory_get_context,
    memory_decay,
)
from cognex_mcp.tools.trust_tools import (
    trust_check,
    trust_record,
    trust_get,
    trust_summary,
)
from cognex_mcp.tools.ledger_tools import (
    ledger_record,
    ledger_outcome,
    ledger_find_similar,
)
from cognex_mcp.tools.teleport_tools import (
    teleport_create_bundle,
    teleport_rehydrate,
)
from cognex_mcp.tools.swarm_tools import (
    swarm_compile_intent,
)

__all__ = [
    "list_all_tools",
    "handle_tool_call",
    "run_in_thread",
    # Core tools
    "cognex_start_session",
    "cognex_end_session",
    "cognex_process_transcript",
    "cognex_report",
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
