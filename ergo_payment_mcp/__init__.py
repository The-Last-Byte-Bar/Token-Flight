"""
Ergo Payment Server MCP Implementation

This module provides a Model Context Protocol (MCP) server for Ergo blockchain payments,
including bonus payments, demurrage payments, and custom payment configurations.
"""

# Import from the actual MCP package
from mcp.server.fastmcp import FastMCP

# Import components
from ergo_payment_mcp.tools.blockchain_tools import register_blockchain_tools
from ergo_payment_mcp.tools.wallet_tools import register_wallet_tools
from ergo_payment_mcp.resources.payment_resources import register_payment_resources
from ergo_payment_mcp.prompts.payment_prompts import register_payment_prompts

__version__ = "0.1.0"

def create_server():
    """Create and configure the MCP server for Ergo payments"""
    
    # Create the server
    mcp_server = FastMCP(
        "Ergo Payment Server",
        description="MCP server for Ergo blockchain payments and distributions",
        dependencies=["typing", "logging", "requests", "pandas", "dataclasses"]
    )
    
    # Register components
    mcp_server = register_blockchain_tools(mcp_server)
    mcp_server = register_wallet_tools(mcp_server)
    mcp_server = register_payment_resources(mcp_server)
    mcp_server = register_payment_prompts(mcp_server)
    
    return mcp_server
    
# Default server instance
server = create_server()

# For direct execution
if __name__ == "__main__":
    server.run() 