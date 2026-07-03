
from typing import Any

from cognex_mcp.context import CognexContext


async def chp_create_channel(
    unit_id: str,
    source_agent: str,
    target_agent: str,
) -> dict[str, Any]:
    if not unit_id:
        raise ValueError("unit_id is required")

    ctx = CognexContext.get_instance()
    channel_key = ctx.chp.create_channel(
        unit_id, source_agent, target_agent
    )

    return {
        "channel_key": channel_key,
        "unit_id": unit_id,
        "source_agent": source_agent,
        "target_agent": target_agent,
        "state": "established",
    }


async def chp_transfer(
    channel_key: str,
    unit_data: dict[str, Any],
) -> dict[str, Any]:
    if not channel_key:
        raise ValueError("channel_key is required")

    ctx = CognexContext.get_instance()
    success = ctx.chp.transfer_via_channel(channel_key, unit_data)

    result: dict[str, Any] = {
        "success": success,
        "channel_key": channel_key,
    }

    if success:
        entanglement = ctx.chp.get_channel(channel_key)
        result["state"] = entanglement.get("state") if entanglement else None
        result["transferred"] = True
    else:
        # Channel not found or already used — surface why it failed
        entanglement = ctx.chp.get_channel(channel_key)
        result["state"] = entanglement.get("state") if entanglement else "not_found"

    return result


async def chp_project(unit: dict[str, Any]) -> dict[str, Any]:
    from cognex.models import StateUnit

    ctx = CognexContext.get_instance()
    unit_obj = StateUnit(
        content=unit.get("content", ""),
        rationale=unit.get("rationale", ""),
        unit_type=unit.get("unit_type", "decision"),
        scope=unit.get("scope", ""),
        confidence=unit.get("confidence", 1.0),
        tags=tuple(unit.get("tags", [])),
    )
    return ctx.chp.generate_state_view(unit_obj)
