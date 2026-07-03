# Tools Reference

> For practical usage examples and copy-paste prompts, see [Usage Guide](guides.md).

Cognex provides **41 MCP tools**.

---

## Session & Arcs (6 tools)

### `cognex_start_session`
Start a new session in the cognex engine and return relevant memories. Use when: beginning a new work session, task, or conversation. This initializes session tracking and retrieves context from past sessions.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | Unique session identifier |
| `project` | string | No | `""` | Project name |

### `cognex_end_session`
End the current session with summary and metrics. Use when: finishing a work session, task, or conversation. This saves session insights, records key decisions, and tracks performance metrics.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `summary` | string | No | — | Session summary |
| `key_decisions` | string[] | No | — | Key decisions made |
| `tools_used` | string[] | No | — | Tools used |
| `errors` | string[] | No | — | Errors encountered |
| `input_tokens` | integer | No | `0` | Input token count |
| `output_tokens` | integer | No | `0` | Output token count |

### `cognex_process_transcript`
Extract memories from a conversation transcript. Use when: reviewing past conversations to capture important insights, decisions, or preferences mentioned by the user that should be remembered for future sessions.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `transcript` | string | Yes | — | Conversation text |
| `session_id` | string | No | — | Session ID |
| `project` | string | No | — | Project name |
| `context` | string | No | — | Additional context |

### `arc_start`
Start or retrieve the active session arc for a project.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — | Project name |

### `arc_close`
Close an active session arc and generate its narrative summary.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `arc_id` | string | Yes | — | The unique arc ID to close |

### `arc_get_context`
Get the active session arc narrative for a project.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — | Project name |

---

## Memory & Retrieval (3 tools)

### `memory_add`
Add a memory to the cognex engine. Use when: user says 'remember', wants to save a preference, preference, decision, insight, pattern, or any knowledge they want preserved across sessions. Memories are searchable and persistent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | — | Memory content |
| `memory_type` | string | No | `"fact"` | Type: fact, preference, decision, pattern, context, lesson |
| `scope` | string | No | `"private"` | Scope: private, project, shared |
| `project` | string | No | — | Project name |
| `tags` | string[] | No | — | Tags |
| `context` | string | No | — | Additional context |

### `memory_decay`
Apply aging/decay to all memories. Use when: cleaning up old memories, maintaining database health, or ensuring older information decays in relevance while newer information remains prominent.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `factor` | number | No | `0.95` | Decay factor |

### `memory_consolidate`
Consolidate episodic memories into semantic clusters and promote stable ones to schemas.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | No | `""` | Filter to specific project |
| `min_cluster_size` | integer | No | `5` | Minimum count of similar episodic memories to form a cluster |

---

## Trust & Audit (4 tools)

### `trust_check`
Check if an operation requires approval. Use when: planning to execute a potentially sensitive tool (delete, update, deploy), checking if the operation has already been approved based on trust history.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | string | Yes | — | Tool name |
| `operation` | string | No | — | Operation |
| `project` | string | No | — | Project name |

### `trust_record`
Record an approval, denial, or violation. Use when: user approves/denies a tool operation (approval/denial), or to flag security violations. Builds trust history to inform future approvals.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | Yes | — | Action: approval, denial, violation |
| `tool_name` | string | Yes | — | Tool name |
| `operation` | string | No | — | Operation |
| `context` | string | No | — | Context |
| `project` | string | No | — | Project name |
| `reason` | string | No | — | Reason |

### `audit_get_recent`
Get recent audit log entries for a project. Returns list of audit events with timestamps.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — | Project name to filter by |
| `limit` | integer | No | `50` | Max number of entries to return |

### `audit_verify_chain`
Walk the full audit log hash chain and verify every link. Detects tampering (deletion or modification of any log entry) because any change breaks all subsequent checksums. Use after suspected tampering, compliance audits, or periodic integrity checks.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | No | `""` | Optional project filter.  Empty = check all projects. |
| `limit` | integer | No | `200` | Maximum entries to scan (1-10000) |

