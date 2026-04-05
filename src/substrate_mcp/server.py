"""
Cognitive Substrate MCP Server

Exposes the Cognitive Substrate as MCP tools for use with Claude Code,
OpenCode, Cursor, Codex, and any MCP-compatible AI coding assistant.

Uses stdio transport for local tool integration.
"""

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

from substrate_mcp.context import SubstrateContext
from substrate_mcp.tools import (
    list_all_tools,
    handle_tool_call,
)

# Configure logging to stderr (stdout is for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("substrate-mcp")


def create_server(name: str = "cognitive-substrate") -> Server:
    server = Server(name)

    @server.list_tools()
    async def handle_list_tools(
        params: types.ListToolsRequest,
    ) -> types.ListToolsResult:
        """List all available MCP tools."""
        return types.ListToolsResult(tools=list_all_tools())

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> types.CallToolResult:
        """Execute tool calls with error handling."""
        try:
            # Validate arguments exist
            if not arguments:
                raise McpError(
                    ErrorData(code=INVALID_PARAMS, message="Missing tool arguments")
                )

            # Delegate to tool handler
            result = await handle_tool_call(name, arguments)

            # Format result as text content
            if isinstance(result, dict):
                text = json.dumps(result, indent=2, default=str)
            else:
                text = str(result)

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=text)]
            )

        except McpError:
            # Re-raise MCP errors as-is
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
        """List all available MCP prompts."""
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
                description="End current session, save key decisions and memories, generate summary",
                arguments=[],
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
        """Get a specific prompt by name."""
        project = (arguments or {}).get("project", "")
        topic = (arguments or {}).get("topic", "")

        prompts = {
            "start-session": f"""
Please start a new Cognex session now.
1. Call substrate_start_session with a unique session_id (use current timestamp) and project="{project}"
2. Call memory_get_context with query="current work preferences decisions" and project="{project}"
3. Summarize what you found — preferences, recent decisions, patterns
4. Tell me what context you loaded so I know what you remember
""",
            "end-session": """
Please end the current Cognex session now.
1. Call memory_add for each important fact, preference, or pattern from this session
2. Call ledger_record for each significant decision made
3. Call substrate_end_session with a clear summary and list of key decisions
4. Tell me what you saved so I can verify nothing important was missed
""",
            "export-brain": """
Please export my entire Cognex brain now.
1. Call substrate_report to show current stats
2. Call teleport_create_bundle to create a portable export
3. Display the bundle JSON so I can save it
4. Tell me how to import it on another machine
""",
            "what-do-you-know": f"""
Please show me everything Cognex has stored about me.
1. Call memory_search with query="{topic or "preferences decisions patterns"}" and no project filter
2. Call trust_summary to show tool approval patterns
3. Call substrate_report for overall stats
4. Organize the results into categories: preferences, decisions, patterns, facts
""",
            "daily-standup": """
Please give me a daily standup summary from Cognex.
1. Call memory_search with query="yesterday recent completed" 
2. Call ledger_find_similar with query="recent decisions"
3. Call substrate_report for session stats
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
    server_name: str = "cognitive-substrate",
) -> None:
    # Initialize context
    ctx = SubstrateContext.get_instance(db_path=db_path, project=project)
    logger.info(f"Starting Cognitive Substrate MCP Server (db: {ctx.db_path})")

    # Create server
    server = create_server(server_name)

    # Run with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name=server_name,
            server_version=importlib.metadata.version("cognex"),
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(), experimental_capabilities={}
            ),
        )

        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    """Main entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Cognitive Substrate MCP Server")
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to database file (default: .substrate/substrate.db)",
    )
    parser.add_argument(
        "--project", type=str, default="default", help="Default project name"
    )
    parser.add_argument(
        "--name", type=str, default="cognitive-substrate", help="Server name"
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

    args = parser.parse_args()

    # Handle install command
    if args.install:
        from substrate_mcp.installer import run_install

        run_install(platform=args.platform, dry_run=args.dry_run)
        return

    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Run server
    try:
        asyncio.run(
            run_server(
                db_path=args.db_path, project=args.project, server_name=args.name
            )
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
    finally:
        SubstrateContext.reset_instance()


if __name__ == "__main__":
    main()
