
from typing import Any
import logging

from cognex_sync.client import SyncClient

logger = logging.getLogger(__name__)


async def sync_push(
    peer_host: str,
    peer_port: int = 7474,
) -> dict[str, Any]:
    if not peer_host:
        raise ValueError("peer_host is required")

    client = SyncClient(host=peer_host, port=peer_port)
    result = await client.push()
    return result


async def sync_pull(
    peer_host: str,
    peer_port: int = 7474,
) -> dict[str, Any]:
    if not peer_host:
        raise ValueError("peer_host is required")

    client = SyncClient(host=peer_host, port=peer_port)
    result = await client.pull_and_merge()
    return result
