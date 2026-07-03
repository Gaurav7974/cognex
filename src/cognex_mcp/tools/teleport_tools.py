
import json
from typing import Any

from cognex_mcp.context import CognexContext
from cognex_mcp.tools.dispatcher import run_in_thread


async def teleport_create_bundle(
    source_host: str | None = None,
    target_host: str | None = None,
    pending_tasks: list[str] | None = None,
    last_action: str | None = None,
    model_name: str | None = None,
    tool_claims: list[str] | None = None,
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

    bundle = ctx.teleport.create_bundle(
        engine=ctx.engine,
        source_host=source_host or "",
        target_host=target_host or "",
        pending_tasks=tuple(pending_tasks or []),
        last_action=last_action or "",
        model_name=model_name or "",
        tool_claims=tuple(tool_claims or []),
        trust_engine=ctx.trust,
        decision_ledger=ctx.ledger,
        unit_store=ctx.unit_store,
    )

    # Audit log (direct call - AuditLog is thread-safe)
    ctx.audit.append(
        event_type="bundle_created",
        session_id=ctx.engine.get_current_session(),
        project=None,
        agent_id=None,
        payload={"bundle_id": bundle.bundle_id, "source_host": source_host or "", "target_host": target_host or ""},
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
    ctx = CognexContext.get_instance()

    from cognex import StateBundle

    # Handle multiple input forms:
    # 1. Raw serialized bundle string (from StateBundle.serialize())
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
        bundle = StateBundle.deserialize(bundle_json)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid bundle format: {e}")

    memory_conflicts = ctx.reconciler.classify_memories(list(bundle.memories))
    unit_conflicts = ctx.reconciler.classify_units(list(bundle.cognitive_units))
    if memory_conflicts["conflicts"] or unit_conflicts["conflicts"]:
        ctx.audit.append(
            event_type="bundle_rehydrate_conflicts",
            session_id=ctx.engine.get_current_session(),
            project=bundle.project,
            agent_id=None,
            payload={
                "bundle_id": bundle.bundle_id,
                "memory_conflicts": len(memory_conflicts["conflicts"]),
                "unit_conflicts": len(unit_conflicts["conflicts"]),
            },
        )
        return {
            "status": "conflicts",
            "bundle_id": bundle.bundle_id,
            "memory_conflicts": memory_conflicts["conflicts"],
            "unit_conflicts": unit_conflicts["conflicts"],
            "message": "Conflicted items were not imported; resolve with reconcile_resolve.",
        }

    report = ctx.teleport.rehydrate(
        bundle=bundle,
        engine=ctx.engine,
        trust_engine=ctx.trust,
        decision_ledger=ctx.ledger,
        unit_store=ctx.unit_store,
    )

    # Audit log (direct call - AuditLog is thread-safe)
    ctx.audit.append(
        event_type="bundle_rehydrated",
        session_id=ctx.engine.get_current_session(),
        project=None,
        agent_id=None,
        payload={"bundle_id": report.get("bundle_id", ""), "memories_restored": report.get("memories_restored", 0)},
    )

    return {
        "status": report.get("status", "rehydrated"),
        "bundle_version": report.get("bundle_version", "1.0"),
        "memories_restored": report.get("memories_restored", 0),
        "decisions_restored": report.get("decisions_restored", 0),
        "sessions_restored": report.get("sessions_restored", 0),
        "trust_restored": report.get("trust_restored", False),
        "units_restored": report.get("units_restored", 0),
        "reconciliation": {
            "memories": {
                "new": len(memory_conflicts["new"]),
                "identical": len(memory_conflicts["identical"]),
            },
            "units": {
                "new": len(unit_conflicts["new"]),
                "identical": len(unit_conflicts["identical"]),
            },
        },
        "bundle_id": report.get("bundle_id", ""),
    }
