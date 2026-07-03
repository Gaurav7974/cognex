
from __future__ import annotations

import asyncio
import json
import logging
import struct
from typing import Any

logger = logging.getLogger(__name__)


async def send_msg(writer: asyncio.StreamWriter, msg: dict[str, Any]) -> None:
    try:
        data = json.dumps(msg).encode("utf-8")
        header = struct.pack("!I", len(data))
        writer.write(header)
        writer.write(data)
        await writer.drain()
    except Exception as e:
        logger.error("Failed to send message: %s", e)
        raise


async def recv_msg(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    try:
        header = await reader.readexactly(4)
        length = struct.unpack("!I", header)[0]
        data = await reader.readexactly(length)
        return json.loads(data.decode("utf-8"))
    except asyncio.IncompleteReadError:
        # Graceful socket EOF / closed connection
        return None
    except Exception as e:
        logger.error("Failed to receive message: %s", e)
        raise
