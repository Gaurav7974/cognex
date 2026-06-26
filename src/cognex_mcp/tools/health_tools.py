"""Cognex health check tool.

Provides a single ``cognex_health`` tool that returns a comprehensive
status snapshot of all Cognex components.  Intended to be called at the
start of each session to confirm the engine is operational before any
memory or session operations are attempted.
"""

from __future__ import annotations

from typing import Any

from cognex_mcp.context import CognexContext


async def cognex_health() -> dict[str, Any]:
    """Return a health snapshot for all Cognex engine components.

    Checks:
    - Whether all components are initialised.
    - Whether the database is reachable (executes a lightweight COUNT query).
    - Whether FTS5 full-text search is compiled into this SQLite build.
    - The current memory count for a quick sanity check.
    - Uptime since the server was last started.

    Returns:
        Dict with keys:
        - ``status``           — ``"ok"`` | ``"degraded"``
        - ``initialized``      — bool
        - ``db_path``          — str
        - ``db_reachable``     — bool
        - ``fts5_available``   — bool
        - ``memory_count``     — int | None
        - ``startup_at``       — ISO-8601 timestamp | None
        - ``uptime_seconds``   — float | None
        - ``components``       — dict of component → ``"ok"`` | ``"missing"``
    """
    ctx = CognexContext.get_instance()
    return ctx.health_check()
