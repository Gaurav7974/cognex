
from __future__ import annotations

from typing import Any

from cognex_mcp.context import CognexContext


async def cognex_health() -> dict[str, Any]:
    ctx = CognexContext.get_instance()
    return ctx.health_check()
