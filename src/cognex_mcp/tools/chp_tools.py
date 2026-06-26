"""CHP Tools - Cognitive Handoff Protocol integration.

All handlers use the shared CHPProtocol singleton from CognexContext so
handoff state (entanglements) persists across tool calls. This fixes the
previous stateless bug where each call constructed a fresh CHPProtocol and
lost every pending handoff.
"""

from typing import Any

from cognex_mcp.context import CognexContext


async def chp_entangle(
    unit_id: str,
    source_agent: str,
    target_agent: str,
) -> dict[str, Any]:
    """Create an entanglement channel for Cognitive Unit transfer.

    The returned entanglement_key is required by chp_transfer to complete the
    handoff. State is held on the shared CHPProtocol instance, so a subsequent
    chp_transfer call (even in a different session) can resolve the channel.
    """
    if not unit_id:
        raise ValueError("unit_id is required")

    ctx = CognexContext.get_instance()
    entanglement_key = ctx.chp.create_entanglement(
        unit_id, source_agent, target_agent
    )

    return {
        "entanglement_key": entanglement_key,
        "unit_id": unit_id,
        "source_agent": source_agent,
        "target_agent": target_agent,
        "state": "entangled",
    }


async def chp_transfer(
    entanglement_key: str,
    unit_data: dict[str, Any],
) -> dict[str, Any]:
    """Transfer Cognitive Unit data via an entanglement channel.

    Resolves the channel created by chp_entangle on the shared instance and
    marks the handoff as transferred. Returns the resulting channel state so
    the caller can verify the handoff completed.
    """
    if not entanglement_key:
        raise ValueError("entanglement_key is required")

    ctx = CognexContext.get_instance()
    success = ctx.chp.transfer_via_entanglement(entanglement_key, unit_data)

    result: dict[str, Any] = {
        "success": success,
        "entanglement_key": entanglement_key,
    }

    if success:
        entanglement = ctx.chp.get_entanglement(entanglement_key)
        result["state"] = entanglement.get("state") if entanglement else None
        result["transferred"] = True
    else:
        # Channel not found or already used — surface why it failed
        entanglement = ctx.chp.get_entanglement(entanglement_key)
        result["state"] = entanglement.get("state") if entanglement else "not_found"

    return result


async def chp_project(unit: dict[str, Any]) -> dict[str, Any]:
    """Create a holographic projection of a Cognitive Unit for inspection."""
    from cognex.models import CognitiveUnit

    ctx = CognexContext.get_instance()
    unit_obj = CognitiveUnit(
        content=unit.get("content", ""),
        rationale=unit.get("rationale", ""),
        unit_type=unit.get("unit_type", "decision"),
        scope=unit.get("scope", ""),
        confidence=unit.get("confidence", 1.0),
        tags=tuple(unit.get("tags", [])),
    )
    return ctx.chp.holographic_project(unit_obj)
