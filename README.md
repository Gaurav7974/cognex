# 🧠 Cognex

**Persistent memory layer for AI agents — survives sessions, learns patterns, enables continuity.**

Give your AI coding assistant long-term memory, decision tracking, and trust management.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![MCP](https://img.shields.io/badge/MCP-1.0%2B-purple)
![Tests](https://img.shields.io/badge/tests-79%2F84%20passing-brightgreen)

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
| 🧠 **Persistent Memory** | Remembers preferences, facts, patterns across sessions |
| 📝 **Decision Ledger** | Tracks choices made and their outcomes |
| 🛡️ **Trust Engine** | Learns which tools you approve vs deny |
| 🔄 **Teleportation** | Export your brain, load it on another machine |
| 🐝 **Swarm Mode** | Turn natural language into multi-agent plans |

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

### Option 4: Install from this folder (development)

```bash
cd D:\COGNITIVE\cognitive-substrate
pip install -e .
```

---

## Configuration by CLI Tool

### OpenCode

**Config location:** `%USERPROFILE%\.config\opencode\opencode.json`

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

```
%USERPROFILE%\.cognex\
└── cognex.db
    ├── memories      (your persistent memories)
    ├── sessions      (session history)
    ├── trust_records (tool approval history)
    └── decisions     (decision ledger)
```

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
# Run tests
cd D:\COGNITIVE\cognitive-substrate
python tests/test_mcp_server.py

# Run pytest
python -m pytest tests/ -v -k "not mcp_server"

# Run demo
python demo/run_demo.py
```

---

## File Structure

```
D:\COGNITIVE\cognitive-substrate\
├── README.md              ← You are here!
├── mcp.json               ← MCP config ready to copy
├── pyproject.toml         ← Package config (name: cognex)
├── demo/
│   ├── run_demo.py        ← Simple demo
│   └── run_full_demo.py   ← Full workflow demo
├── src/
│   ├── substrate/         ← Core memory system
│   │   ├── substrate.py   ← Main orchestrator
│   │   ├── store.py       ← SQLite storage
│   │   ├── extractor.py   ← Memory extraction
│   │   ├── retriever.py   ← Memory retrieval
│   │   ├── ledger.py      ← Decision tracking
│   │   ├── trust.py       ← Trust engine
│   │   ├── teleport.py    ← State export/import
│   │   └── swarm.py       ← Multi-agent planning
│   └── substrate_mcp/     ← MCP server
│       ├── server.py      ← MCP server entry
│       └── tools/         ← 18 tool implementations
└── tests/
    ├── test_substrate.py  ← Core tests
    ├── test_layers.py     ← Layer tests
    └── test_mcp_server.py ← Tool tests
```

---

## License

MIT — free to use, modify, and distribute.

---

## Need Help?

- 📂 Source code: `D:\COGNITIVE\cognitive-substrate\src\`
- 🧪 Run tests: `python tests/test_mcp_server.py`
- 🔧 Tool implementations: `src\substrate_mcp\tools\`