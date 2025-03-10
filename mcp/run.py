#!/usr/bin/env python3
"""
Run script for the Ergo Payment Server MCP implementation.

This script starts the MCP server for Ergo blockchain payments.
"""

import os
import sys
import logging
from pathlib import Path
import subprocess

def ensure_conda_env():
    """Ensure we're running in the correct conda environment"""
    if 'CONDA_PREFIX' not in os.environ:
        logger.error("Not running in a conda environment. Please activate the 'pool' environment first.")
        sys.exit(1)
    
    if not os.environ.get('CONDA_PREFIX', '').endswith('pool'):
        logger.error("Wrong conda environment. Please activate the 'pool' environment.")
        sys.exit(1)

# Set up logging first
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
        # Ensure correct environment
        # ensure_conda_env()
        
        # Add both the parent directory and src directory to Python path
        current_dir = Path(__file__).parent
        parent_dir = current_dir.parent
        sys.path.extend([str(parent_dir), str(parent_dir / "src")])
        
        # Log Python environment details
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        from mcp import run
        logger.info("Starting Ergo Payment MCP server...")
        run()
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 