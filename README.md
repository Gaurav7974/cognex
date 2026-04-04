# 🧠 Cognex

**Persistent memory layer for AI agents — survives sessions, learns patterns, enables continuity.**

Give your AI coding assistant long-term memory, decision tracking, and trust management.

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

# Verify installation
```bash
uvx cognex --help
# Should show: usage: cognex [-h] [--db-path ...] [--project ...] [--name ...] [--debug]
```

### Option 2: pipx (isolated environment)

```bash
pipx install cognex
```

# Verify installation
```bash
uvx cognex --help
# Should show: usage: cognex [-h] [--db-path ...] [--project ...] [--name ...] [--debug]
```

### Option 3: pip (system-wide install)

```bash
pip install cognex
```

# Verify installation
```bash
uvx cognex --help
# Should show: usage: cognex [-h] [--db-path ...] [--project ...] [--name ...] [--debug]
```

### Option 4: Install from source (development)

```bash
git clone https://github.com/Gaurav7974/cognex
cd cognex
pip install -e .
```

# Verify installation
```bash
uvx cognex --help
# Should show: usage: cognex [-h] [--db-path ...] [--project ...] [--name ...] [--debug]
```

---

## Configuration by CLI Tool

### OpenCode

**Config location:** `~/.config/opencode/opencode.json` (Linux/Mac) or `%USERPROFILE%\.config\opencode\opencode.json` (Windows)

**With uvx (no install):**
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

**With pipx:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cognex": {
      "type": "local",
      "command": ["pipx", "run", "cognex"],
      "enabled": true
    }
  }
}
```

**With pip (simplest):**
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

---

### Claude Code / Claude Desktop

**Config location (Windows):** `%APPDATA%\Claude\claude_desktop_config.json`

**Config location (Mac):** `~/Library/Application Support/Claude/claude_desktop_config.json`

**With pip:**
```json
{
  "mcpServers": {
    "cognex": {
      "command": "cognex"
    }
  }
}
```

**With uvx:**
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

### Cursor

**Config location (Windows):** `%USERPROFILE%\.cursor\mcp.json`

**Config location (Mac):** `~/.cursor/mcp.json`

**With pip:**
```json
{
  "mcpServers": {
    "cognex": {
      "command": "cognex"
    }
  }
}
```

---

### VS Code (with MCP extension)

Create `.vscode/mcp.json` in your project:

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

### Codex

Add to your Codex config (`~/.codex/config.json`):

```json
{
  "mcpServers": {
    "cognex": {
      "command": "cognex"
    }
  }
}
```

---

## Restart Your AI Tool

After adding the config, **completely close and reopen** your AI tool. You should see 18 new tools available.

---

## The 18 Tools

### 🗓️ Session Management
| Tool | Description |
|------|-------------|
| `substrate_start_session` | Start a new work session |
| `substrate_end_session` | End session with summary/metrics |
| `substrate_process_transcript` | Extract memories from conversation |
| `substrate_report` | Get memory health report |

### 💾 Memory
| Tool | Description |
|------|-------------|
| `memory_add` | Add a memory (fact, preference, decision, pattern) |
| `memory_search` | Search memories with filters |
| `memory_get_context` | Get relevant context for current work |
| `memory_decay` | Age memories (auto-cleanup old ones) |

### 🛡️ Trust Engine
| Tool | Description |
|------|-------------|
| `trust_check` | Check if tool needs approval |
| `trust_record` | Record approval/denial/violation |
| `trust_get` | Get trust score for a tool |
| `trust_summary` | Get trust overview |

### 📖 Decision Ledger
| Tool | Description |
|------|-------------|
| `ledger_record` | Record a decision made |
| `ledger_outcome` | Record what happened after |
| `ledger_find_similar` | Find similar past decisions |

### 🚀 Teleportation
| Tool | Description |
|------|-------------|
| `teleport_create_bundle` | Export your brain to JSON |
| `teleport_rehydrate` | Import brain from another machine |

### 🐝 Swarm
| Tool | Description |
|------|-------------|
| `swarm_compile_intent` | Turn "build me an API" into a multi-agent plan |

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
