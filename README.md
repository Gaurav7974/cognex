# Cognex

> Your AI forgets everything. Cognex doesn't.

Give your AI coding assistant persistent memory, decision tracking, trust management, and structured state that survives across sessions and agents.

[![PyPI version](https://badge.fury.io/py/cognex.svg)](https://pypi.org/project/cognex/)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://pypi.org/project/cognex/)
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

Your AI forgets everything between sessions. **Cognex** fixes that — providing long-term memory, state replication, and synchronization across all your coding environments.

---

## What's New in v0.2.0

- **Three-Tier Memory Hierarchy:** Episodic memories consolidate into clusters (`memory_clusters`) and promote to behavioral schemas (`memory_schemas`).
- **Session Arc Abstraction:** Sessions within 7 days are grouped into arcs (`session_arcs`) with multi-session narrative summaries.
- **Peer-to-Peer Sync (`cognex_sync`):** Delta sync over TCP with `pull_and_merge` and `push`, using Ed25519 challenge-response auth for peer verification.
- **Hybrid Retrieval (RRF):** BM25 lexical search combined with semantic vector search via Reciprocal Rank Fusion.
- **Local Embeddings:** Offline `sentence-transformers` and `sqlite-vec` integration for lightning-fast semantic search.
- **Trust-Gated Conflict Resolution:** Last-writer-wins and confidence-weighted merge rules.
- **Outcome Feedback:** Retroactive memory relevance adjustment based on your ledger decision outcomes.
- **State Replication:** Explicit epistemic status on State Units, signed Merkle integrity roots, compact handoff manifests, and reconciliation conflict tracking.
- **Provenance Graph:** Origin and impact traces with `provenance_trace` and `provenance_link` tools.

---

## Features

| Feature | What It Does |
|---------|-------------|
| **Persistent Memory** | Remembers preferences, facts, and patterns across sessions |
| **Three-Tier Memory** | Consolidates single facts into behavioral schemas |
| **Decision Ledger** | Tracks choices made and their outcomes |
| **Trust Engine** | Learns which tools you approve vs deny |
| **State Transfer** | Export your state and load it on another machine (Ed25519 signed) |
| **P2P Sync** | Synchronize memories directly across machines over TCP |
| **Session Arcs** | Connects related sessions into long-running narratives |
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

---

## Check Your Status

Inspect your memory bank without starting the server:

```bash
cognex --status
```

Output:
```
Cognex v0.2.0
─────────────────────────
Memories:       142
Decisions:       38
Trust records:   21
DB path:        ~/.cognex.db/cognex.db

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

## Configuration by AI Tool

### Claude Code
```bash
claude mcp add cognex -- uvx cognex
```

### OpenCode
Config file: `~/.config/opencode/opencode.json`
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

---

## The Core Tools

The Cognex MCP server exposes dozens of tools for your AI. Here are the main categories:

### Session & Arcs
- `cognex_start_session`, `cognex_end_session`, `cognex_process_transcript`
- `arc_start`, `arc_close`, `arc_get_context`

### Memory & Retrieval
- `memory_add`, `memory_search`, `memory_get_context`, `memory_decay`
- `memory_consolidate`

### Trust & Audit
- `trust_check`, `trust_record`, `trust_get`, `trust_summary`
- `audit_get_recent`, `audit_verify`, `audit_verify_chain`

### Decision Ledger & Patterns
- `ledger_record`, `ledger_outcome`, `ledger_find_similar`
- `pattern_analyze`, `pattern_stats`

### State Units & Provenance
- `unit_commit`, `unit_checkout`, `unit_search`, `unit_mark_overridden`, `unit_verify`
- `unit_get_relevant`, `unit_export_snapshot`, `unit_decay_stale`

### Sync & State Transfer
- `sync_push`, `sync_pull`
- `teleport_create_bundle`, `teleport_rehydrate`
- `chp_transfer`, `chp_project`

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
AI:  (calls cognex_start_session and arc_get_context)
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

### Sync Across Machines
```bash
# On your work laptop: Start the TCP sync server
python -m cognex_sync.server

# On your personal desktop: Connect and pull the state
AI: (calls sync_pull)
```

---

## Where Data Lives

All data stays local in SQLite under the centralized `~/.cognex.db/` directory in your user home folder:

```
~/.cognex.db/
├── cognex.db     — unified database (memories, sessions, units, trust, ledger, logs)
└── keys/
    ├── signing_key.pem  — Ed25519 private key
    └── signing_key.pub  — Ed25519 public key
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

## License

MIT — free to use, modify, and distribute.

---

## Need Help?

- Issues: https://github.com/Gaurav7974/cognex/issues
- PyPI: https://pypi.org/project/cognex/