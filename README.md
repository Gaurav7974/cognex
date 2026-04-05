# Cognex

**Persistent memory layer for AI agents — survives sessions, learns patterns, enables continuity.**

Give your AI coding assistant long-term memory, decision tracking, and trust management. Benchmarked to reduce context tokens by ~70% compared to manual context pasting.

[![PyPI version](https://badge.fury.io/py/cognex.svg)](https://pypi.org/project/cognex/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

---

## Why Use It?

```
You: "Remember I prefer pytest over unittest"

Next session:
AI: "Got it — I'll use pytest for your tests instead."
```

Your AI forgets everything between sessions. **Cognex** fixes that.

### Features

| Feature | What It Does |
|---------|-------------|
| **Persistent Memory** | Remembers preferences, facts, patterns across sessions |
| **Decision Ledger** | Tracks choices made and their outcomes |
| **Trust Engine** | Learns which tools you approve vs deny |
| **Teleportation** | Export your brain, load it on another machine |
| **Swarm Mode** | Turn natural language into multi-agent plans |
| **MCP Prompts** | 5 built-in prompts for common workflows |
| **Auto-Installer** | One command setup for 7+ AI platforms |

---

## Quick Install

### Option A — Auto-installer (Recommended)

```bash
# Install and auto-configure for your AI tool
uvx cognex --install
```

This detects your AI tool (Claude Code, OpenCode, Cursor, VS Code, etc.) and writes the correct config automatically.

### Option B — One command (Terminal)

**Mac/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/Gaurav7974/cognex/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/Gaurav7974/cognex/main/install.ps1 | iex
```

These scripts automatically:
- Install cognex via pip
- Detect your AI tool (Claude Code, OpenCode, Cursor, Codex)
- Write the correct config file
- Print confirmation when done

---

### Option C — Paste this prompt into your AI agent

If you're already inside Claude Code, OpenCode, Cursor or any MCP-compatible tool,
just paste this prompt and your AI will configure everything:

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

Copy that prompt → paste into your AI tool → it handles the rest.

---

### Option D — Manual (full control)

See the [Configuration](#configuration-by-cli-tool) section below
for step-by-step setup per tool.

---

## Supported AI Tools

| Tool | Works? |
|------|--------|
| Claude Code | ✅ |
| Claude Desktop | ✅ |
| OpenCode | ✅ |
| Cursor | ✅ |
| Codex | ✅ |
| Any MCP-compatible tool | ✅ |

---

## Installation (Choose One)

### Option 1: uvx (Recommended — no install needed)

```bash
uvx cognex
```

### Option 2: pipx (isolated environment)

```bash
pipx install cognex
```

### Option 3: pip (system-wide install)

```bash
pip install cognex
```

### Option 4: Install from source (development)

```bash
git clone https://github.com/Gaurav7974/cognex
cd cognex
pip install -e .
```

### Verify Installation

After any install method above:

```bash
cognex --help
# Should show: usage: cognex [-h] [--db-path ...] [--project ...] [--name ...] [--debug] [--install]
```

---

## Configuration

### Claude Code

Config file: `~/.claude.json` (global) or `.mcp.json` (project root)

Add via CLI (recommended):
```bash
claude mcp add cognex -- uvx cognex
```

Or manually add to `~/.claude.json`:
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

Or add to `.mcp.json` in your project root (team-shared):
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

Note: `.mcp.json` in project root is version-controlled and shared with your team.
`~/.claude.json` is user-specific and works across all projects.

---

### Claude Desktop

Config file:
  Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  Mac:     `~/Library/Application Support/Claude/claude_desktop_config.json`
  Linux:   `~/.config/Claude/claude_desktop_config.json`

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

Config file: `~/.config/opencode/opencode.json` (global)
             `opencode.json` in project root (project-specific)

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

Note: OpenCode uses `"mcp"` key (not `"mcpServers"`) and requires `"type": "local"`
for stdio servers. Config files are merged, not replaced — safe to add to
existing config.

---

### Cursor

Config file:
  Windows: `%USERPROFILE%\.cursor\mcp.json`
  Mac/Linux: `~/.cursor/mcp.json`

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

Note: Cursor caps at 40 tools per config. Cognex uses 18 tools, well within limit.

---

### VS Code (GitHub Copilot Agent Mode)

Config file: `.vscode/mcp.json` in your workspace (team-shared)
             Or run: MCP: Open User Configuration from Command Palette (global)

Note: VS Code uses `"servers"` key not `"mcpServers"`

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

---

### Cline (VS Code Extension)

Config file: Managed via Cline UI
  Windows: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
  Mac: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

Open Cline → click MCP Servers icon → Configure tab → Edit Config

Add under mcpServers:
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

### Kilo Code (VS Code Extension)

Same format as Cline. Open Kilo Code → MCP Servers → Configure.

```json
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"],
      "disabled": false
    }
  }
}
```

---

### Windsurf

Config file: `~/.codeium/windsurf/mcp_config.json`

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

Config file: `~/.config/zed/settings.json`

Add under `context_servers` key:
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

## Config format reference

| Tool | Key | Config file |
|------|-----|-------------|
| Claude Code | mcpServers | `~/.claude.json` or `.mcp.json` |
| Claude Desktop | mcpServers | `claude_desktop_config.json` |
| OpenCode | mcp | `opencode.json` |
| Cursor | mcpServers | `~/.cursor/mcp.json` |
| VS Code Copilot | servers | `.vscode/mcp.json` |
| Cline | mcpServers | `cline_mcp_settings.json` |
| Kilo Code | mcpServers | `cline_mcp_settings.json` |
| Windsurf | mcpServers | `mcp_config.json` |
| Zed | context_servers | `settings.json` |

Key difference: OpenCode uses `"mcp"` and VS Code uses `"servers"`.
All others use `"mcpServers"`.

---

## After adding config

Completely close and reopen your AI tool.
You should see 18 new cognex tools available.

To verify in Claude Code:
```
/mcp
→ Should show: cognex: connected
```

To verify in OpenCode:
```
Type /mcp in the chat
→ Should show cognex listed with Connected status
```

---

## Restart Your AI Tool

After adding the config, **completely close and reopen** your AI tool. You should see 18 new tools available.

---

## The 18 Tools

### Session Management
| Tool | Description |
|------|-------------|
| `substrate_start_session` | Start a new work session |
| `substrate_end_session` | End session with summary/metrics |
| `substrate_process_transcript` | Extract memories from conversation |
| `substrate_report` | Get memory health report |

### Memory
| Tool | Description |
|------|-------------|
| `memory_add` | Add a memory (fact, preference, decision, pattern) |
| `memory_search` | Search memories with filters |
| `memory_get_context` | Get relevant context for current work |
| `memory_decay` | Age memories (auto-cleanup old ones) |

### Trust Engine
| Tool | Description |
|------|-------------|
| `trust_check` | Check if tool needs approval |
| `trust_record` | Record approval/denial/violation |
| `trust_get` | Get trust score for a tool |
| `trust_summary` | Get trust overview |

### Decision Ledger
| Tool | Description |
|------|-------------|
| `ledger_record` | Record a decision made |
| `ledger_outcome` | Record what happened after |
| `ledger_find_similar` | Find similar past decisions |

### Teleportation
| Tool | Description |
|------|-------------|
| `teleport_create_bundle` | Export your brain to JSON |
| `teleport_rehydrate` | Import brain from another machine |

### Swarm
| Tool | Description |
|------|-------------|
| `swarm_compile_intent` | Turn "build me an API" into a multi-agent plan |

---

## MCP Prompts

Cognex includes 5 built-in prompts accessible via MCP prompt protocol:

| Prompt | Description |
|--------|-------------|
| `cognex://start-session` | Initialize session with relevant memories |
| `cognex://end-session` | Generate session summary and save insights |
| `cognex://context-for-task` | Load context for a specific task |
| `cognex://remember` | Save important information to memory |
| `cognex://weekly-summary` | Get weekly activity and decision summary |

