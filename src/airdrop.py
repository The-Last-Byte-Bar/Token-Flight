#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from typing import List
from pathlib import Path

from models import (
    AirdropConfig, TokenConfig, WalletConfig, 
    RecipientAmount  # Add this import
)
from base_airdrop import BaseAirdrop
from ui.space_ui import SpaceUI
from env_config import EnvironmentConfig

def setup_logging(log_dir: str = "logs"):
    """Setup logging configuration"""
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "airdrop.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def parse_token_configs(config_file: str) -> List[TokenConfig]:
    """Parse token configurations from JSON file"""
    with open(config_file) as f:
        data = json.load(f)
    
    tokens = []
    for token_data in data['distributions']:
        # Parse recipient-specific amounts if provided
        recipients = None
        if 'recipients' in token_data:
            recipients = [
                RecipientAmount(
                    address=r['address'],
                    amount=float(r['amount'])
                )
                for r in token_data['recipients']
            ]
        
        tokens.append(TokenConfig(
            token_name=token_data['token_name'],
            total_amount=token_data.get('total_amount'),
            amount_per_recipient=token_data.get('amount_per_recipient'),
            min_amount=token_data.get('min_amount', 0.001),
            decimals=token_data.get('decimals', 0),
            recipients=recipients
        ))
    return tokens

def main():
    parser = argparse.ArgumentParser(description='Ergo Token Airdrop Tool')
    
    # Required arguments
    parser.add_argument('config', help='Path to token distribution config JSON')
    
    # Auth method (mutually exclusive)
    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument('--use-node', action='store_true', help='Use node wallet for signing')
    auth_group.add_argument('--use-seed', action='store_true', help='Use seed phrase for signing')
    
    # Optional arguments
    parser.add_argument('--source', default='miners', help='Recipients source: miners/CSV file/address')
    parser.add_argument('--min-hashrate', type=float, default=0, help='Minimum hashrate filter')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--headless', action='store_true', help='Run without user prompts')
    
    args = parser.parse_args()
    
    try:
        # Setup logging
        logger = setup_logging()
        
        # Load environment config
        env_dict = EnvironmentConfig.load()
        
        # Create wallet config from environment
        wallet_config = WalletConfig(
            node_url=env_dict['node_url'],
            network_type=env_dict['network_type'],
            explorer_url=env_dict['explorer_url'],
            node_api_key=env_dict['node_api_key'],
            node_wallet_address=env_dict['node_wallet_address'],
            wallet_mnemonic=env_dict['wallet_mnemonic'],
            mnemonic_password=env_dict.get('mnemonic_password', '')
        )
        
        # Validate auth method against available credentials
        if args.use_node and not (wallet_config.node_api_key and wallet_config.node_wallet_address):
            raise ValueError("Node API key and wallet address required for node signing")
        if args.use_seed and not wallet_config.wallet_mnemonic:
            raise ValueError("Seed phrase required for mnemonic signing")
        
        # If using node, remove mnemonic config
        if args.use_node:
            wallet_config.wallet_mnemonic = None
            wallet_config.mnemonic_password = None
        
        # If using seed, remove node config
        if args.use_seed:
            wallet_config.node_api_key = None
            wallet_config.node_wallet_address = None
        
        # Parse token configs
        tokens = parse_token_configs(args.config)
        
        # Create airdrop config
        config = AirdropConfig(
            wallet_config=wallet_config,
            tokens=tokens,
            min_hashrate=args.min_hashrate,
            debug=args.debug,
            headless=args.headless,
            recipients_file=args.source if args.source.endswith('.csv') else None,
            recipient_addresses=[args.source] if args.source.startswith('9') else None
        )
        
        # Initialize and execute airdrop
        airdrop = BaseAirdrop(config=config, ui=SpaceUI())
        result = airdrop.execute()
        
        if result.status not in ["completed", "debug"]:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()