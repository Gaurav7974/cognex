# Usage Examples

## Basic Memory Operations

### Add and Search Memories

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    # Add a preference
    result = await handle_tool_call("memory_add", {
        "content": "Always use type hints in Python code",
        "memory_type": "preference",
        "project": "my-api"
    })
    print("Added:", result)

    # Search for it later
    result = await handle_tool_call("memory_search", {
        "query": "python type hints",
        "project": "my-api"
    })
    print("Found:", result)

asyncio.run(main())
```

---

## Full Session Workflow

### Start, Work, End

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    # 1. Start a session
    await handle_tool_call("substrate_start_session", {
        "session_id": "session-001",
        "project": "my-api"
    })

    # 2. Process conversation
    await handle_tool_call("substrate_process_transcript", {
        "transcript": "I prefer pytest over unittest for testing.",
        "session_id": "session-001",
        "project": "my-api"
    })

    # 3. Record a decision
    await handle_tool_call("ledger_record", {
        "tool_used": "pytest",
        "reasoning": "Better fixtures and less boilerplate",
        "context": "Choosing test framework",
        "tags": ["testing"]
    })

    # 4. End session
    await handle_tool_call("substrate_end_session", {
        "summary": "Set up project structure",
        "key_decisions": ["Use pytest"],
        "tools_used": ["memory_add", "ledger_record"],
        "input_tokens": 5000,
        "output_tokens": 3000
    })

asyncio.run(main())
```

---

## Trust Engine

### Check and Record Tool Trust

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    # Check if a tool needs approval
    result = await handle_tool_call("trust_check", {
        "tool_name": "filesystem_write",
        "operation": "write_file"
    })
    print("Needs approval?", result)

    # Record user's decision
    await handle_tool_call("trust_record", {
        "action": "approval",
        "tool_name": "filesystem_write",
        "operation": "write_file",
        "reason": "Trusted operation"
    })

    # Get trust summary
    result = await handle_tool_call("trust_summary")
    print("Trust summary:", result)

asyncio.run(main())
```

---

## Teleport (State Transfer)

### Export and Import Agent State

```python
import asyncio
import json
from substrate_mcp.tools import handle_tool_call

async def main():
    # Export full state
    bundle = await handle_tool_call("teleport_create_bundle", {
        "source_host": "dev-machine",
        "target_host": "production"
    })

    # Save to file
    with open("bundle.json", "w") as f:
        f.write(bundle)

    # On target machine, rehydrate:
    with open("bundle.json", "r") as f:
        bundle_json = f.read()

    result = await handle_tool_call("teleport_rehydrate", {
        "bundle_json": bundle_json
    })
    print("Rehydrated:", result)

asyncio.run(main())
```

---

## Swarm Mode

### Compile Intent into Multi-Agent Plan

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    result = await handle_tool_call("swarm_compile_intent", {
        "intent": "Build a REST API with authentication, user CRUD, and rate limiting",
        "project": "my-api"
    })
    print("Plan:", result)

asyncio.run(main())
```

---

## Memory Decay

### Clean Up Old Memories

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    # Age all memories by 5% (default factor)
    result = await handle_tool_call("memory_decay", {
        "factor": 0.95
    })
    print("Decayed:", result)

asyncio.run(main())
```

---

## Substrate Report

### Get Health Statistics

```python
import asyncio
from substrate_mcp.tools import handle_tool_call

async def main():
    result = await handle_tool_call("substrate_report")
    print(result)

asyncio.run(main())
```

---

## Using Cognex Programmatically (Without MCP)

You can also use the core substrate directly:

```python
import sys
sys.path.insert(0, 'src')

from substrate.substrate import CognitiveSubstrate

substrate = CognitiveSubstrate()

# Start session
substrate.start_session("session-001", project="my-api")

# Add memory
substrate.add_memory(
    content="Use pytest for testing",
    memory_type="preference",
    project="my-api"
)

# Get context
context = substrate.get_context(query="testing", project="my-api")
print(context)

# End session
substrate.end_session(
    summary="Set up testing",
    key_decisions=("Use pytest",),
    tools_used=("add_memory",)
)
```
