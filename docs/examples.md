# Usage Examples

## Basic Memory Operations

### Add and Search Memories

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

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

## Session Arcs Workflow

### Start Arc, Work, Close Arc

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

async def main():
    # 1. Start a session arc for the week
    await handle_tool_call("arc_start", {
        "project": "my-api"
    })

    # 2. Start a daily session
    await handle_tool_call("cognex_start_session", {
        "session_id": "session-001",
        "project": "my-api"
    })

    # 3. Record a structured State Unit
    await handle_tool_call("unit_commit", {
        "content": "Use pytest instead of unittest",
        "rationale": "Better fixtures and less boilerplate",
        "unit_type": "decision",
        "scope": "my-api/testing",
        "project": "my-api"
    })

    # 4. End the daily session
    await handle_tool_call("cognex_end_session", {
        "summary": "Set up project testing structure"
    })

    # 5. At the end of the week, close the arc
    # (In reality, you need the arc_id returned from arc_start)
    await handle_tool_call("arc_close", {
        "arc_id": "arc_123456"
    })

asyncio.run(main())
```

---

## Trust Engine & Audit

### Check Trust and Verify Logs

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

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

    # Verify the cryptographically signed audit log chain
    result = await handle_tool_call("audit_verify_chain", {
        "limit": 100
    })
    print("Audit verified:", result)

asyncio.run(main())
```

---

## Peer-to-Peer Sync

### Push and Pull State Across Machines

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

async def main():
    # Push your local changes to a remote machine running the TCP sync server
    result = await handle_tool_call("sync_push", {
        "peer_host": "192.168.1.100",
        "peer_port": 7474
    })
    print("Pushed:", result)

    # Pull changes from the remote machine and merge them locally
    result = await handle_tool_call("sync_pull", {
        "peer_host": "192.168.1.100",
        "peer_port": 7474
    })
    print("Pulled & Merged:", result)

asyncio.run(main())
```

---

## State Transfer

### Export and Import Agent State via Bundles

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

async def main():
    # Export full state to an Ed25519-signed bundle
    bundle = await handle_tool_call("teleport_create_bundle", {
        "source_host": "dev-machine",
        "target_host": "production"
    })

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

## State Units (Cognitive State)

### Checkout and Commit Units

```python
import asyncio
from cognex_mcp.tools import handle_tool_call

async def main():
    # Checkout the full structured state for a project
    state = await handle_tool_call("unit_checkout", {
        "project": "my-api"
    })
    print("Current Project State:", state)

    # Commit a new progress state unit
    result = await handle_tool_call("unit_commit", {
        "content": "Finished implementing the Auth module",
        "rationale": "All tests are passing and JWTs are secure",
        "unit_type": "progress",
        "scope": "my-api/auth",
        "project": "my-api"
    })
    print("Committed:", result)

asyncio.run(main())
```
