#!/bin/sh
set -e

echo "Installing cognex..."
pip install cognex

echo "Detecting AI tool config..."

# Claude Code
CLAUDE_CONFIG="$HOME/.claude/settings.json"
# OpenCode  
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
# Cursor
CURSOR_CONFIG="$HOME/.cursor/mcp.json"

install_claude() {
    mkdir -p "$(dirname $CLAUDE_CONFIG)"
    if [ -f "$CLAUDE_CONFIG" ]; then
        echo "Found Claude config at $CLAUDE_CONFIG"
        echo "Add this to mcpServers in $CLAUDE_CONFIG:"
        echo '    "cognex": { "command": "cognex" }'
    else
        echo '{"mcpServers": {"cognex": {"command": "cognex"}}}' > "$CLAUDE_CONFIG"
        echo "Created Claude config at $CLAUDE_CONFIG"
    fi
}

install_opencode() {
    mkdir -p "$(dirname $OPENCODE_CONFIG)"
    if [ -f "$OPENCODE_CONFIG" ]; then
        echo "Found OpenCode config at $OPENCODE_CONFIG"
        echo "Add this to mcp in $OPENCODE_CONFIG:"
        echo '    "cognex": {"type": "local", "command": ["cognex"], "enabled": true}'
    else
        cat > "$OPENCODE_CONFIG" << 'EOF'
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
EOF
        echo "Created OpenCode config at $OPENCODE_CONFIG"
    fi
}

install_cursor() {
    mkdir -p "$(dirname $CURSOR_CONFIG)"
    if [ -f "$CURSOR_CONFIG" ]; then
        echo "Found Cursor config at $CURSOR_CONFIG"
        echo "Add this to mcpServers in $CURSOR_CONFIG:"
        echo '    "cognex": { "command": "cognex" }'
    else
        echo '{"mcpServers": {"cognex": {"command": "cognex"}}}' > "$CURSOR_CONFIG"
        echo "Created Cursor config at $CURSOR_CONFIG"
    fi
}

# Detect and install
if [ -d "$HOME/.claude" ] || [ -f "$CLAUDE_CONFIG" ]; then
    install_claude
elif [ -d "$HOME/.config/opencode" ] || [ -f "$OPENCODE_CONFIG" ]; then
    install_opencode
elif [ -d "$HOME/.cursor" ] || [ -f "$CURSOR_CONFIG" ]; then
    install_cursor
else
    echo "No AI tool detected. Installing cognex globally."
    echo "Add cognex to your MCP config manually."
    echo "See: https://github.com/Gaurav7974/cognex#configuration-by-cli-tool"
fi

echo ""
echo "Done! Restart your AI tool and you should see 18 new cognex tools."
echo "Docs: https://github.com/Gaurav7974/cognex"
