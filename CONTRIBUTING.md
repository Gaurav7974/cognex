# Contributing to Cognex

Thank you for your interest in contributing! Cognex is an open-source persistent memory layer for AI agents. Whether it's a bug fix, new feature, documentation improvement, or a new MCP tool — your help is welcome.

---

## Reporting Issues

Before reporting, check [existing issues](https://github.com/Gaurav7974/cognex/issues) to avoid duplicates.

When reporting a bug, include:
- Python version (`python --version`)
- How you installed Cognex (pip, uvx, pipx, source)
- Steps to reproduce
- Expected vs actual behavior
- Any error messages or logs

For feature requests, describe the use case and why it would be valuable.

---

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Clone & Install

```bash
git clone https://github.com/Gaurav7974/cognex.git
cd cognex
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
cognex/
├── src/
│   ├── substrate/         # Core memory system (business logic)
│   └── substrate_mcp/     # MCP server (18 tools)
│       ├── server.py      # MCP server entry point
│       ├── tools/         # Individual tool implementations
│       └── installer.py   # Auto-installer CLI
├── tests/                 # Test suite
├── docs/                  # Documentation
├── evaluate/              # Benchmarks & evaluation
└── scripts/               # Install scripts (install.sh, install.ps1)
```

**Where to make changes:**
- New MCP tool → add to `src/substrate_mcp/tools/` and register in `tools/__init__.py`
- Core logic changes → `src/substrate/`
- Documentation → `docs/`
- Tests → `tests/`

---

## Adding a New MCP Tool

1. Implement the tool in the appropriate file under `src/substrate_mcp/tools/`
2. Register it in `src/substrate_mcp/tools/__init__.py`
3. Add tests in `tests/`
4. Document it in `docs/tools.md`
5. Verify it loads:
   ```bash
   python -c "from substrate_mcp.tools import list_all_tools; print(len(list_all_tools()), 'tools')"
   ```

---

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/
ruff format src/
```

---

## Test Logging

All test files use Python's standard `logging` module for output, not `print()` statements. This ensures consistent formatting, proper log levels, and cross-platform compatibility (especially on Windows with different encodings).

### Using Logging in Tests

Import the logger from the logger utility module:

```python
from substrate_mcp.logger import TEST_LOGGER

# Log a test result with a status
TEST_LOGGER.info("Test passed successfully")
TEST_LOGGER.error("Test failed with error: {error_message}")

# Log with ASCII-safe symbols (no Unicode to avoid encoding issues)
TEST_LOGGER.info("[PASS] substrate_start_session: session=123abc")
TEST_LOGGER.error("[FAIL] trust_record: database is locked")
```

### Logger Configuration

- **Format**: `"  %(levelname)-4s | %(message)s"` for clean, readable output
- **Log Levels**: Use `INFO` for passing tests, `ERROR` for failures
- **Symbols**: Use ASCII brackets `[PASS]`/`[FAIL]` instead of Unicode checkmarks/crosses to support Windows cp1252 encoding

See `src/substrate_mcp/logger.py` for implementation details.

---

## Submitting a Pull Request

1. [Fork](https://github.com/Gaurav7974/cognex/fork) and clone the repository
2. Create a branch: `git checkout -b fix/your-fix`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Run linter: `ruff check src/`
6. Commit with a descriptive message
7. Push and [open a PR](https://github.com/Gaurav7974/cognex/compare)

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

feat(db): add schema migrations for seamless upgrades
fix(server): handle empty project name in session start
docs: add practical usage guide with 14 scenarios
chore: add evaluate/results to gitignore
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `security`

### PR Guidelines

- Keep changes focused — one logical change per PR
- Include tests for new functionality
- Update documentation if the change affects user-facing behavior
- Reference related issues with `Fixes #123` or `Closes #456`

---

## Testing Your Changes Locally

To test with your AI tool (OpenCode, Claude Code, etc.), configure it to use your local source:

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

## Release Process (Maintainers Only)

1. Bump version in `pyproject.toml`
2. Update `CHANGELOG.md` with new release notes
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin main --tags`
6. GitHub Actions automatically publishes to PyPI

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
