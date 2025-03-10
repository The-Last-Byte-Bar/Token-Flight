"""
MCP (Monitoring and Control Panel) package for Ergo blockchain.
"""

import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the Python environment for MCP"""
    # Add the parent directory to Python path if not already there
    parent_dir = str(Path(__file__).parent.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        logger.info(f"Added {parent_dir} to Python path")
    
    # Add src directory to Python path if not already there
    src_dir = str(Path(parent_dir) / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        logger.info(f"Added {src_dir} to Python path")

# Set up the environment
setup_environment()

try:
    from src.models import AirdropConfig, WalletConfig, TokenConfig, RecipientAmount, AirdropRecipient, TransactionResult
    from mcp.server import run
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error(f"Python path: {sys.path}")
    raise

__version__ = "0.5.0"  # Updated to match setup.py

__all__ = [
    'run',
    'AirdropConfig',
    'WalletConfig',
    'TokenConfig',
    'RecipientAmount',
    'AirdropRecipient',
    'TransactionResult'
] 