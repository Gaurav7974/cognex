"""TCP sync client for Cognex delta replication."""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any

from cognex_mcp.context import CognexContext
from cognex.teleport import (
    sign_bundle,
    get_or_create_keys,
    get_key_fingerprint,
)
from cognex.models import MemoryEntry, CognitiveUnit
from cognex.ledger import DecisionEntry
from .protocol import send_msg, recv_msg
from .delta import DeltaComputer, MergeResolver

logger = logging.getLogger(__name__)


class SyncClient:
    """Sync client that connects to a peer server, pulls deltas, and merges them."""

    def __init__(self, host: str, port: int = 7474) -> None:
        self.host = host
        self.port = port

    async def pull_and_merge(self) -> dict[str, Any]:
        """Connect to the peer, fetch its deltas, and merge into local databases."""
        ctx = CognexContext.get_instance()
        reader, writer = await asyncio.open_connection(self.host, self.port)

        try:
            # 1. Read cryptographic challenge
            challenge_msg = await recv_msg(reader)
            if not challenge_msg or challenge_msg.get("type") != "challenge":
                raise RuntimeError("Invalid handshake: challenge missing")

            challenge = challenge_msg["challenge"]

            # 2. Sign challenge and authenticate
            private_bytes, public_pem = get_or_create_keys()
            signature = sign_bundle(challenge, private_bytes)

            auth_msg = {
                "type": "auth",
                "public_key": base64.b64encode(public_pem).decode("utf-8"),
                "signature": base64.b64encode(signature).decode("utf-8"),
            }
            await send_msg(writer, auth_msg)

            # 3. Read auth status
            status_msg = await recv_msg(reader)
            if not status_msg or not status_msg.get("success"):
                err = (
                    status_msg.get("error")
                    if status_msg
                    else "Authentication failed"
                )
                raise PermissionError(f"Sync connection rejected: {err}")

            # 4. Find since timestamp from local clocks
            clocks = DeltaComputer.compute_vector_clock(
                ctx.engine.store, ctx.ledger, ctx.unit_store
            )
            since = min(clocks.values())

            # 5. Send request
            await send_msg(writer, {"type": "get_delta", "since": since})

            # 6. Receive delta response
            response = await recv_msg(reader)
            if not response or response.get("type") != "delta":
                raise RuntimeError("Invalid delta response from peer")

            delta = response["delta"]
            peer_clocks = response["vector_clock"]

            # 7. Merge deltas
            stats = {"memories": 0, "decisions": 0, "cognitive_units": 0, "conflicts": 0}

            # Merge memories
            for m_dict in delta.get("memories", []):
                remote_mem = MemoryEntry.from_dict(m_dict)
                local_mem = ctx.engine.store.get(remote_mem.id)

                if local_mem:
                    winner = MergeResolver.resolve_memory_conflict(
                        local_mem, remote_mem
                    )
                    if winner == remote_mem:
                        ctx.engine.store.delete(local_mem.id)
                        ctx.engine.store.save(remote_mem)
                        ctx.audit.append(
                            event_type="sync_merge_conflict",
                            payload={
                                "type": "memory",
                                "id": remote_mem.id,
                                "action": "overwritten",
                            },
                        )
                        stats["conflicts"] += 1
                        stats["memories"] += 1
                else:
                    ctx.engine.store.save(remote_mem)
                    stats["memories"] += 1

            # Merge decisions
            for d_dict in delta.get("decisions", []):
                remote_dec = DecisionEntry.from_dict(d_dict)
                local_dec = ctx.ledger.get(remote_dec.id)

                if local_dec:
                    winner = MergeResolver.resolve_decision_conflict(
                        local_dec, remote_dec
                    )
                    if winner == remote_dec:
                        ctx.ledger._save(remote_dec)
                        ctx.audit.append(
                            event_type="sync_merge_conflict",
                            payload={
                                "type": "decision",
                                "id": remote_dec.id,
                                "action": "overwritten",
                            },
                        )
                        stats["conflicts"] += 1
                        stats["decisions"] += 1
                else:
                    ctx.ledger._save(remote_dec)
                    stats["decisions"] += 1

            # Merge cognitive units
            for u_dict in delta.get("cognitive_units", []):
                remote_unit = CognitiveUnit(
                    unit_id=u_dict["unit_id"],
                    unit_type=u_dict["unit_type"],
                    content=u_dict["content"],
                    rationale=u_dict.get("rationale", ""),
                    scope=u_dict.get("scope", ""),
                    confidence=u_dict.get("confidence", 1.0),
                    tags=tuple(u_dict.get("tags", [])),
                    created_at=datetime.fromisoformat(u_dict["created_at"]),
                    session_id=u_dict.get("session_id", ""),
                    project=u_dict.get("project", ""),
                    override_count=u_dict.get("override_count", 0),
                    last_verified=datetime.fromisoformat(u_dict["last_verified"])
                    if u_dict.get("last_verified")
                    else None,
                )
                local_unit = ctx.unit_store.get(remote_unit.unit_id)

                if local_unit:
                    winner = MergeResolver.resolve_unit_conflict(
                        local_unit, remote_unit
                    )
                    if winner == remote_unit:
                        ctx.unit_store.save(remote_unit)
                        ctx.audit.append(
                            event_type="sync_merge_conflict",
                            payload={
                                "type": "cognitive_unit",
                                "id": remote_unit.unit_id,
                                "action": "overwritten",
                            },
                        )
                        stats["conflicts"] += 1
                        stats["cognitive_units"] += 1
                else:
                    ctx.unit_store.save(remote_unit)
                    stats["cognitive_units"] += 1

            return {
                "status": "success",
                "stats": stats,
                "peer_clock": peer_clocks,
            }

        finally:
            writer.close()
            await writer.wait_closed()

    async def push(self) -> dict[str, Any]:
        """Connect to the peer, fetch its vector clock, compile local changes, and push them."""
        ctx = CognexContext.get_instance()
        reader, writer = await asyncio.open_connection(self.host, self.port)

        try:
            # 1. Read cryptographic challenge
            challenge_msg = await recv_msg(reader)
            if not challenge_msg or challenge_msg.get("type") != "challenge":
                raise RuntimeError("Invalid handshake: challenge missing")

            challenge = challenge_msg["challenge"]

            # 2. Sign challenge and authenticate
            private_bytes, public_pem = get_or_create_keys()
            signature = sign_bundle(challenge, private_bytes)

            auth_msg = {
                "type": "auth",
                "public_key": base64.b64encode(public_pem).decode("utf-8"),
                "signature": base64.b64encode(signature).decode("utf-8"),
            }
            await send_msg(writer, auth_msg)

            # 3. Read auth status
            status_msg = await recv_msg(reader)
            if not status_msg or not status_msg.get("success"):
                err = (
                    status_msg.get("error")
                    if status_msg
                    else "Authentication failed"
                )
                raise PermissionError(f"Sync connection rejected: {err}")

            # 4. Peer clock is in the auth success payload
            peer_clocks = status_msg["vector_clock"]
            since = min(peer_clocks.values())

            # 5. Compile local delta
            local_delta = DeltaComputer.compute_delta(
                ctx.engine.store, ctx.ledger, ctx.unit_store, since
            )

            # 6. Send post_delta request
            await send_msg(writer, {"type": "post_delta", "delta": local_delta})

            # 7. Receive status response
            response = await recv_msg(reader)
            if not response or response.get("type") != "status" or not response.get("success"):
                err = response.get("error") if response else "Unknown error"
                raise RuntimeError(f"Sync push rejected by peer: {err}")

            return {
                "status": "success",
                "stats": response.get("stats", {}),
                "peer_clock": response.get("vector_clock"),
            }

        finally:
            writer.close()
            await writer.wait_closed()
