
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

# Thread pool for synchronous DB operations
_db_workers = max(4, int(os.getenv("COGNEX_DB_WORKERS", "8")))
_db_executor = ThreadPoolExecutor(
    max_workers=_db_workers, thread_name_prefix="cognex-db"
)

# Backpressure semaphore
#
# Limits the number of tool calls that can be executing concurrently.
# When all permits are taken, additional callers wait (back-pressure) rather
# than spawning new threads that could exhaust the SQLite WAL file-descriptor
# limit or the OS thread count.
_max_queued = max(1, int(os.getenv("COGNEX_MAX_QUEUED", "12")))
_semaphore = asyncio.Semaphore(_max_queued)


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, partial(func, *args, **kwargs))


# Import all handler modules

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
    trust_query,
    trust_manage,
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
    unit_decay_stale,
)
from cognex_mcp.tools.audit_tools import (
    audit_get_recent,
    audit_verify,
    audit_verify_chain,
)
from cognex_mcp.tools.health_tools import (
    cognex_health,
)
from cognex_mcp.tools.recall_tools import (
    recall,
)
from cognex_mcp.tools.state_tools import (
    provenance_trace,
    provenance_link,
    question_raise,
    question_resolve,
    integrity_verify,
    handoff_create,
    handoff_resume,
    reconcile_resolve,
    note_reasoning,
)

