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
    """Create a teleport bundle for state transfer.

    v2.0: Now includes full memory and decision content for cross-machine transfer.
    """
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
        decision_ledger=ctx.ledger,
    )

    return {
        "bundle_id": bundle.bundle_id,
        "version": bundle.version,
        "created_at": bundle.created_at.isoformat(),
        "source_host": bundle.source_host,
        "target_host": bundle.target_host,
        "memories_count": len(bundle.memories),
        "decisions_count": len(bundle.decisions),
        "trust_records_count": len(bundle.trust_records),
        "serialized": bundle.serialize(),
    }


async def teleport_rehydrate(bundle_json: str | dict) -> dict[str, Any]:
    """Rehydrate substrate state from a bundle.

    v2.0: Now restores full memory and decision content for cross-machine transfer.
    """
    ctx = SubstrateContext.get_instance()

    from substrate import TeleportBundle

    # Handle multiple input forms:
    # 1. Raw serialized bundle string (from TeleportBundle.serialize())
    # 2. JSON string of the wrapper dict from teleport_create_bundle
    # 3. Dict object from teleport_create_bundle
    if isinstance(bundle_json, dict):
        if "serialized" in bundle_json:
            bundle_json = bundle_json["serialized"]
        else:
            bundle_json = json.dumps(bundle_json)
    elif isinstance(bundle_json, str):
        # Could be raw serialized bundle OR JSON-encoded wrapper dict
        try:
            parsed = json.loads(bundle_json)
            if isinstance(parsed, dict) and "serialized" in parsed:
                bundle_json = parsed["serialized"]
            elif (
                isinstance(parsed, dict)
                and "bundle_id" in parsed
                and "version" not in parsed
            ):
                # It's the wrapper dict parsed — extract serialized
                bundle_json = parsed.get("serialized", bundle_json)
            # else: it's already the raw serialized bundle, use as-is
        except (json.JSONDecodeError, ValueError):
            pass  # Not JSON — assume raw serialized bundle

    if not isinstance(bundle_json, str):
        raise ValueError(
            f"Expected str or dict with 'serialized' key, got {type(bundle_json)}"
        )

    try:
        bundle = TeleportBundle.deserialize(bundle_json)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid bundle format: {e}")

    report = ctx.teleport.rehydrate(
        bundle=bundle,
        substrate=ctx.substrate,
        trust_engine=ctx.trust,
        decision_ledger=ctx.ledger,
    )

    return {
        "status": report.get("status", "rehydrated"),
        "bundle_version": report.get("bundle_version", "1.0"),
        "memories_restored": report.get("memories_restored", 0),
        "decisions_restored": report.get("decisions_restored", 0),
        "sessions_restored": report.get("sessions_restored", 0),
        "trust_restored": report.get("trust_restored", False),
        "bundle_id": report.get("bundle_id", ""),
    }
