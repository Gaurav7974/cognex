
import asyncio
import importlib.metadata
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
from mcp import types
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR, ErrorData

from cognex_mcp.context import CognexContext
from cognex_mcp.tools import (
    list_all_tools,
    handle_tool_call,
)

# Configure logging to stderr (stdout is for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cognex-mcp")


def create_server(name: str = "cognex-engine") -> Server:
    server = Server(name)

    @server.list_tools()
    async def handle_list_tools(
        params: types.ListToolsRequest,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list_all_tools())

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> types.CallToolResult:
        try:
            if not arguments:
                raise McpError(
                    ErrorData(code=INVALID_PARAMS, message="Missing tool arguments")
                )

            result = await handle_tool_call(name, arguments)

            if isinstance(result, dict):
                text = json.dumps(result, indent=2, default=str)
            else:
                text = str(result)

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=text)]
            )

        except McpError:
            raise
        except ValueError as e:
            # Convert ValueError to MCP error
            raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))
        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception(f"Error executing tool {name}")
            raise McpError(
                ErrorData(code=INTERNAL_ERROR, message=f"Internal error: {str(e)}")
            )

    @server.list_prompts()
    async def handle_list_prompts() -> list[types.Prompt]:
        return [
            types.Prompt(
                name="start-session",
                description="Start a new Cognex session and load relevant memories for current project",
                arguments=[
                    types.PromptArgument(
                        name="project",
                        description="Project name to load context for",
                        required=False,
                    )
                ],
            ),
            types.Prompt(
                name="end-session",
                description="End current session and create a compact signed handoff manifest",
                arguments=[],
            ),
            types.Prompt(
                name="resume-handoff",
                description="Resume from a signed Cognex handoff manifest",
                arguments=[
                    types.PromptArgument(
                        name="manifest_json",
                        description="Signed handoff manifest JSON",
                        required=True,
                    )
                ],
            ),
            types.Prompt(
                name="export-brain",
                description="Export all memories and decisions as a portable bundle for transfer",
                arguments=[],
            ),
            types.Prompt(
                name="what-do-you-know",
                description="Show everything Cognex remembers about current project and preferences",
                arguments=[
                    types.PromptArgument(
                        name="topic",
                        description="Specific topic to query",
                        required=False,
                    )
                ],
            ),
            types.Prompt(
                name="daily-standup",
                description="Summarize what was worked on recently and what decisions were made",
                arguments=[],
            ),
        ]

    @server.get_prompt()
    async def handle_get_prompt(
        name: str, arguments: dict | None
    ) -> types.GetPromptResult:
        project = (arguments or {}).get("project", "")
        topic = (arguments or {}).get("topic", "")
        manifest_json = (arguments or {}).get("manifest_json", "")

        prompts = {
            "start-session": f"""
Please start a new Cognex session now.
1. Call cognex_start_session with a unique session_id (use current timestamp) and project="{project}"
2. Call recall with query="current work preferences decisions" and project="{project}"
3. Use note_reasoning at decision points for decisions, assumptions, rejected options, constraints, and questions
4. Tell me what context you loaded so I know what you remember
""",
            "end-session": """
Please end the current Cognex session now.
1. Call note_reasoning for any important unsaved decision, assumption, rejection, constraint, or question
2. Call cognex_end_session with a short summary and list of key decision ids
3. Call handoff_create with the active project, ordered goal_stack, in_flight_ops, and concise notes
4. Return the manifest id, baseline marker, and open questions
""",
            "resume-handoff": f"""
Please resume work from this Cognex handoff manifest.
1. Call handoff_resume with manifest_json={manifest_json!r}
2. Review the goal stack, must-not-revisit counterfactuals, open questions, and stale units
3. Pull details on demand with recall and provenance_trace; do not eagerly load full content
4. Continue by calling note_reasoning at new decision points
""",
            "export-brain": """
Please export my entire Cognex brain now.
1. Call cognex_report to show current stats
2. Call teleport_create_bundle to create a portable export
3. Display the bundle JSON so I can save it
4. Tell me how to import it on another machine
""",
            "what-do-you-know": f"""
Please show me everything Cognex has stored about me.
1. Call memory_search with query="{topic or "preferences decisions patterns"}" and no project filter
2. Call trust_summary to show tool approval patterns
3. Call cognex_report for overall stats
4. Organize the results into categories: preferences, decisions, patterns, facts
""",
            "daily-standup": """
Please give me a daily standup summary from Cognex.
1. Call memory_search with query="yesterday recent completed" 
2. Call ledger_find_similar with query="recent decisions"
3. Call cognex_report for session stats
4. Format as: What was done, What decisions were made, What to focus on next
""",
        }

        return types.GetPromptResult(
            description=f"Cognex prompt: {name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text", text=prompts.get(name, "Unknown prompt")
                    ),
                )
            ],
        )

    return server


