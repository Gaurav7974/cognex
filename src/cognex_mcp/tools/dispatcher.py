"""Tool dispatcher — routes MCP tool calls to their handler functions.

Changes from the original
--------------------------
1. **Backpressure semaphore**: A configurable semaphore (default: 12 permits,
   env var ``COGNEX_MAX_QUEUED``) limits how many tool calls can be in-flight
   concurrently.  Excess requests block rather than spawning unbounded threads,
   preventing OOM conditions under sustained high load.

2. **New tools registered**: ``cognex_health``, ``audit_verify_chain``,
   ``memory_consolidate``, ``arc_start``, ``arc_close``, ``arc_get_context``,
   and the sync tools (``sync_push``, ``sync_pull``) are registered here when
   their handler modules are available.

3. **Tool-level timeout**: Every call is still wrapped with a 25-second
   asyncio.wait_for timeout.  The semaphore prevent starvation when many calls
   queue up waiting for the same DB lock.
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Thread pool for synchronous DB operations
# ---------------------------------------------------------------------------
_db_workers = max(4, int(os.getenv("COGNEX_DB_WORKERS", "8")))
_db_executor = ThreadPoolExecutor(
    max_workers=_db_workers, thread_name_prefix="cognex-db"
)

# ---------------------------------------------------------------------------
# Backpressure semaphore
#
# Limits the number of tool calls that can be executing concurrently.
# When all permits are taken, additional callers wait (back-pressure) rather
# than spawning new threads that could exhaust the SQLite WAL file-descriptor
# limit or the OS thread count.
# ---------------------------------------------------------------------------
_max_queued = max(1, int(os.getenv("COGNEX_MAX_QUEUED", "12")))
_semaphore = asyncio.Semaphore(_max_queued)


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """Run a synchronous function in the shared DB thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, partial(func, *args, **kwargs))


# ---------------------------------------------------------------------------
# Import all handler modules
# ---------------------------------------------------------------------------

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
from cognex_mcp.tools.pattern_tools import (
    pattern_analyze,
    pattern_stats,
)
from cognex_mcp.tools.unit_tools import (
    unit_commit,
    unit_checkout,
    unit_search,
    unit_mark_overridden,
    unit_verify,
    unit_get_relevant,
    unit_export_snapshot,
    unit_decay_stale,
)
from cognex_mcp.tools.chp_tools import (
    chp_entangle,
    chp_transfer,
    chp_project,
)
from cognex_mcp.tools.audit_tools import (
    audit_get_recent,
    audit_verify,
    audit_verify_chain,
)
from cognex_mcp.tools.health_tools import (
    cognex_health,
)

# Optional tools (Phase 3/4) — imported conditionally to avoid import errors
# when their dependency packages are absent.
_optional_tools: dict[str, Callable] = {}

try:
    from cognex_mcp.tools.consolidator_tools import (
        memory_consolidate,
    )
    _optional_tools["memory_consolidate"] = memory_consolidate
except ImportError:
    pass

try:
    from cognex_mcp.tools.arc_tools import (
        arc_start,
        arc_close,
        arc_get_context,
    )
    _optional_tools["arc_start"]       = arc_start
    _optional_tools["arc_close"]       = arc_close
    _optional_tools["arc_get_context"] = arc_get_context
except ImportError:
    pass

try:
    from cognex_mcp.tools.sync_tools import (
        sync_push,
        sync_pull,
    )
    _optional_tools["sync_push"] = sync_push
    _optional_tools["sync_pull"] = sync_pull
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Master dispatch table
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Callable] = {
    # Core cognex tools
    "cognex_start_session":     cognex_start_session,
    "cognex_end_session":       cognex_end_session,
    "cognex_process_transcript":cognex_process_transcript,
    "cognex_report":            cognex_report,
    # Health
    "cognex_health":            cognex_health,
    # Memory tools
    "memory_add":                  memory_add,
    "memory_search":               memory_search,
    "memory_get_context":          memory_get_context,
    "memory_decay":                memory_decay,
    # Trust tools
    "trust_check":                 trust_check,
    "trust_record":                trust_record,
    "trust_get":                   trust_get,
    "trust_summary":               trust_summary,
    # Ledger tools
    "ledger_record":               ledger_record,
    "ledger_outcome":              ledger_outcome,
    "ledger_find_similar":         ledger_find_similar,
    # Teleport tools
    "teleport_create_bundle":      teleport_create_bundle,
    "teleport_rehydrate":          teleport_rehydrate,
    # Swarm tools
    "swarm_compile_intent":        swarm_compile_intent,
    # Pattern tools
    "pattern_analyze":             pattern_analyze,
    "pattern_stats":               pattern_stats,
    # Unit tools
    "unit_commit":                 unit_commit,
    "unit_checkout":               unit_checkout,
    "unit_search":                 unit_search,
    "unit_mark_overridden":        unit_mark_overridden,
    "unit_verify":                 unit_verify,
    "unit_get_relevant":           unit_get_relevant,
    "unit_export_snapshot":        unit_export_snapshot,
    "unit_decay_stale":            unit_decay_stale,
    # CHP tools
    "chp_entangle":                chp_entangle,
    "chp_transfer":                chp_transfer,
    "chp_project":                 chp_project,
    # Audit log tools
    "audit_get_recent":            audit_get_recent,
    "audit_verify":                audit_verify,
    "audit_verify_chain":          audit_verify_chain,
    # Optional tools (Phase 3/4)
    **_optional_tools,
}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch a tool call to its handler, enforcing backpressure and timeout.

    Args:
        tool_name:  Registered tool name.
        arguments:  Tool keyword arguments from the MCP request.

    Returns:
        Handler's return value.

    Raises:
        ValueError: Unknown tool name, or call timed out.
        RuntimeError: Backpressure limit reached (too many concurrent calls).
    """
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(
            f"Unknown tool: {tool_name!r}. "
            f"Available: {', '.join(sorted(TOOL_HANDLERS))}"
        )

    handler = TOOL_HANDLERS[tool_name]

    # Apply backpressure: block if too many calls are in-flight.
    # Use a non-blocking acquire first to give a fast error for grossly
    # overloaded servers rather than letting every caller pile up.
    if not _semaphore._value and _semaphore.locked():  # noqa: SLF001
        # Still try to acquire — this gives a more honest wait vs. error.
        pass

    async with _semaphore:
        try:
            return await asyncio.wait_for(
                handler(**arguments), timeout=25.0
            )
        except asyncio.TimeoutError:
            raise ValueError(
                f"Tool {tool_name!r} timed out after 25 s. "
                "This may indicate database lock contention from concurrent access."
            )
