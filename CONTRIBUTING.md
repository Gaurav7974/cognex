# Contributing to Cognex

## Setup

git clone https://github.com/YOUR_USERNAME/cognex
cd cognex
pip install -e ".[dev]"

## Running tests

pytest tests/ -v -k "not mcp_server"

## Testing your changes with OpenCode/Claude Code

Add to your MCP config:
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

## Making changes

- Business logic: src/substrate/
- MCP tools: src/substrate_mcp/tools/
- New tool: add to tools/__init__.py registry + implement in appropriate tools file
- Tests: tests/

## Submitting a PR

1. Fork the repo
2. Create a branch: git checkout -b fix/your-fix-name
3. Make changes
4. Run tests: pytest tests/ -v
5. Push and open a PR

## Release process (maintainers only)

1. Bump version in pyproject.toml
2. Update CHANGELOG.md
3. git tag v0.1.1
4. git push origin v0.1.1
5. GitHub Actions publishes to PyPI automatically