---

## Decision Ledger & Patterns (4 tools)

### `ledger_record`
Record a decision in the ledger. Use when: making a significant technical decision (e.g., 'FastAPI vs Flask', 'SQL vs NoSQL'). Tracks the decision, alternatives considered, reasoning, and outcome for future reference.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_used` | string | Yes | — | Tool used |
| `alternatives` | string[] | No | — | Alternatives considered |
| `reasoning` | string | No | — | Reasoning |
| `context` | string | No | — | Context |
| `project` | string | No | — | Project name |
| `session_id` | string | No | — | Session ID |
| `tags` | string[] | No | — | Tags |

### `ledger_outcome`
Record outcome for a decision. Use when: a decision you previously logged has been executed and you want to capture results. Connects decision to outcome for pattern learning and retrospectives.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `decision_id` | string | Yes | — | Decision ID |
| `outcome` | string | Yes | — | Outcome description |
| `success` | boolean | No | — | Success flag |

### `pattern_analyze`
Analyze decision history and discover behavioral patterns. Use when: looking for trends in past decisions (e.g., 'when do I fail', 'which tools succeed most'). Saves patterns as memories.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | No | — | Project name to filter analysis |
| `save_patterns` | boolean | No | `true` | Whether to save discovered patterns as memories |

### `pattern_stats`
Get statistics about decision history. Use when: checking if enough data exists for pattern analysis, or reviewing decision counts by tool/outcome.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | No | — | Project name to filter stats |

---

## State Units & Provenance (5 tools)

### `unit_commit`
Create a Cognitive Unit capturing decision/constraint/progress state. Use when: documenting a structured decision, constraint, or progress checkpoint. Stores what was decided, why, scope, and confidence level.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | — | The what - what was decided/done |
| `rationale` | string | No | — | The why - reasoning behind |
| `unit_type` | string | No | `"decision"` | Type: decision, constraint, progress, task_state |
| `scope` | string | No | — | Project/module/subsystem scope |
| `confidence` | number | No | `1.0` | Confidence 0.0-1.0 |
| `tags` | string[] | No | — | Tags |
| `project` | string | No | — | Project name |

### `unit_checkout`
Get cognitive bundle (decisions, constraints, progress) for a project. Use when: preparing to work on a task or retrieving full state snapshot for a scope. Returns structured JSON for handoff.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — | Project name |
| `scope` | string | No | — | Scope filter (optional) |
| `unit_type_filter` | string | No | — | Filter by unit_type |

### `unit_mark_overridden`
Mark a unit as contradicted - decays confidence by 0.2

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | string | Yes | — | Unit ID |

### `unit_verify`
Confirm a unit still holds - updates last_verified

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | string | Yes | — | Unit ID |

### `unit_decay_stale`
Mark stale units as overridden and decay their confidence

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — | Project name |
| `threshold` | number | No | `0.8` | Staleness threshold |

---

## Sync & State Transfer (4 tools)

### `teleport_create_bundle`
Create teleport bundle for state transfer between sessions. Use when: transferring full agent state to another machine or session. Captures pending tasks, tool claims, and context.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source_host` | string | No | — | Source host |
| `target_host` | string | No | — | Target host |
| `pending_tasks` | string[] | No | — | Pending tasks |
| `last_action` | string | No | — | Last action |
| `model_name` | string | No | — | Model name |
| `tool_claims` | string[] | No | — | Tool claims |

