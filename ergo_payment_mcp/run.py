#!/usr/bin/env python3
"""
Run script for the Ergo Payment Server MCP implementation.

This script starts the MCP server for Ergo blockchain payments.
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "mcp_server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run the MCP server"""
    try:
        from ergo_payment_mcp import server
        logger.info("Starting Ergo Payment MCP server...")
        server.run()
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 