# CHP tools gated behind COGNEX_EXPERIMENTAL=1
_EXPERIMENTAL = os.environ.get("COGNEX_EXPERIMENTAL", "").lower() in ("1", "true", "yes")
if _EXPERIMENTAL:
    from cognex_mcp.tools.chp_tools import (
        chp_create_channel,
        chp_transfer,
        chp_project,
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


# Wrap deprecated search tools as thin aliases to `recall`.
# Deprecated aliases preserve the original return shape (full content)
# for one release so existing callers don't break.
async def _deprecated_memory_search(**kwargs: Any) -> Any:
    res = await recall(
        query=kwargs.get("query", ""),
        kind="memory",
        detail="full",
        filters={k: v for k, v in kwargs.items()
                 if k in ("project", "type", "tags") and v},
        limit=kwargs.get("limit", 20),
    )
    memories = res.get("memories", [])
    return {
        "count": len(memories),
        "memories": [
            {
                "id": m["id"],
                "content": m.get("content", ""),
                "type": m["type"],
                "scope": m.get("scope", "private"),
                "project": m.get("project", ""),
                "tags": m.get("tags", []),
                "relevance": m.get("score", 0),
                "created_at": m["date"],
            }
            for m in memories
        ],
    }

async def _deprecated_memory_get_context(**kwargs: Any) -> Any:
    res = await recall(
        query=kwargs.get("query", ""),
        kind="memory",
        detail="full",
        filters={k: v for k, v in kwargs.items()
                 if k in ("project",) and v},
        limit=kwargs.get("limit", 5),
    )
    memories = res.get("memories", [])
    return {
        "memories": [
            {
                "content": m.get("content", ""),
                "type": m["type"],
                "score": m.get("score", 0),
                "tags": m.get("tags", []),
                "id": m["id"],
            }
            for m in memories
        ],
        "count": len(memories),
        "search_type": "recall",
    }

async def _deprecated_unit_search(**kwargs: Any) -> Any:
    res = await recall(
        query=kwargs.get("query", ""),
        kind="unit",
        detail="full",
        filters={k: v for k, v in kwargs.items()
                 if k in ("project", "type") and v},
        limit=kwargs.get("limit", 20),
    )
    units = res.get("units", [])
    return {
        "count": len(units),
        "units": [
            {
                "unit_id": u["id"],
                "unit_type": u["type"],
                "content": u.get("content", ""),
                "rationale": u.get("rationale", ""),
                "scope": u.get("scope", ""),
                "confidence": u.get("score", 1.0),
                "created_at": u["date"],
            }
            for u in units
        ],
    }

async def _deprecated_unit_get_relevant(**kwargs: Any) -> Any:
    res = await recall(
        query=kwargs.get("query", ""),
        kind="unit",
        detail="full",
        filters={k: v for k, v in kwargs.items()
                 if k in ("project",) and v},
        limit=kwargs.get("limit", 10),
    )
    units = res.get("units", [])
    return {
        "count": len(units),
        "units": [
            {
                "unit_id": u["id"],
                "unit_type": u["type"],
                "content": u.get("content", ""),
                "rationale": u.get("rationale", ""),
                "scope": u.get("scope", ""),
                "confidence": u.get("score", 1.0),
                "staleness": 0.0,
                "relevance_score": u.get("score", 0),
            }
            for u in units
        ],
    }

async def _deprecated_ledger_find_similar(**kwargs: Any) -> Any:
    res = await recall(
        query=kwargs.get("query", ""),
        kind="decision",
        detail="full",
        filters={k: v for k, v in kwargs.items()
                 if k in ("project",) and v},
        limit=kwargs.get("limit", 5),
    )
    decisions = res.get("decisions", [])
    return {
        "count": len(decisions),
        "decisions": [
            {
                "id": d["id"],
                "tool_used": d.get("tool_used", ""),
                "reasoning": d.get("reasoning", ""),
                "context": d.get("context", ""),
                "outcome": d.get("outcome", ""),
                "outcome_success": d.get("outcome_success"),
                "timestamp": d["date"],
            }
            for d in decisions
        ],
    }


# Master dispatch table

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
    "memory_decay":                memory_decay,
    "recall":                      recall,
    "memory_search":               _deprecated_memory_search,
    "memory_get_context":          _deprecated_memory_get_context,
    # Trust tools
    "trust_query":                 trust_query,
    "trust_manage":                trust_manage,
    "trust_check":                 trust_check,   # deprecated alias
    "trust_record":                trust_record,  # deprecated alias
    "trust_get":                   trust_get,     # hidden deprecated alias
    "trust_summary":               trust_summary, # hidden deprecated alias
    # Ledger tools
    "ledger_record":               ledger_record,
    "ledger_outcome":              ledger_outcome,
    "ledger_find_similar":         _deprecated_ledger_find_similar,
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
    "unit_mark_overridden":        unit_mark_overridden,
    "unit_verify":                 unit_verify,
    "unit_decay_stale":            unit_decay_stale,
    "unit_search":                 _deprecated_unit_search,
    "unit_get_relevant":           _deprecated_unit_get_relevant,
    # Audit log tools
    "audit_get_recent":            audit_get_recent,
    "audit_verify":                audit_verify,
    "audit_verify_chain":          audit_verify_chain,
    # Cognitive state replication tools
    "provenance_trace":            provenance_trace,
    "provenance_link":             provenance_link,
    "question_raise":              question_raise,
    "question_resolve":            question_resolve,
    "integrity_verify":            integrity_verify,
    "handoff_create":              handoff_create,
    "handoff_resume":              handoff_resume,
    "reconcile_resolve":           reconcile_resolve,
    "note_reasoning":              note_reasoning,
    # Optional tools (Phase 3/4)
    **_optional_tools,
}

if _EXPERIMENTAL:
    TOOL_HANDLERS["chp_create_channel"] = chp_create_channel
    TOOL_HANDLERS["chp_transfer"] = chp_transfer
    TOOL_HANDLERS["chp_project"] = chp_project


# Dispatcher

async def handle_tool_call(tool_name: str, arguments: dict[str, Any] | None) -> Any:
    arguments = arguments or {}
    if tool_name not in TOOL_HANDLERS:
        raise ValueError(f"Unknown tool: {tool_name!r}. Call list_tools to see available tools.")

    handler = TOOL_HANDLERS[tool_name]

    async with _semaphore:
        try:
            return await asyncio.wait_for(handler(**arguments), timeout=25.0)
        except asyncio.TimeoutError:
            raise ValueError(
                f"Tool {tool_name!r} timed out after 25 s. "
                "This may indicate database lock contention from concurrent access."
            )
