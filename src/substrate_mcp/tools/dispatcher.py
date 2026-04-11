"""Tool dispatcher - handles routing tool calls to appropriate handlers."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

# Shared thread pool for running synchronous DB operations off the event loop
_db_workers = int(os.getenv("COGNEX_DB_WORKERS", "8"))
_db_workers = max(4, _db_workers)
_db_executor = ThreadPoolExecutor(
    max_workers=_db_workers, thread_name_prefix="cognex-db"
)


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """Run a synchronous function in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, partial(func, *args, **kwargs))


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
from substrate_mcp.tools.pattern_tools import (
    pattern_analyze,
    pattern_stats,
)
from substrate_mcp.tools.unit_tools import (
    unit_commit,
    unit_checkout,
    unit_search,
    unit_mark_overridden,
    unit_verify,
    unit_get_relevant,
    unit_export_snapshot,
    unit_decay_stale,
)
from substrate_mcp.tools.chp_tools import (
    chp_entangle,
    chp_transfer,
    chp_project,
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
    # Pattern tools
    "pattern_analyze": pattern_analyze,
    "pattern_stats": pattern_stats,
    # Unit tools
    "unit_commit": unit_commit,
    "unit_checkout": unit_checkout,
    "unit_search": unit_search,
    "unit_mark_overridden": unit_mark_overridden,
    "unit_verify": unit_verify,
    "unit_get_relevant": unit_get_relevant,
    "unit_export_snapshot": unit_export_snapshot,
    "unit_decay_stale": unit_decay_stale,
    # CHP tools
    "chp_entangle": chp_entangle,
    "chp_transfer": chp_transfer,
    "chp_project": chp_project,
}


async def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch tool call to appropriate handler.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Tool result

    Raises:
        ValueError: If tool not found or times out
    """
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {tool_name}")

    handler = TOOL_HANDLERS[tool_name]

    # Wrap with timeout to prevent blocking from SQLite locks
    try:
        return await asyncio.wait_for(handler(**arguments), timeout=25.0)
    except asyncio.TimeoutError:
        raise ValueError(
            f"Tool '{tool_name}' timed out after 25 seconds. "
            "This may indicate database lock contention from concurrent access."
        )
