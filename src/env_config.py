from typing import Optional, Dict
import os
from dotenv import load_dotenv
import logging

class EnvironmentConfig:
    """Handles environment configuration and validation."""
    
    REQUIRED_VARS = [
        'NODE_URL',
        'NETWORK_TYPE',
        'EXPLORER_URL',
        'WALLET_ADDRESS'  # Added WALLET_ADDRESS as required
    ]
    
    NODE_VARS = ['NODE_API_KEY']
    MNEMONIC_VARS = ['WALLET_MNEMONIC']
    
    @staticmethod
    def load() -> Dict[str, str]:
        """Load and validate environment configuration."""
        logger = logging.getLogger(__name__)
        load_dotenv()
        
        # Check required variables
        missing = [var for var in EnvironmentConfig.REQUIRED_VARS 
                  if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        # Get wallet address
        wallet_address = os.getenv('WALLET_ADDRESS')
        if not wallet_address:
            raise ValueError("WALLET_ADDRESS must be provided in environment variables")
            
        # Check signing method requirements
        has_node = bool(os.getenv('NODE_API_KEY'))
        has_mnemonic = bool(os.getenv('WALLET_MNEMONIC'))
        
        if not (has_node or has_mnemonic):
            raise ValueError(
                "Either NODE_API_KEY or WALLET_MNEMONIC must be provided for transaction signing"
            )
            
        if has_node:
            logger.info("Found node API key - will use node signing")
        else:
            logger.info("No node API key found - will use mnemonic signing if available")
        
        if has_mnemonic:
            logger.info("Found mnemonic for backup signing")
            
        # Log configuration details
        logger.debug(f"Node URL: {os.getenv('NODE_URL')}")
        logger.debug(f"Network Type: {os.getenv('NETWORK_TYPE')}")
        logger.debug(f"Explorer URL: {os.getenv('EXPLORER_URL')}")
        logger.debug(f"Wallet Address: {wallet_address}")
        logger.debug(f"Node API Key: {'configured' if has_node else 'not configured'}")
        logger.debug(f"Mnemonic: {'configured' if has_mnemonic else 'not configured'}")
        
        config = {
            'node_url': os.getenv('NODE_URL'),
            'network_type': os.getenv('NETWORK_TYPE'),
            'explorer_url': os.getenv('EXPLORER_URL'),
            'node_api_key': os.getenv('NODE_API_KEY'),
            'node_wallet_address': wallet_address,  # Changed from wallet_address
            'wallet_mnemonic': os.getenv('WALLET_MNEMONIC'),
            'mnemonic_password': os.getenv('MNEMONIC_PASSWORD', ''),
            'use_node': has_node
        }
        
        return config