"""
Session workflow example.
Shows the full lifecycle: start session -> do work -> end session.
"""

import sys
import asyncio

sys.path.insert(0, "../src")

from substrate_mcp.tools import handle_tool_call


async def main():
    # Step 1: Start a session
    result = await handle_tool_call(
        "substrate_start_session", {"session_id": "session-001", "project": "my-api"}
    )
    print("Session started:", result)

    # Step 2: Process some conversation transcript
    result = await handle_tool_call(
        "substrate_process_transcript",
        {
            "transcript": "I prefer using pytest over unittest for testing. Also, always use type hints in Python code.",
            "session_id": "session-001",
            "project": "my-api",
        },
    )
    print("Transcript processed:", result)

    # Step 3: Get a trust check example
    result = await handle_tool_call(
        "trust_check", {"tool_name": "filesystem_write", "operation": "write_file"}
    )
    print("Trust check:", result)

    # Step 4: Record a decision
    result = await handle_tool_call(
        "ledger_record",
        {
            "tool_used": "pytest",
            "alternatives": ["unittest", "nose"],
            "reasoning": "pytest has better fixtures and less boilerplate",
            "context": "Choosing test framework for my-api project",
            "tags": ["testing", "framework"],
        },
    )
    print("Decision recorded:", result)

    # Step 5: End the session
    result = await handle_tool_call(
        "substrate_end_session",
        {
            "summary": "Set up project structure and chose pytest as test framework",
            "key_decisions": ["Use pytest for testing", "Use FastAPI for API"],
            "tools_used": ["memory_add", "ledger_record", "trust_check"],
            "errors": [],
            "input_tokens": 5000,
            "output_tokens": 3000,
        },
    )
    print("Session ended:", result)


if __name__ == "__main__":
    asyncio.run(main())
