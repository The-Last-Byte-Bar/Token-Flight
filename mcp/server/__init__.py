"""
MCP server package initialization.
"""

from mcp.server.base import FastMCP, Context, Image
from mcp.server.fastmcp import mcp

__all__ = ['FastMCP', 'Context', 'Image', 'mcp']

def run():
    """Start the MCP server"""
    mcp.run()
