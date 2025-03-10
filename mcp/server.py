"""
MCP server module for Ergo blockchain monitoring and control.
"""

import logging
import sys
import os
from pathlib import Path

# Add both the parent directory and src directory to Python path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.extend([str(parent_dir), str(parent_dir / "src")])

from models import AirdropConfig, WalletConfig, TokenConfig

logger = logging.getLogger(__name__)

class Server:
    """MCP Server implementation"""
    def __init__(self):
        self.config = None
        
    def start(self):
        """Start the MCP server"""
        # Initialize with default configuration
        wallet_config = WalletConfig(
            node_url="http://localhost:9053",
            network_type="mainnet",
            explorer_url="https://api.ergoplatform.com"
        )
        
        self.config = AirdropConfig(
            wallet_config=wallet_config,
            tokens=[],
            debug=True
        )
        
        logger.info("MCP Server initialized successfully")

def run():
    """Start the MCP server"""
    try:
        logger.info("Starting Ergo Payment MCP server...")
        server = Server()
        server.start()
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise 