"""
Teleport tools - state serialization and transfer.
"""

import json
from typing import Any

from substrate_mcp.context import SubstrateContext


async def teleport_create_bundle(
    source_host: str | None = None,
    target_host: str | None = None,
    pending_tasks: list[str] | None = None,
    last_action: str | None = None,
    model_name: str | None = None,
    tool_claims: list[str] | None = None,
) -> dict[str, Any]:
    """Create a teleport bundle for state transfer."""
    ctx = SubstrateContext.get_instance()

    bundle = ctx.teleport.create_bundle(
        substrate=ctx.substrate,
        source_host=source_host or "",
        target_host=target_host or "",
        pending_tasks=tuple(pending_tasks or []),
        last_action=last_action or "",
        model_name=model_name or "",
        tool_claims=tuple(tool_claims or []),
        trust_engine=ctx.trust,
    )

    return {
        "bundle_id": bundle.bundle_id,
        "created_at": bundle.created_at.isoformat(),
        "source_host": bundle.source_host,
        "target_host": bundle.target_host,
        "serialized": bundle.serialize(),
    }


async def teleport_rehydrate(bundle_json: str) -> dict[str, Any]:
    """Rehydrate substrate state from a bundle."""
    ctx = SubstrateContext.get_instance()

    from substrate import TeleportBundle

    if isinstance(bundle_json, dict):
        bundle_json = json.dumps(bundle_json)

    try:
        bundle = TeleportBundle.deserialize(bundle_json)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid bundle format: {e}")

    report = ctx.teleport.rehydrate(
        bundle=bundle, substrate=ctx.substrate, trust_engine=ctx.trust
    )

    return {
        "status": report.get("status", "rehydrated"),
        "memories_restored": report.get("memories_restored", 0),
        "sessions_restored": report.get("sessions_restored", 0),
        "trust_restored": report.get("trust_restored", False),
    }