Use these in any MCP-compatible client that supports prompts.

---

## Example Usage

### Remember a Preference
```
You: "I prefer using type hints everywhere"
AI: (calls memory_add)
→ Saved to your memory bank
```

### Get Context Next Session
```
You: (start new session)
AI: (calls memory_get_context with "coding style")
→ Returns: "I prefer using type hints everywhere"
AI: "Got it — I'll add type hints throughout."
```

### Track a Decision
```
You: "FastAPI or Flask?"
AI: "FastAPI has better type safety."
AI: (calls ledger_record)

Later...
You: "Did that work out?"
AI: (calls ledger_outcome with success: true)
```

### Tool Trust Check
```
AI wants to run: rm -rf /
AI: (calls trust_check)
→ {requires_approval: true, trust_level: 0.2}
AI asks: "Can I delete everything?"
```

---

## Where Data is Stored

All data stays local on your machine in SQLite:

Linux/Mac:   `~/.cognex/cognex.db`
Windows:     `%USERPROFILE%\.cognex\cognex.db`

Contains:
- memories      — persistent memories
- sessions      — session history
- trust_records — tool approval history
- decisions     — decision ledger

---

## Troubleshooting

### "command not found" or "cognex" not recognized

**Fix:** Make sure you installed it:
```bash
pip install cognex
```
Or use uvx in your config:
```json
"command": ["uvx", "cognex"]
```

### Tools not appearing

1. Check the AI tool's developer console for errors
2. Try restarting the AI tool completely
3. Verify your JSON config is valid (use a JSON validator)

---

## Development

```bash
git clone https://github.com/Gaurav7974/cognex
cd cognex
pip install -e ".[dev]"
pytest tests/ -v
```

---

## File Structure

```
cognex/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── publish.yml
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── docs/
│   ├── configuration.md
│   ├── tools.md
│   └── examples.md
├── examples/
│   ├── basic_usage.py
│   ├── session_workflow.py
│   └── teleport_example.py
├── src/
│   ├── substrate/         ← Core memory system
│   └── substrate_mcp/     ← MCP server with 18 tools
├── tests/
│   ├── test_substrate.py
│   ├── test_layers.py
│   └── test_mcp_server.py
├── demo/
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── mcp.example.json       ← copy this to configure
└── pyproject.toml
```

---

## License

MIT — free to use, modify, and distribute.

---

## Need Help?

- Open an issue: https://github.com/Gaurav7974/cognex/issues
- PyPI page: https://pypi.org/project/cognex/
- Read the docs: see docs/ folder