### `teleport_rehydrate`
Rehydrate engine state from a teleport bundle. Use when: restoring agent state from a bundle created on another machine. Reverses teleport_create_bundle to resume work.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bundle_json` | string | Yes | — | Bundle JSON string |

### `sync_push`
Push local cognex changes (memories, decisions, cognitive units) to a peer sync server.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `peer_host` | string | Yes | — | The IP or hostname of the remote peer to connect to. |
| `peer_port` | integer | No | `7474` | The TCP port of the remote peer's sync server. |

### `sync_pull`
Pull remote cognex changes (memories, decisions, cognitive units) from a peer sync server and merge them.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `peer_host` | string | Yes | — | The IP or hostname of the remote peer to connect to. |
| `peer_port` | integer | No | `7474` | The TCP port of the remote peer's sync server. |

---

## Health (1 tools)

### `cognex_health`
Return a health snapshot of all Cognex engine components. Checks: initialization status, database reachability, FTS5 availability, memory count, and uptime. Use at session start to confirm the engine is operational.

**No parameters required.**

---

## Other (14 tools)

### `cognex_report`
Get cognex health and statistics report. Use when: checking memory bank status, monitoring database health, or verifying how many memories and decisions have been stored.

**No parameters required.**

### `swarm_compile_intent`
Compile natural language intent into a swarm plan. Use when: translating a high-level goal into a structured execution plan for agent swarms. Returns actionable task breakdown.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | string | Yes | — | Natural language intent |
| `project` | string | No | — | Project name |

### `trust_query`
Consolidated trust query for checking approval posture or retrieving trust summaries.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tool_name` | string | No | — |  |
| `operation` | string | No | — |  |
| `project` | string | No | — |  |
| `mode` | string | No | `"check"` |  |

### `trust_manage`
Consolidated trust mutation for recording approvals, denials, and violations.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | Yes | — |  |
| `tool_name` | string | Yes | — |  |
| `operation` | string | No | — |  |
| `context` | string | No | — |  |
| `project` | string | No | — |  |
| `reason` | string | No | — |  |

### `recall`
Consolidated retrieval across memories, cognitive units, and decisions with compact or full detail.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | — |  |
| `kind` | string | No | `"all"` |  |
| `detail` | string | No | `"compact"` |  |
| `filters` | object | No | — |  |
| `limit` | integer | No | `10` |  |

### `provenance_trace`
Trace origins or impacts through the provenance DAG using compact id/gist nodes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `node_or_ref_id` | string | Yes | — |  |
| `direction` | string | No | `"origins"` |  |
| `depth` | integer | No | `3` |  |

### `provenance_link`
Explicitly link two provenance nodes or source row refs with a typed edge.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from_ref` | string | Yes | — |  |
| `to_ref` | string | Yes | — |  |
| `edge_type` | string | Yes | — |  |
| `rationale` | string | No | — |  |

### `question_raise`
Record an explicit open question for a project or scope.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | — |  |
| `project` | string | No | — |  |
| `scope` | string | No | — |  |

### `question_resolve`
Resolve an open question and connect it to an answer reference in provenance.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `question_id` | string | Yes | — |  |
| `answer_ref` | string | Yes | — |  |

### `integrity_verify`
Compute and Ed25519-sign the current project Merkle root, optionally checking selected refs.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — |  |
| `ref_ids` | string[] | No | — |  |

### `handoff_create`
Create the default signed manifest handoff with compact ids, gists, open questions, counterfactuals, and Merkle root.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | Yes | — |  |
| `goal_stack` | string[] | Yes | — |  |
| `in_flight_ops` | string[] | No | — |  |
| `notes` | string | No | — |  |
| `prior_baseline` | string | No | — |  |

### `handoff_resume`
Verify a signed handoff manifest and return a compact resume briefing.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `manifest_json` | string | Yes | — |  |

### `reconcile_resolve`
Resolve a recorded reconciliation conflict with a rationale and audit event.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `conflict_id` | string | Yes | — |  |
| `resolution` | string | Yes | — |  |
| `rationale` | string | Yes | — |  |

### `note_reasoning`
Low-friction write-ahead reasoning note that records a decision, assumption, rejection, constraint, or question.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `kind` | string | Yes | — |  |
| `content` | string | Yes | — |  |
| `refs` | string[] | No | — |  |
| `project` | string | No | — |  |

