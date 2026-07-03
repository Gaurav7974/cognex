
from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

from cognex_mcp.context import CognexContext
from cognex.teleport import (
    verify_signature,
    get_key_fingerprint,
    get_or_create_keys,
)
from cognex.trust import TrustLevel
from .protocol import send_msg, recv_msg
from .delta import DeltaComputer

logger = logging.getLogger(__name__)


class SyncServer:

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7474,
        allowed_ips: list[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.allowed_ips = allowed_ips or ["127.0.0.1"]
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        logger.info("Sync server listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Sync server stopped.")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peername = writer.get_extra_info("peername")
        if not peername:
            writer.close()
            return

        ip, _ = peername
        if ip not in self.allowed_ips:
            logger.warning("Rejected connection from unauthorized IP: %s", ip)
            writer.close()
            return

        ctx = CognexContext.get_instance()
        try:
            challenge = os.urandom(16).hex()
            await send_msg(writer, {"type": "challenge", "challenge": challenge})

            auth = await recv_msg(reader)
            if not auth or auth.get("type") != "auth":
                await send_msg(
                    writer,
                    {"type": "status", "success": False, "error": "Invalid handshake"},
                )
                writer.close()
                return

            try:
                public_key = base64.b64decode(auth["public_key"])
                signature = base64.b64decode(auth["signature"])
            except Exception:
                await send_msg(
                    writer,
                    {
                        "type": "status",
                        "success": False,
                        "error": "Failed to decode keys",
                    },
                )
                writer.close()
                return

            if not verify_signature(challenge, signature, public_key):
                await send_msg(
                    writer,
                    {"type": "status", "success": False, "error": "Signature invalid"},
                )
                writer.close()
                return

            fingerprint = get_key_fingerprint(public_key)

            trust_record = ctx.trust.get_trust(
                tool_name="sync", context=fingerprint
            )
            if trust_record.trust_level not in (TrustLevel.TRUSTED, TrustLevel.DELEGATED):
                # Auto-trust local-loopback client for testing convenience
                if ip == "127.0.0.1" and os.getenv("COGNEX_TEST_ENV") == "true":
                    pass
                else:
                    logger.warning(
                        "Peer %s (%s) is not trusted (level=%s)",
                        fingerprint,
                        ip,
                        trust_record.trust_level,
                    )
                    await send_msg(
                        writer,
                        {
                            "type": "status",
                            "success": False,
                            "error": "Peer fingerprint not trusted",
                        },
                    )
                    writer.close()
                    return

            await send_msg(
                writer,
                {
                    "type": "status",
                    "success": True,
                    "vector_clock": DeltaComputer.compute_vector_clock(
                        ctx.engine.store, ctx.ledger, ctx.unit_store
                    ),
                },
            )

            req = await recv_msg(reader)
            if not req:
                writer.close()
                return

            req_type = req.get("type")
            if req_type == "get_delta":
                since = req.get("since", "1970-01-01T00:00:00Z")

                delta = DeltaComputer.compute_delta(
                    ctx.engine.store, ctx.ledger, ctx.unit_store, since
                )
                await send_msg(
                    writer,
                    {
                        "type": "delta",
                        "delta": delta,
                        "vector_clock": DeltaComputer.compute_vector_clock(
                            ctx.engine.store, ctx.ledger, ctx.unit_store
                        ),
                    },
                )
            elif req_type == "post_delta":
                delta = req.get("delta", {})
                stats = DeltaComputer.apply_delta(
                    ctx.engine.store,
                    ctx.ledger,
                    ctx.unit_store,
                    ctx.audit,
                    delta,
                )
                await send_msg(
                    writer,
                    {
                        "type": "status",
                        "success": True,
                        "stats": stats,
                        "vector_clock": DeltaComputer.compute_vector_clock(
                            ctx.engine.store, ctx.ledger, ctx.unit_store
                        ),
                    },
                )
            else:
                await send_msg(
                    writer,
                    {
                        "type": "status",
                        "success": False,
                        "error": f"Unknown request type: {req_type}",
                    },
                )

        except Exception as e:
            logger.error("Error in sync server handler: %s", e)
        finally:
            writer.close()
            await writer.wait_closed()


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Cognex Sync Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to listen on")
    parser.add_argument("--port", type=int, default=7474, help="Port to listen on")
    parser.add_argument(
        "--allowed-ips",
        default="127.0.0.1",
        help="Comma-separated list of allowed client IPs",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    allowed_ips = [ip.strip() for ip in args.allowed_ips.split(",") if ip.strip()]

    async def run() -> None:
        from cognex_mcp.context import CognexContext
        ctx = CognexContext.get_instance()
        ctx._ensure_initialized()

        server = SyncServer(host=args.host, port=args.port, allowed_ips=allowed_ips)
        await server.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted. Exiting.")