async def run_server(
    db_path: Optional[str] = None,
    project: str = "default",
    server_name: str = "cognex-engine",
) -> None:
    ctx = CognexContext.get_instance(db_path=db_path, project=project)
    logger.info(f"Starting Cognex Engine MCP Server (db: {ctx.db_path})")

    try:
        count = ctx.engine.store.count()
        logger.info(f"Database health check passed: {count} memories")
        logger.info(
            "Cognex ready. Add to your AI tool config to connect. "
            "Run 'cognex --install' to auto-configure. "
            "Docs: https://github.com/Gaurav7004/cognex"
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise RuntimeError(f"Cannot start server: database not accessible - {e}")

    server = create_server(server_name)

    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name=server_name,
            server_version=importlib.metadata.version("cognex"),
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(), experimental_capabilities={}
            ),
        )

        await server.run(read_stream, write_stream, init_options)


def print_status(db_path: Optional[str] = None, project: str = "default") -> None:
    ctx = CognexContext.get_instance(db_path=db_path, project=project)

    print("Cognex status")
    print(f"Database: {ctx.db_path}")

    try:
        memory_count = ctx.engine.store.count()
        print(f"Memories: {memory_count}")
    except Exception as e:
        print(f"Memories: ERROR - {e}")

    try:
        from cognex.ledger import DecisionLedger

        ledger = DecisionLedger(ctx.db_path)
        decision_count = len(ledger.get_all(limit=9999))
        print(f"Decisions: {decision_count}")
    except Exception as e:
        print(f"Decisions: ERROR - {e}")

    try:
        from cognex.trust import TrustEngine

        trust = TrustEngine(ctx.db_path)
        trust_summary = trust.get_trust_summary()
        print(f"Trust Records: {len(trust_summary)}")
    except Exception as e:
        print(f"Trust Records: ERROR - {e}")

    print("Configured AI tools:")
    from cognex_mcp.installer import detect_installed_platforms

    detected = detect_installed_platforms()
    if detected:
        for platform in detected:
            print(f"- {platform}")
    else:
        print("- none")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Cognex Engine MCP Server")
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to database file (default: ~/.cognex.db/cognex.db)",
    )
    parser.add_argument(
        "--project", type=str, default="default", help="Default project name"
    )
    parser.add_argument(
        "--name", type=str, default="cognex-engine", help="Server name"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Auto-install Cognex config for all detected AI tools",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help="Install for specific platform: claude-code, opencode, cursor, cline, vscode, windsurf",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview install without making changes",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show cognex status (memories, decisions, trust records, AI tools)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cognex {importlib.metadata.version('cognex')}",
        help="Show version number and exit",
    )

    args = parser.parse_args()

    if args.install:
        from cognex_mcp.installer import run_install

        run_install(platform=args.platform, dry_run=args.dry_run)
        return

    if args.status:
        print_status(db_path=args.db_path, project=args.project)
        return

    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        asyncio.run(
            run_server(
                db_path=args.db_path, project=args.project, server_name=args.name
            )
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
    finally:
        CognexContext.reset_instance()


if __name__ == "__main__":
    main()
