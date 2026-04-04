# Tools Reference

Cognex provides **18 MCP tools** across 6 categories.

---

## Session Management (4 tools)

### `substrate_start_session`
Start a new session in the cognitive substrate and return relevant memories.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | Unique session identifier |
| `project` | string | No | `""` | Project name |

**Returns:** Session context with relevant memories loaded.

---

### `substrate_end_session`
End the current session with summary and metrics.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `summary` | string | No | — | Session summary |
| `key_decisions` | string[] | No | — | Key decisions made |
| `tools_used` | string[] | No | — | Tools used |
| `errors` | string[] | No | — | Errors encountered |
| `input_tokens` | integer | No | `0` | Input token count |
| `output_tokens` | integer | No | `0` | Output token count |

**Returns:** Session summary with metrics.

---

### `substrate_process_transcript`
Extract memories from a conversation transcript.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `transcript` | string | Yes | — | Conversation text |
| `session_id` | string | No | — | Session ID |
| `project` | string | No | — | Project name |
| `context` | string | No | — | Additional context |

**Returns:** Extracted memories from the transcript.

---

### `substrate_report`
Get substrate health and statistics report.

**No parameters required.**

**Returns:** Memory counts, session counts, top projects, memory ages.

---

## Memory (4 tools)

### `memory_add`
Add a memory to the cognitive substrate.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | — | Memory content |
| `memory_type` | string | No | `"fact"` | Type: fact, preference, decision, pattern, context, lesson |
| `scope` | string | No | `"private"` | Scope: private, project, shared |
| `project` | string | No | — | Project name |
| `tags` | string[] | No | — | Tags |
| `context` | string | No | — | Additional context |

**Returns:** Created memory entry.

---

### `memory_search`
Search memories with filters.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | — | Search query |
| `memory_type` | string | No | — | Filter by type |
| `project` | string | No | — | Filter by project |
| `scope` | string | No | — | Filter by scope |
| `tags` | string[] | No | — | Filter by tags |
| `limit` | integer | No | `20` | Max results |

**Returns:** Matching memories with relevance scores.

---

### `memory_get_context`
Get relevant context memories for a query.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | — | Query |
| `project` | string | No | — | Project name |

**Returns:** Relevant context memories.

---

### `memory_decay`
Apply aging/decay to all memories.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `factor` | number | No | `0.95` | Decay factor |

**Returns:** Number of memories affected.

---

## Trust Engine (4 tools)

### `trust_check`
Check if an operation requires approval.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | string | Yes | — | Tool name |
| `operation` | string | No | — | Operation |
| `project` | string | No | — | Project name |

**Returns:** Whether approval is required and trust level.

---

### `trust_record`
Record an approval, denial, or violation.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | Yes | — | Action: approval, denial, violation |
| `tool_name` | string | Yes | — | Tool name |
| `operation` | string | No | — | Operation |
| `context` | string | No | — | Context |
| `project` | string | No | — | Project name |
| `reason` | string | No | — | Reason |

**Returns:** Recorded trust event.

---

### `trust_get`
Get trust record for a tool.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | string | Yes | — | Tool name |
| `context` | string | No | — | Context |
| `project` | string | No | — | Project name |

**Returns:** Trust record for the specified tool.

---

### `trust_summary`
Get trust summary for all tools or a project.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | No | — | Project name |

**Returns:** Trust summary across tools.

---

## Decision Ledger (3 tools)

### `ledger_record`
Record a decision in the ledger.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_used` | string | Yes | — | Tool used |
| `alternatives` | string[] | No | — | Alternatives considered |
| `reasoning` | string | No | — | Reasoning |
| `context` | string | No | — | Context |
| `project` | string | No | — | Project name |
| `session_id` | string | No | — | Session ID |
| `tags` | string[] | No | — | Tags |

**Returns:** Decision ID and recorded entry.

---

### `ledger_outcome`
Record outcome for a decision.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `decision_id` | string | Yes | — | Decision ID |
| `outcome` | string | Yes | — | Outcome description |
| `success` | boolean | No | — | Success flag |

**Returns:** Updated decision record with outcome.

---

### `ledger_find_similar`
Find similar past decisions.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Context query |
| `project` | string | No | — | Project name |
| `limit` | integer | No | `5` | Max results |

**Returns:** Similar past decisions.

---

## Teleportation (2 tools)

### `teleport_create_bundle`
Create a teleport bundle for state transfer.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source_host` | string | No | — | Source host |
| `target_host` | string | No | — | Target host |
| `pending_tasks` | string[] | No | — | Pending tasks |
| `last_action` | string | No | — | Last action |
| `model_name` | string | No | — | Model name |
| `tool_claims` | string[] | No | — | Tool claims |

**Returns:** JSON bundle containing full agent state.

---

### `teleport_rehydrate`
Rehydrate substrate state from a bundle.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bundle_json` | string | Yes | — | Bundle JSON string |

**Returns:** Rehydration result with imported data summary.

---

## Swarm (1 tool)

### `swarm_compile_intent`
Compile natural language intent into a swarm plan.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | string | Yes | — | Natural language intent |
| `project` | string | No | — | Project name |

**Returns:** Multi-agent execution plan.
