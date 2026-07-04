
import asyncio
import importlib.metadata
import json
import logging
import re
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
from mcp import types
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR, ErrorData

from cognex_mcp.context import CognexContext
from cognex_mcp.tools import list_all_tools, handle_tool_call

logger = logging.getLogger("cognex-mcp")

# ---------------------------------------------------------------------------
# Safe string sanitiser: strips characters that enable prompt injection.
# Keeps printable ASCII + common Unicode text; removes control chars and
# the injection delimiters most commonly exploited in f-string prompts.
# ---------------------------------------------------------------------------
_INJECTION_RE = re.compile(r'[\x00-\x1f\x7f]|(?:ignore|disregard)\s+(?:previous|above)', re.I)

def _safe(value: str) -> str:
    """Sanitise user-supplied text before embedding in prompt messages."""
    return _INJECTION_RE.sub("", value)[:500]


# ---------------------------------------------------------------------------
# Prompt metadata (static — built once, not per-request)
# ---------------------------------------------------------------------------
_PROMPT_DEFS: list[types.Prompt] = [
    types.Prompt(
        name="start-session",
        description="Start a new Cognex session and load relevant memories for the current project",
        arguments=[
            types.PromptArgument(name="project", description="Project name", required=False)
        ],
    ),
    types.Prompt(
        name="end-session",
        description="End the current session and create a signed handoff manifest",
        arguments=[],
    ),
    types.Prompt(
        name="resume-handoff",
        description="Resume work from a signed Cognex handoff manifest",
        arguments=[
            types.PromptArgument(name="manifest_json", description="Signed handoff manifest JSON", required=True)
        ],
    ),
    types.Prompt(
        name="export-brain",
        description="Export all memories and decisions as a portable bundle",
        arguments=[],
    ),
    types.Prompt(
        name="what-do-you-know",
        description="Show everything Cognex remembers about the current project and preferences",
        arguments=[
            types.PromptArgument(name="topic", description="Specific topic to query", required=False)
        ],
    ),
    types.Prompt(
        name="daily-standup",
        description="Summarise recent work and decisions",
        arguments=[],
    ),
]

_PROMPT_NAMES: frozenset[str] = frozenset(p.name for p in _PROMPT_DEFS)

# Required arguments per prompt (empty set = none required)
_PROMPT_REQUIRED: dict[str, frozenset[str]] = {
    "resume-handoff": frozenset({"manifest_json"}),
}


def _build_prompt_text(name: str, args: dict) -> str:
    """Return the instruction text for a prompt, with sanitised interpolations."""
    project      = _safe(args.get("project", ""))
    topic        = _safe(args.get("topic", ""))
    manifest_json = _safe(args.get("manifest_json", ""))

    if name == "start-session":
        return (
            "Please start a new Cognex session now.\n"
            f'1. Call cognex_start_session with a unique session_id and project="{project}"\n'
            f'2. Call recall with query="current work preferences decisions" and project="{project}"\n'
            "3. Use note_reasoning at decision points for decisions, assumptions, constraints, and questions\n"
            "4. Tell me what context you loaded so I know what you remember"
        )
    if name == "end-session":
        return (
            "Please end the current Cognex session now.\n"
            "1. Call note_reasoning for any unsaved decision, assumption, rejection, constraint, or question\n"
            "2. Call cognex_end_session with a short summary and list of key decision IDs\n"
            "3. Call handoff_create with the active project, ordered goal_stack, in_flight_ops, and concise notes\n"
            "4. Return the manifest id, baseline marker, and open questions"
        )
    if name == "resume-handoff":
        return (
            "Please resume work from this Cognex handoff manifest.\n"
            f"1. Call handoff_resume with manifest_json={manifest_json!r}\n"
            "2. Review the goal stack, must-not-revisit counterfactuals, open questions, and stale units\n"
            "3. Pull details on demand with recall and provenance_trace — do not eagerly load full content\n"
            "4. Continue by calling note_reasoning at new decision points"
        )
    if name == "export-brain":
        return (
            "Please export my entire Cognex brain now.\n"
            "1. Call cognex_report to show current stats\n"
            "2. Call teleport_create_bundle to create a portable export\n"
            "3. Display the bundle JSON so I can save it\n"
            "4. Tell me how to import it on another machine"
        )
    if name == "what-do-you-know":
        query = topic or "preferences decisions patterns"
        return (
            "Please show me everything Cognex has stored about me.\n"
            f'1. Call recall with query="{query}" and kind="all"\n'
            "2. Call trust_query to show tool approval patterns\n"
            "3. Call cognex_report for overall stats\n"
            "4. Organise the results into categories: preferences, decisions, patterns, facts"
        )
    if name == "daily-standup":
        return (
            "Please give me a daily standup summary from Cognex.\n"
            '1. Call recall with query="yesterday recent completed" and kind="all"\n'
            '2. Call recall with query="recent decisions" and kind="decision"\n'
            "3. Call cognex_report for session stats\n"
            "4. Format as: What was done | What decisions were made | What to focus on next"
        )
    # Should never reach here — caller validates the name first.
    raise AssertionError(f"unhandled prompt name: {name!r}")


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_server(server_name: str = "cognex-engine") -> Server:
    server = Server(server_name)

    @server.list_tools()
    async def handle_list_tools(params: types.ListToolsRequest) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list_all_tools())

    @server.call_tool()
    async def handle_call_tool(
        tool_name: str, arguments: dict | None
    ) -> types.CallToolResult:
        logger.info("tool_call name=%s args_keys=%s", tool_name, list((arguments or {}).keys()))
        try:
            result = await handle_tool_call(tool_name, arguments or {})
            text = json.dumps(result, indent=2, default=str) if isinstance(result, dict) else str(result)
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)])

        except McpError:
            raise
        except (ValueError, TypeError, KeyError) as e:
            # Caller error — classify as INVALID_PARAMS, not internal error
            raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))
        except Exception as e:
            logger.exception("Unexpected error in tool %r", tool_name)
            # Avoid leaking internal paths/tracebacks to the client
            raise McpError(ErrorData(code=INTERNAL_ERROR, message="Internal server error"))

    @server.list_prompts()
    async def handle_list_prompts() -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=_PROMPT_DEFS)

    @server.get_prompt()
    async def handle_get_prompt(
        name: str, arguments: dict | None
    ) -> types.GetPromptResult:
        if name not in _PROMPT_NAMES:
            raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Unknown prompt: {name!r}"))

        args = arguments or {}
        required = _PROMPT_REQUIRED.get(name, frozenset())
        missing = required - args.keys()
        if missing:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message=f"Prompt {name!r} requires argument(s): {', '.join(sorted(missing))}",
            ))

        text = _build_prompt_text(name, args)
        return types.GetPromptResult(
            description=next(p.description for p in _PROMPT_DEFS if p.name == name),
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )

    return server


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _cognex_version() -> str:
    try:
        return importlib.metadata.version("cognex")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


