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
      "command": ["uvx", "cognex"],
      "enabled": true
    }
  }
}
```

### Claude Code

**Config location:** `~/.claude.json` or `.mcp.json`

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

### Claude Desktop

**Config location (Windows):** `%APPDATA%\Claude\claude_desktop_config.json`
**Config location (Mac):** `~/Library/Application Support/Claude/claude_desktop_config.json`

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

### Cursor

**Config location (Windows):** `%USERPROFILE%\.cursor\mcp.json`
**Config location (Mac):** `~/.cursor/mcp.json`

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

### VS Code (GitHub Copilot Agent Mode)

**Config location:** `.vscode/mcp.json` in workspace

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

### Development Mode (from source)

When working on the codebase directly, point directly to the python module:

```json
{
  "mcpServers": {
    "cognex": {
      "command": "python",
      "args": ["-m", "cognex_mcp.server"],
      "cwd": "/path/to/cognex",
      "env": {"PYTHONPATH": "/path/to/cognex/src"}
    }
  }
}
```

---

## Data Storage

All data is stored locally in SQLite:

```
~/.cognex.db/
└── cognex.db
```

The database uses WAL (Write-Ahead Logging) mode for safe concurrent access from multiple AI tools.

## Environment Variables

No environment variables are required. The database path defaults to `~/.cognex.db/cognex.db`.
