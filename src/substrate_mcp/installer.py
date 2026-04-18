"""Auto-installer for Cognex MCP across all AI coding tools."""

import datetime
import json
import os
import shutil
from pathlib import Path


def detect_command() -> str:
    """Detect whether to use uvx or direct command."""
    if shutil.which("uvx"):
        return "uvx"
    return "cognex"


PLATFORMS = {
    "claude-code": {
        "paths": [
            Path.home() / ".claude.json",
        ],
        "format": "claude_json",
        "display": "Claude Code",
    },
    "claude-desktop": {
        "paths": [
            Path(os.environ.get("APPDATA", ""))
            / "Claude"
            / "claude_desktop_config.json",
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json",
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        ],
        "format": "mcp_servers",
        "display": "Claude Desktop",
    },
    "opencode": {
        "paths": [
            Path.home() / ".config" / "opencode" / "opencode.json",
        ],
        "format": "opencode",
        "display": "OpenCode",
    },
    "cursor": {
        "paths": [
            Path.home() / ".cursor" / "mcp.json",
        ],
        "format": "mcp_servers",
        "display": "Cursor",
    },
    "vscode": {
        "paths": [
            Path.home() / ".vscode" / "mcp.json",
        ],
        "format": "vscode_servers",
        "display": "VS Code Copilot",
    },
    "cline": {
        "paths": [
            Path(os.environ.get("APPDATA", ""))
            / "Code"
            / "User"
            / "globalStorage"
            / "saoudrizwan.claude-dev"
            / "settings"
            / "cline_mcp_settings.json",
            Path.home()
            / "Library"
            / "Application Support"
            / "Code"
            / "User"
            / "globalStorage"
            / "saoudrizwan.claude-dev"
            / "settings"
            / "cline_mcp_settings.json",
        ],
        "format": "mcp_servers",
        "display": "Cline",
    },
    "windsurf": {
        "paths": [
            Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
        ],
        "format": "mcp_servers",
        "display": "Windsurf",
    },
}


def detect_installed_platforms() -> list[str]:
    """Find which AI tools are actually installed."""
    found = []
    for name, config in PLATFORMS.items():
        for path in config["paths"]:
            if path.exists() or path.parent.exists():
                found.append(name)
                break
    return found


def write_config(platform: str, dry_run: bool = False) -> bool:
    """Write Cognex config for a platform. Returns True if successful."""
    config = PLATFORMS[platform]
    cmd = detect_command()

    if cmd == "uvx":
        cognex_entry = {"command": "uvx", "args": ["cognex"]}
    else:
        cognex_entry = {"command": "cognex"}

    for path in config["paths"]:
        if path.parent.exists():
            # Read existing config
            existing: dict = {}
            if path.exists():
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}

                # Create .bak copy before modifying
                if not dry_run:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    bak_path = Path(str(path) + f".bak.{timestamp}")
                    try:
                        shutil.copy2(path, bak_path)
                    except Exception:
                        pass  # Backup creation is non-critical

            # Merge cognex in
            fmt = config["format"]
            if fmt == "mcp_servers":
                existing.setdefault("mcpServers", {})["cognex"] = cognex_entry
            elif fmt == "opencode":
                existing.setdefault("mcp", {})["cognex"] = {
                    "type": "local",
                    "command": ["uvx", "cognex"] if cmd == "uvx" else ["cognex"],
                    "enabled": True,
                }
                if "$schema" not in existing:
                    existing["$schema"] = "https://opencode.ai/config.json"
            elif fmt == "vscode_servers":
                existing.setdefault("servers", {})["cognex"] = cognex_entry
            elif fmt == "claude_json":
                existing.setdefault("mcpServers", {})["cognex"] = cognex_entry

            if dry_run:
                print(f"  [dry-run] Would write to {path}")
                # Show JSON diff of the change
                if fmt == "mcp_servers" or fmt == "claude_json":
                    diff_obj = {"mcpServers": {"cognex": cognex_entry}}
                elif fmt == "opencode":
                    diff_obj = {
                        "mcp": {
                            "cognex": {
                                "type": "local",
                                "command": ["uvx", "cognex"]
                                if cmd == "uvx"
                                else ["cognex"],
                                "enabled": True,
                            }
                        }
                    }
                elif fmt == "vscode_servers":
                    diff_obj = {"servers": {"cognex": cognex_entry}}
                else:
                    diff_obj = existing
                print(f"  {json.dumps(diff_obj, indent=2)}")
                return True

            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            print(f"  Configured {config['display']} at {path}")
            return True

    return False


def inject_agents_md(dry_run: bool = False) -> None:
    """Inject Cognex instructions into AGENTS.md or CLAUDE.md if present."""
    instruction = """<!-- cognex-agents v0.1.6 -->
## Cognex Memory (Auto-injected)
Cognex MCP is connected. Use it automatically:
- Session start: call substrate_start_session with project name
- When user says "remember": call memory_add
- When starting work: call memory_get_context to load context
- When user asks about past decisions: call ledger_find_similar
- Session end: call substrate_end_session with summary
- Never ask user to repeat context if it can be loaded from Cognex
"""
    for fname in ["AGENTS.md", "CLAUDE.md", ".cursorrules"]:
        p = Path(fname)
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if "Cognex Memory" not in content:
                if dry_run:
                    print(f"  [dry-run] Would inject Cognex instructions into {fname}")
                else:
                    p.write_text(content + instruction, encoding="utf-8")
                    print(f"  Injected Cognex instructions into {fname}")


def run_install(platform: str | None = None, dry_run: bool = False) -> None:
    """Main install function."""
    print("Cognex MCP Installer")
    print("=" * 40)

    if dry_run:
        print("DRY RUN - no changes will be made\n")

    if platform:
        platforms = [platform]
    else:
        platforms = detect_installed_platforms()
        if not platforms:
            print("No AI tools detected. Add config manually.")
            print("See: https://github.com/Gaurav7974/cognex#configuration")
            return
        print(f"Detected: {', '.join(platforms)}\n")

    success = []
    failed = []

    for p in platforms:
        if p not in PLATFORMS:
            print(f"Unknown platform: {p}")
            failed.append(p)
            continue
        ok = write_config(p, dry_run=dry_run)
        if ok:
            success.append(p)
        else:
            failed.append(p)

    # Inject AGENTS.md
    inject_agents_md(dry_run=dry_run)

    print("\n" + "=" * 40)
    if success:
        print(f"Configured: {', '.join(success)}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print("\nRestart your AI tool to activate Cognex.")
    print("You should see 18 new tools available.")


if __name__ == "__main__":
    run_install()
