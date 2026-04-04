#!/bin/sh
set -e

echo "Installing cognex..."
pip install cognex

echo "Detecting AI tool configs..."

# Claude Code
CLAUDE_CONFIG="$HOME/.claude.json"
CLAUDE_DESKTOP_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
# OpenCode
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
# Cursor
CURSOR_CONFIG="$HOME/.cursor/mcp.json"
# Cline
CLINE_CONFIG="$HOME/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
# Zed
ZED_CONFIG="$HOME/.config/zed/settings.json"
# Windsurf
WINDSURF_CONFIG="$HOME/.codeium/windsurf/mcp_config.json"

configured=false

install_claude_code() {
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
    if [ -f "$CLAUDE_CONFIG" ]; then
        echo "Found Claude Code config at $CLAUDE_CONFIG"
        echo "Add cognex to mcpServers in $CLAUDE_CONFIG"
    else
        cat > "$CLAUDE_CONFIG" << 'EOF'
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
EOF
        echo "Created Claude Code config at $CLAUDE_CONFIG"
    fi
}

install_claude_desktop() {
    mkdir -p "$(dirname "$CLAUDE_DESKTOP_CONFIG")"
    if [ -f "$CLAUDE_DESKTOP_CONFIG" ]; then
        echo "Found Claude Desktop config at $CLAUDE_DESKTOP_CONFIG"
    else
        cat > "$CLAUDE_DESKTOP_CONFIG" << 'EOF'
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
EOF
        echo "Created Claude Desktop config at $CLAUDE_DESKTOP_CONFIG"
    fi
}

install_opencode() {
    mkdir -p "$(dirname "$OPENCODE_CONFIG")"
    if [ -f "$OPENCODE_CONFIG" ]; then
        echo "Found OpenCode config at $OPENCODE_CONFIG"
    else
        cat > "$OPENCODE_CONFIG" << 'EOF'
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
EOF
        echo "Created OpenCode config at $OPENCODE_CONFIG"
    fi
}

install_cursor() {
    mkdir -p "$(dirname "$CURSOR_CONFIG")"
    if [ -f "$CURSOR_CONFIG" ]; then
        echo "Found Cursor config at $CURSOR_CONFIG"
    else
        cat > "$CURSOR_CONFIG" << 'EOF'
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
EOF
        echo "Created Cursor config at $CURSOR_CONFIG"
    fi
}

install_cline() {
    mkdir -p "$(dirname "$CLINE_CONFIG")"
    if [ -f "$CLINE_CONFIG" ]; then
        echo "Found Cline config at $CLINE_CONFIG"
    else
        cat > "$CLINE_CONFIG" << 'EOF'
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
EOF
        echo "Created Cline config at $CLINE_CONFIG"
    fi
}

install_zed() {
    mkdir -p "$(dirname "$ZED_CONFIG")"
    if [ -f "$ZED_CONFIG" ]; then
        echo "Found Zed config at $ZED_CONFIG"
    else
        cat > "$ZED_CONFIG" << 'EOF'
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
EOF
        echo "Created Zed config at $ZED_CONFIG"
    fi
}

install_windsurf() {
    mkdir -p "$(dirname "$WINDSURF_CONFIG")"
    if [ -f "$WINDSURF_CONFIG" ]; then
        echo "Found Windsurf config at $WINDSURF_CONFIG"
    else
        cat > "$WINDSURF_CONFIG" << 'EOF'
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
EOF
        echo "Created Windsurf config at $WINDSURF_CONFIG"
    fi
}

# Detect and install all found tools
if [ -f "$CLAUDE_CONFIG" ] || [ -d "$HOME/.claude" ]; then
    install_claude_code
    configured=true
fi

if [ -d "$HOME/.config/Claude" ]; then
    install_claude_desktop
    configured=true
fi

if [ -d "$HOME/.config/opencode" ] || [ -f "$OPENCODE_CONFIG" ]; then
    install_opencode
    configured=true
fi

if [ -d "$HOME/.cursor" ] || [ -f "$CURSOR_CONFIG" ]; then
    install_cursor
    configured=true
fi

if [ -d "$HOME/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev" ]; then
    install_cline
    configured=true
fi

if [ -d "$HOME/.config/zed" ] || [ -f "$ZED_CONFIG" ]; then
    install_zed
    configured=true
fi

if [ -d "$HOME/.codeium/windsurf" ] || [ -f "$WINDSURF_CONFIG" ]; then
    install_windsurf
    configured=true
fi

if [ "$configured" = false ]; then
    echo "No AI tool detected. Installing cognex globally."
    echo "Add cognex to your MCP config manually."
    echo "See: https://github.com/Gaurav7974/cognex#configuration"
fi

echo ""
echo "Done! Restart your AI tool and you should see 18 new cognex tools."
echo "Docs: https://github.com/Gaurav7974/cognex"
