# Cognex

> Your AI forgets everything. Cognex doesn't.

Give your AI coding assistant persistent memory, decision tracking, trust management, and now — structured cognitive state that survives across sessions and agents.

[![PyPI version](https://badge.fury.io/py/cognex.svg)](https://pypi.org/project/cognex/)
[![Version](https://img.shields.io/badge/version-0.1.6-blue.svg)](https://pypi.org/project/cognex/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/cognex?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/cognex)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

---

## Why Use It?

```
You: "Remember I prefer pytest over unittest"

Next session:
AI: "Got it — I'll use pytest as we discussed."
```

Your AI forgets everything between sessions. **Cognex** fixes that — and in v0.1.6, it does it with full structured cognitive state tracking.

---

## What's New in v0.1.6

- **Cognitive Units:** First-class structured state with content, rationale, scope, and confidence
- **Delta Tracking:** Append-only change log per unit — full audit trail of how cognition evolved
- **Staleness Scoring:** Computed on read from override count, last verified age, and confidence
- **Selective Retrieval:** get_relevant_units() scores by BM25 + confidence + recency + scope match
- **Cognitive Snapshot:** export_snapshot() returns full structured CHP handoff bundle with delta trail
- **8 New MCP Tools:** unit_commit, unit_checkout, unit_search, unit_mark_overridden, unit_verify, unit_get_relevant, unit_export_snapshot, unit_decay_stale
- **TeleportBundle Enhancement:** Now carries cognitive_units for full cross-machine cognitive state transfer
- **CLI Fix:** cognex --status now working (was reported done in 0.1.5 but not implemented until now)

---

## Features

| Feature | What It Does |
|---------|-------------|
| **Persistent Memory** | Remembers preferences, facts, patterns across sessions |
| **Decision Ledger** | Tracks choices made and their outcomes |
| **Trust Engine** | Learns which tools you approve vs deny |
| **Teleportation** | Export your cognitive state, load it on another machine — now Ed25519 signed |
| **Pattern Intelligence** | Discovers behavioral patterns from decision history |
| **Swarm Mode** | Turn natural language into multi-agent plans |
| **MCP Prompts** | 5 built-in prompts for common workflows |
| **Auto-Installer** | One command setup for 7+ AI platforms |

---

## Quick Install

### Option A — Auto-installer (Recommended)

```bash
uvx cognex --install
```

Detects your AI tool (Claude Code, OpenCode, Cursor, VS Code, etc.) and writes the correct config automatically.

### Option B — One command (Terminal)

**Mac/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/Gaurav7974/cognex/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/Gaurav7974/cognex/main/install.ps1 | iex
```

### Option C — Paste this into your AI agent

```
Install and configure the cognex MCP server on my system.

Steps:
1. Run: pip install cognex
2. Detect which AI tool I am using (Claude Code / OpenCode / Cursor / Codex / VS Code)
3. Find the correct MCP config file for this tool
4. Add cognex to the config:
   - command: "cognex"
   - no extra args needed
5. Tell me to restart my AI tool
6. After I restart, call substrate_start_session with session_id "setup-verify" to confirm it works
```

### Option D — Manual

See the [Configuration](#configuration-by-ai-tool) section below.

---

## Check Your Status

New in v0.1.5 — inspect your memory bank without starting the server:

```bash
cognex --status
```

Output:
```
Cognex v0.1.5
─────────────────────────
Memories:       142
Decisions:       38
Trust records:   21
DB path:        .substrate/substrate.db

Configured tools:
  ✓ Claude Code
  ✓ OpenCode
```

---

## Supported AI Tools

| Tool | Works? |
|------|--------|
| Claude Code | ✅ |
| Claude Desktop | ✅ |
| OpenCode | ✅ |
| Cursor | ✅ |
| Codex | ✅ |
| VS Code (Copilot) | ✅ |
| Cline | ✅ |
| Windsurf | ✅ |
| Zed | ✅ |
| Any MCP-compatible tool | ✅ |

---

## Installation

### Option 1: uvx (Recommended — no install needed)

```bash
uvx cognex
```

### Option 2: pipx (isolated environment)

```bash
pipx install cognex
```

### Option 3: pip

```bash
pip install cognex
```

### Option 4: From source

```bash
git clone https://github.com/Gaurav7974/cognex
cd cognex
pip install -e .
```

### Verify

```bash
cognex --help
cognex --status
```

---

## Configuration by AI Tool

### Claude Code

```bash
claude mcp add cognex -- uvx cognex
```

Or manually in `~/.claude.json` or `.mcp.json`:
```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
```

---

### Claude Desktop

Config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
```

---

### OpenCode

Config file: `~/.config/opencode/opencode.json` or `opencode.json` in project root

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cognex": {
      "type": "local",
      "command": ["uvx", "cognex"],
      "enabled": true
    }
  }
}
```

Note: OpenCode uses `"mcp"` not `"mcpServers"`, and requires `"type": "local"`.

---

### Cursor

Config: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
```

Note: Cursor caps at 40 tools. Cognex uses 20, well within limit.

---

### VS Code (GitHub Copilot Agent Mode)

Config: `.vscode/mcp.json` in workspace, or Command Palette → `MCP: Open User Configuration`

```json
{
  "servers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
```

Note: VS Code uses `"servers"` not `"mcpServers"`.

---

### Cline

Open Cline → MCP Servers → Configure tab → Edit Config:

```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"],
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

---

### Windsurf

Config: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
```

---

### Zed

Config: `~/.config/zed/settings.json`

```json
{
  "context_servers": {
    "cognex": {
      "command": {
        "path": "uvx",
        "args": ["cognex"]
      }
    }
  }
}
```

---

## Config Format Reference

| Tool | Key | Config file |
|------|-----|-------------|
| Claude Code | mcpServers | `~/.claude.json` or `.mcp.json` |
| Claude Desktop | mcpServers | `claude_desktop_config.json` |
| OpenCode | mcp | `opencode.json` |
| Cursor | mcpServers | `~/.cursor/mcp.json` |
| VS Code Copilot | servers | `.vscode/mcp.json` |
| Cline | mcpServers | `cline_mcp_settings.json` |
| Windsurf | mcpServers | `mcp_config.json` |
| Zed | context_servers | `settings.json` |

---

## After Adding Config

Completely close and reopen your AI tool. You should see 20 new Cognex tools available.

Verify in Claude Code:
```
/mcp
→ cognex: connected
```

Verify in OpenCode:
```
/mcp
→ cognex: Connected
```

---

## The 20 Tools

### Session Management
| Tool | Description |
|------|-------------|
| `substrate_start_session` | Start a new work session |
| `substrate_end_session` | End session with summary and metrics |
| `substrate_process_transcript` | Extract memories from conversation |
| `substrate_report` | Get memory health report |

### Memory
| Tool | Description |
|------|-------------|
| `memory_add` | Add a memory (fact, preference, decision, pattern) |
| `memory_search` | Search memories with filters |
| `memory_get_context` | Get relevant context for current work |
| `memory_decay` | Age memories and clean up old ones |

### Trust Engine
| Tool | Description |
|------|-------------|
| `trust_check` | Check if a tool operation needs approval |
| `trust_record` | Record approval, denial, or violation |
| `trust_get` | Get trust score for a tool |
| `trust_summary` | Get trust overview across all tools |

### Decision Ledger
| Tool | Description |
|------|-------------|
| `ledger_record` | Record a decision made |
| `ledger_outcome` | Record what happened after the decision |
| `ledger_find_similar` | Find similar past decisions |

### Teleportation
| Tool | Description |
|------|-------------|
| `teleport_create_bundle` | Export cognitive state to a signed JSON bundle |
| `teleport_rehydrate` | Import cognitive state from a bundle |

### Swarm
| Tool | Description |
|------|-------------|
| `swarm_compile_intent` | Turn natural language into a multi-agent plan |

### Pattern Intelligence
| Tool | Description |
|------|-------------|
| `pattern_analyze` | Discover behavioral patterns from decision history |
| `pattern_stats` | Check if enough data exists for pattern analysis |

---

## MCP Prompts

| Prompt | Description |
|--------|-------------|
| `cognex://start-session` | Initialize session with relevant memories |
| `cognex://end-session` | Generate session summary and save insights |
| `cognex://context-for-task` | Load context for a specific task |
| `cognex://remember` | Save important information to memory |
| `cognex://weekly-summary` | Get weekly activity and decision summary |

---

## Example Usage

### Remember a Preference
```
You: "I prefer using type hints everywhere"
AI:  (calls memory_add)
→   Saved to your memory bank
```

### Pick Up Where You Left Off
```
You: (start new session)
AI:  (calls memory_get_context with "current project")
→   Returns decisions, preferences, and progress from last session
AI:  "Continuing from where we left off — you were building the auth module."
```

### Track a Decision
```
You: "FastAPI or Flask?"
AI:  "FastAPI has better type safety for your use case."
AI:  (calls ledger_record)

Later...
You: "Did that work out?"
AI:  (calls ledger_outcome — success: true)
```

### Teleport Your Brain to Another Machine
```bash
# On machine A
cognex teleport export → generates bundle.json (Ed25519 signed)

# On machine B
cognex teleport import bundle.json → full state restored, signature verified
```

---

## Where Data Lives

All data stays local in SQLite under `.substrate/` in your project directory:

```
.substrate/
├── substrate.db   — memories, sessions, cognitive units
├── trust.db       — tool approval history
├── decisions.db   — decision ledger
└── signing_key.pem — Ed25519 private key (generated on first run, never leaves your machine)
```

---

## Troubleshooting

### "command not found"
```bash
pip install cognex
# or use uvx in your config — no install needed
```

### Tools not appearing
1. Completely close and reopen your AI tool (not just reload)
2. Check developer console for JSON parse errors
3. Validate your config JSON at jsonlint.com
4. Run `cognex --status` to confirm the DB is accessible

### Stale uvx cache
```bash
uvx cognex@latest  # force fetch latest version
```

---

## Development

```bash
git clone https://github.com/Gaurav7974/cognex
cd cognex
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Roadmap

- **v0.1.6** — Cognitive Units: structured decisions with rationale, scope, and confidence
- **v0.1.7** — Selective retrieval: load only what matters for the current task
- **v0.1.8** — Audited handoff protocol: full CHP compliance for multi-agent workflows
- **v0.2.0** — Persistent agent identity: agents that resume instantly with full cognitive context

---

## License

MIT — free to use, modify, and distribute.

---

## Need Help?

- Issues: https://github.com/Gaurav7974/cognex/issues
- PyPI: https://pypi.org/project/cognex/
- Docs: see `docs/` folder