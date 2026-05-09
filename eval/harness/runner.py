"""LongMemEval evaluation harness — test case loader for Cognex."""

import json
import asyncio
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.context import SubstrateContext
from substrate_mcp.tools.dispatcher import handle_tool_call


async def load_case(case: dict, tmp_db_path: str) -> None:
    """Load a single test case into a fresh Cognex context.
    
    Resets the singleton context, initializes with a unique db_path,
    adds the primary memory, then distractor memories.
    """
    SubstrateContext.reset_instance()
    SubstrateContext.get_instance(db_path=tmp_db_path, project=case["project"])

    # Store the primary memory
    await handle_tool_call("memory_add", {
        "content": case["memory_to_store"],
        "project": case["project"]
    })

    # Store distractor memories
    for distractor in case.get("distractor_memories", []):
        await handle_tool_call("memory_add", {
            "content": distractor,
            "project": case["project"]
        })