async def run_server(
    db_path: Optional[str] = None,
    project: str = "default",
    server_name: str = "cognex-engine",
) -> None:
    ctx = CognexContext.get_instance(db_path=db_path, project=project)
    logger.info("Starting Cognex Engine MCP Server (db: %s)", ctx.db_path)

    try:
        count = ctx.engine.store.count()
        logger.info("Database health check passed: %d memories", count)
    except Exception as e:
        logger.error("Startup health check failed: %s", e)
        raise RuntimeError(f"Cannot start server: {e}") from e

    server = create_server(server_name)

    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name=server_name,
            server_version=_cognex_version(),
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_options)


# ---------------------------------------------------------------------------
# CLI status
# ---------------------------------------------------------------------------

def print_status(db_path: Optional[str] = None, project: str = "default") -> None:
    ctx = CognexContext.get_instance(db_path=db_path, project=project)
    print("Cognex status")
    print(f"Database: {ctx.db_path}")

    try:
        print(f"Memories:  {ctx.engine.store.count()}")
    except Exception as e:
        print(f"Memories:  ERROR — {e}")

    try:
        from cognex.ledger import DecisionLedger
        print(f"Decisions: {DecisionLedger(ctx.db_path).count()}")
    except Exception as e:
        print(f"Decisions: ERROR — {e}")

    try:
        from cognex.trust import TrustEngine
        print(f"Trust records: {len(TrustEngine(ctx.db_path).get_trust_summary())}")
    except Exception as e:
        print(f"Trust records: ERROR — {e}")

    try:
        from cognex_mcp.installer import detect_installed_platforms
        detected = detect_installed_platforms()
        print("Configured AI tools:", ", ".join(detected) if detected else "none")
    except Exception as e:
        print(f"Configured AI tools: ERROR — {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    # Logging belongs here, not at module level — avoids side-effects on import
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description="Cognex Engine MCP Server")
    parser.add_argument("--db-path", default=None, help="Path to database file")
    parser.add_argument("--project", default="default", help="Default project name")
    parser.add_argument("--name", default="cognex-engine", help="Server name")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=f"cognex {_cognex_version()}")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true", help="Auto-install config for all detected AI tools")
    mode.add_argument("--status", action="store_true", help="Show status (memories, decisions, trust, platforms)")

    parser.add_argument("--platform", default=None, help="Install for specific platform")
    parser.add_argument("--dry-run", action="store_true", help="Preview install without changes")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.install:
        from cognex_mcp.installer import run_install
        run_install(platform=args.platform, dry_run=args.dry_run)
        return

    if args.status:
        print_status(db_path=args.db_path, project=args.project)
        return

    try:
        asyncio.run(run_server(db_path=args.db_path, project=args.project, server_name=args.name))
    except KeyboardInterrupt:
        logger.info("Server stopped")
    finally:
        ctx = CognexContext._instance  # noqa: SLF001 — explicit close before reset
        if ctx is not None:
            try:
                ctx.engine.close()
            except Exception:
                pass
        CognexContext.reset_instance()


if __name__ == "__main__":
    main()
