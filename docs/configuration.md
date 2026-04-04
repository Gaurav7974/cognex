# Configuration Guide

## MCP Server Configuration

Cognex runs as an MCP (Model Context Protocol) server. Configure it in your AI tool's MCP config file.

### OpenCode

**Config location:** `%USERPROFILE%\.config\opencode\opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cognex": {
      "type": "local",
      "command": ["cognex"],
      "enabled": true
    }
  }
}
```

### Claude Code / Claude Desktop

**Config location (Windows):** `%APPDATA%\Claude\claude_desktop_config.json`
**Config location (Mac):** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cognex": {
      "command": "cognex"
    }
  }
}
```

### Cursor

**Config location (Windows):** `%USERPROFILE%\.cursor\mcp.json`
**Config location (Mac):** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "cognex": {
      "command": "cognex"
    }
  }
}
```

### Development Mode (from source)

When working on the codebase directly:

```json
{
  "mcpServers": {
    "cognex": {
      "command": "python",
      "args": ["-m", "substrate_mcp.server"],
      "cwd": "/path/to/cognex",
      "env": {"PYTHONPATH": "/path/to/cognex/src"}
    }
  }
}
```

---

## Tool Configuration Reference

### Session Tools

#### `substrate_start_session`
- **Required:** `session_id` (string)
- **Optional:** `project` (string, default: "")
- **Purpose:** Initialize a work session and load relevant memories

#### `substrate_end_session`
- **Required:** none
- **Optional:** `summary`, `key_decisions` (array), `tools_used` (array), `errors` (array), `input_tokens` (int), `output_tokens` (int)
- **Purpose:** Save session snapshot and extract final memories

#### `substrate_process_transcript`
- **Required:** `transcript` (string)
- **Optional:** `session_id`, `project`, `context`
- **Purpose:** Automatically extract memories from conversation text

#### `substrate_report`
- **Required:** none
- **Purpose:** Get health statistics about the substrate (memory counts, sessions, etc.)

---

### Memory Tools

#### `memory_add`
- **Required:** `content` (string)
- **Optional:** `memory_type` (fact|preference|decision|pattern|context|lesson, default: "fact"), `scope` (private|project|shared, default: "private"), `project`, `tags` (array), `context`
- **Purpose:** Manually add a memory entry

#### `memory_search`
- **Required:** none
- **Optional:** `query`, `memory_type`, `project`, `scope`, `tags` (array), `limit` (int, default: 20)
- **Purpose:** Search memories with filters

#### `memory_get_context`
- **Required:** none
- **Optional:** `query`, `project`
- **Purpose:** Get relevant context memories for current work

#### `memory_decay`
- **Required:** none
- **Optional:** `factor` (float, default: 0.95)
- **Purpose:** Age all memories — faded ones are auto-deleted

---

### Trust Tools

#### `trust_check`
- **Required:** `tool_name` (string)
- **Optional:** `operation`, `project`
- **Purpose:** Check if a tool operation needs user approval

#### `trust_record`
- **Required:** `action` (approval|denial|violation), `tool_name` (string)
- **Optional:** `operation`, `context`, `project`, `reason`
- **Purpose:** Record user's response to a tool approval request

#### `trust_get`
- **Required:** `tool_name` (string)
- **Optional:** `context`, `project`
- **Purpose:** Get trust record for a specific tool

#### `trust_summary`
- **Required:** none
- **Optional:** `project`
- **Purpose:** Get trust overview for all tools or a specific project

---

### Ledger Tools

#### `ledger_record`
- **Required:** `tool_used` (string)
- **Optional:** `alternatives` (array), `reasoning`, `context`, `project`, `session_id`, `tags` (array)
- **Purpose:** Record an architectural or implementation decision

#### `ledger_outcome`
- **Required:** `decision_id` (string), `outcome` (string)
- **Optional:** `success` (boolean)
- **Purpose:** Record what happened after a decision was made

#### `ledger_find_similar`
- **Required:** `query` (string)
- **Optional:** `project`, `limit` (int, default: 5)
- **Purpose:** Find past decisions similar to current situation

---

### Teleport Tools

#### `teleport_create_bundle`
- **Required:** none
- **Optional:** `source_host`, `target_host`, `pending_tasks` (array), `last_action`, `model_name`, `tool_claims` (array)
- **Purpose:** Export full agent state as a JSON bundle for transfer

#### `teleport_rehydrate`
- **Required:** `bundle_json` (string)
- **Purpose:** Import agent state from a teleport bundle

---

### Swarm Tools

#### `swarm_compile_intent`
- **Required:** `intent` (string)
- **Optional:** `project`
- **Purpose:** Turn natural language intent into a multi-agent execution plan

---

## Data Storage

All data is stored locally in SQLite:

```
~/.cognex/
└── cognex.db
```

The database uses WAL (Write-Ahead Logging) mode for safe concurrent access from multiple AI tools.

## Environment Variables

No environment variables are required. The database path defaults to `~/.cognex/cognex.db`.
