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

    args = parser.parse_args()

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
