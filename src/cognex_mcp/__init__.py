"""
Cognex Engine MCP Package

Persistent memory layer for AI agents via Model Context Protocol (MCP).
"""

__version__ = "0.1.0"

from cognex_mcp.server import create_server

__all__ = ["__version__", "create_server"]
