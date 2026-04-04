"""
Teleport example.
Shows how to export your cognitive substrate state and rehydrate it elsewhere.
"""

import sys
import asyncio
import json

sys.path.insert(0, "../src")

from substrate_mcp.tools import handle_tool_call


async def main():
    # Step 1: Add some memories to export
    await handle_tool_call(
        "memory_add",
        {
            "content": "Always use type hints in Python code",
            "memory_type": "preference",
            "project": "example",
        },
    )

    await handle_tool_call(
        "memory_add",
        {
            "content": "FastAPI is the preferred framework for APIs",
            "memory_type": "decision",
            "project": "example",
        },
    )

    # Step 2: Export the full state as a bundle
    result = await handle_tool_call(
        "teleport_create_bundle",
        {"source_host": "dev-machine-01", "target_host": "production-server"},
    )
    print("Bundle created:")
    bundle = json.loads(result)
    print(f"  Memories exported: {bundle.get('memory_count', 'N/A')}")
    print(f"  Source: {bundle.get('source_host', 'N/A')}")
    print(f"  Target: {bundle.get('target_host', 'N/A')}")

    # Save bundle to file for transfer
    with open("teleport_bundle.json", "w") as f:
        json.dump(bundle, f, indent=2)
    print("  Saved to: teleport_bundle.json")

    # Step 3: Rehydrate on the target machine (simulated)
    # In real usage, you'd copy the JSON file to the other machine
    # and call teleport_rehydrate with its contents
    result = await handle_tool_call(
        "teleport_rehydrate", {"bundle_json": json.dumps(bundle)}
    )
    print("\nRehydration result:", result)


if __name__ == "__main__":
    asyncio.run(main())
