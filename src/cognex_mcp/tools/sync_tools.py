"""Sync tools - exposes MCP tools for P2P cognex synchronization."""

from typing import Any
import logging

from cognex_sync.client import SyncClient

logger = logging.getLogger(__name__)


async def sync_push(
    peer_host: str,
    peer_port: int = 7474,
) -> dict[str, Any]:
    """Push local cognex changes (memories, decisions, cognitive units) to a peer."""
    if not peer_host:
        raise ValueError("peer_host is required")

    client = SyncClient(host=peer_host, port=peer_port)
    result = await client.push()
    return result


async def sync_pull(
    peer_host: str,
    peer_port: int = 7474,
) -> dict[str, Any]:
    """Pull remote cognex changes (memories, decisions, cognitive units) from a peer and merge them."""
    if not peer_host:
        raise ValueError("peer_host is required")

    client = SyncClient(host=peer_host, port=peer_port)
    result = await client.pull_and_merge()
    return result
