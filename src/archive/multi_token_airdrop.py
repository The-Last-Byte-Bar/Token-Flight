import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Tuple
from decimal import Decimal
from dotenv import load_dotenv
import os
from rich.console import Console
import time
import sys
from pathlib import Path
import json
import asyncio
from datetime import datetime
import requests
import pandas as pd
import argparse


from recipient_manager import RecipientManager, AirdropRecipient
from token_distributor import TokenDistributor, DistributionConfig
from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.space_ui import SpaceUI
from art.animations import SpaceAnimation
from env_config import EnvironmentConfig

ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)

@dataclass
class TokenDistributionPlan:
    token_name: str
    token_id: Optional[str]
    decimals: int
    recipients: List[str]
    amounts: List[int]
    hashrates: Optional[List[float]] = None

    def total_amount(self) -> Decimal:
        return Decimal(sum(self.amounts)) / Decimal(10 ** self.decimals)

    def validate_amounts(self) -> None:
        """Validate all amounts are greater than 0"""
        invalid = [(i, amt) for i, amt in enumerate(self.amounts) if amt <= 0]
        if invalid:
            error_msg = "\n".join(
                f"Recipient {i}: {amt}" for i, amt in invalid
            )
            raise ValueError(
                f"Invalid amounts found for {self.token_name}:\n{error_msg}"
            )

class MultiTokenAirdrop:
    def __init__(self, log_dir: str = "logs"):
        load_dotenv()
        self._setup_logging(log_dir)

        self.ui = SpaceUI()
        self.animator = SpaceAnimation(self.ui.console)
        self.console = Console()
        
        # Load and validate environment config
        self.config = EnvironmentConfig.load()
        self.logger.debug("Environment config loaded")
        
        # Initialize builder with network configuration
        self.builder = MultiOutputBuilder(
            node_url=self.config['node_url'],
            network_type=self.config['network_type'],
            explorer_url=self.config['explorer_url']
        )
        
        # Configure wallet based on available credentials
        self._configure_wallet()
        
        self.distributor = TokenDistributor(logger=self.logger)
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG
        
        # Initialize Telegram if configured
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.telegram = None
        if self.telegram_token and self.telegram_chat_id:
            from telegram.ext import Application
            self.telegram = Application.builder().token(self.telegram_token).build()

    def _configure_wallet(self):
        """Configure wallet based on available credentials"""
        try:
            # Start with checking for mnemonic
            mnemonic = self.config.get('wallet_mnemonic')
            if mnemonic:
                self.logger.info("Configuring wallet with mnemonic...")
                self.builder.wallet_manager.configure_mnemonic(
                    mnemonic=mnemonic,
                    password=self.config.get('mnemonic_password', '')
                )
                _, self.wallet_address = self.builder.wallet_manager.get_signing_config()
                self.logger.info(f"Wallet configured with mnemonic. Address: {self.wallet_address}")
                return

            # Fall back to node wallet if available
            node_api_key = self.config.get('node_api_key')
            node_wallet_address = self.config.get('node_wallet_address')
            if node_api_key and node_wallet_address:
                self.logger.info("Configuring wallet with node...")
                self.builder.ergo.apiKey = node_api_key
                self.builder.wallet_manager.configure_node_address(node_wallet_address)
                self.wallet_address = node_wallet_address
                self.logger.info(f"Wallet configured with node. Address: {self.wallet_address}")
                return

            raise ValueError(
                "No valid wallet configuration found. Please provide either:\n"
                "1. WALLET_MNEMONIC (and optionally MNEMONIC_PASSWORD) or\n"
                "2. NODE_API_KEY and NODE_WALLET_ADDRESS"
            )
        except Exception as e:
            self.logger.error(f"Failed to configure wallet: {str(e)}")
            raise

    def _setup_logging(self, log_dir: str):
        """Setup logging configuration"""
        log_dir = Path(log_dir)
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"airdrop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _get_token_data(self, token_name: str) -> tuple[Optional[str], int]:
        """Get token ID and decimals"""
        if token_name.upper() in ['ERG', 'ERGO']:
            return None, 9
            
        df = pd.read_csv('https://raw.githubusercontent.com/marctheshark3/Mining-Reward-Tokens/main/supported-tokens.csv')
        token_row = df[df['Token Name'] == token_name]
        if token_row.empty:
            raise ValueError(f"Token {token_name} not found in supported tokens list.")
        
        return token_row['Token ID'].values[0], int(token_row['Token decimals'].values[0])

    def is_valid_ergo_address(self, address: str) -> bool:
        """Validate Ergo address using ErgoAppKit"""
        try:
            self.builder.ergo.contractFromAddress(address)
            return True
        except Exception as e:
            self.logger.debug(f"Address validation failed: {str(e)}")
            return False
    
    def get_recipients(self, source: str) -> Tuple[List[str], List[float]]:
        """Get recipients and their hashrates from specified source"""
        try:
            # Check if source is a valid Ergo address
            if self.is_valid_ergo_address(source):
                addresses = [source]
                hashrates = [0]  # Set hashrate to 0 for direct address
                self.logger.info("Using direct address as recipient")
                
            elif source == "miners":
                response = requests.get('http://5.78.102.130:8000/sigscore/miners?pageSize=5000')
                response.raise_for_status()
                miners = response.json()
                addresses = [m['address'] for m in miners]
                hashrates = [m['hashrate'] for m in miners]
                
            else:
                # File handling
                if not os.path.exists(source):
                    raise FileNotFoundError(f"Recipients file not found: {source}")
                    
                if source.endswith('.json'):
                    with open(source) as f:
                        data = json.load(f)
                        addresses = [r['address'] for r in data]
                        hashrates = [r.get('hashrate', 0) for r in data]
                else:  # Assume CSV
                    df = pd.read_csv(source)
                    addresses = df['address'].tolist()
                    hashrates = df.get('hashrate', [0] * len(addresses)).tolist()
    
                # Validate all addresses
                invalid_addresses = [addr for addr in addresses if not self.is_valid_ergo_address(addr)]
                if invalid_addresses:
                    raise ValueError(f"Invalid addresses found: {invalid_addresses}")
    
            self.logger.info(f"Found {len(addresses)} valid recipients from source")
            return addresses, hashrates
                
        except Exception as e:
            self.logger.error(f"Failed to get recipients: {e}")
            raise

    async def notify_telegram(self, message: str):
        """Send notification to Telegram"""
        if self.telegram and self.telegram_chat_id:
            try:
                await self.telegram.bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                self.logger.error(f"Failed to send Telegram message: {e}")

    def notify_telegram_sync(self, message: str):
        """Synchronous wrapper for sending Telegram notifications"""
        if self.telegram:
            try:
                # asyncio.run(self.notify_telegram(message))
                pass
            except Exception as e:
                self.logger.error(f"Failed to send Telegram notification: {e}")

    def execute_multi_token_airdrop(self, config_file: str, source: str = "miners", 
                                      dry_run: bool = False) -> Dict:
        """Execute multi-token airdrop"""
        try:
            self.ui.display_welcome()
            self.notify_telegram_sync("🚀 Starting multi-token airdrop")
    
            # Load configuration
            with open(config_file) as f:
                config = json.load(f)
    
            # Get recipients
            recipients, hashrates = self.get_recipients(source)
            self.logger.info(f"Processing airdrop for {len(recipients)} recipients")
    
            # Create distribution plans
            plans = []
            for dist in config['distributions']:
                token_name = dist['token_name']
                token_id, decimals = self._get_token_data(token_name)
                self.logger.debug(f"Configuring distribution for {token_name}")
                
                # Calculate amounts
                distribution_config = DistributionConfig(
                    token_name=token_name,
                    total_amount=dist.get('total_amount'),
                    amount_per_recipient=dist.get('amount_per_recipient'),
                    decimals=decimals,
                    min_amount=0.001  # Set minimum amount to avoid dust
                )
                
                amounts = self.distributor.calculate_distribution(
                    config=distribution_config,
                    recipient_count=len(recipients)
                )
                
                plan = TokenDistributionPlan(
                    token_name=token_name,
                    token_id=token_id,
                    decimals=decimals,
                    recipients=recipients,
                    amounts=amounts,
                    hashrates=hashrates
                )
                
                # Validate amounts
                plan.validate_amounts()
                plans.append(plan)
    
            # Log distribution plans
            for plan in plans:
                total = plan.total_amount()
                self.logger.info(
                    f"Distribution plan for {plan.token_name}: "
                    f"{total:,.{plan.decimals}f} tokens to {len(plan.recipients)} recipients"
                )
    
            # Validate balances
            erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
            
            for plan in plans:
                if plan.token_id is None:  # ERG
                    required = sum(a / ERG_TO_NANOERG for a in plan.amounts)
                    if erg_balance < required:
                        raise ValueError(
                            f"Insufficient ERG. Required: {required:,.4f}, "
                            f"Available: {erg_balance:,.4f}"
                        )
                else:
                    balance = token_balances.get(plan.token_id, 0)
                    required = sum(plan.amounts)
                    if balance < required:
                        raise ValueError(
                            f"Insufficient {plan.token_name}. Required: "
                            f"{required / (10 ** plan.decimals):,.{plan.decimals}f}, "
                            f"Available: {balance / (10 ** plan.decimals):,.{plan.decimals}f}"
                        )
    
            # Create merged outputs
            outputs = []
            for recipient_idx, (recipient, *amounts) in enumerate(zip(recipients, *(plan.amounts for plan in plans))):
                tokens = []
                erg_value = self.min_box_value
                
                for plan, amount in zip(plans, amounts):
                    if amount <= 0:
                        raise ValueError(
                            f"Invalid amount for {plan.token_name} at recipient {recipient_idx}: "
                            f"{amount}. All token amounts must be greater than 0"
                        )
                        
                    if plan.token_id is None:  # ERG
                        erg_value += amount / ERG_TO_NANOERG
                    else:
                        tokens.append({
                            'tokenId': plan.token_id,
                            'amount': amount
                        })
                
                outputs.append(OutputBox(
                    address=recipient,
                    erg_value=erg_value,
                    tokens=tokens if tokens else None
                ))
    
            if dry_run:
                self.logger.info("Dry run completed successfully")
                self.notify_telegram_sync("✅ Dry run completed successfully")
                return {
                    "status": "dry_run",
                    "distributions": [
                        {
                            "token_name": plan.token_name,
                            "recipients": len(plan.recipients),
                            "total_amount": str(plan.total_amount())
                        }
                        for plan in plans
                    ]
                }
    
            # Execute transaction
            self.logger.info("Creating transaction...")
            tx_id = self.builder.create_multi_output_tx(outputs, self.wallet_address)
            
            explorer_base = os.getenv('EXPLORER_URL').rstrip('/').replace('/api/v1', '')
            explorer_link = f"{explorer_base}/transactions/{tx_id}"
            
            success_msg = (
                "✅ Multi-token airdrop successful!\n"
                f"Transaction: {explorer_link}\n\n"
                "Distributions:\n" +
                "\n".join(
                    f"- {plan.token_name}: {plan.total_amount():,.{plan.decimals}f}"
                    for plan in plans
                )
            )
            
            self.notify_telegram_sync(success_msg)
            self.ui.display_success(tx_id, explorer_link)
            
            return {
                "status": "completed",
                "tx_id": tx_id,
                "explorer_url": explorer_link,
                "distributions": [
                    {
                        "token_name": plan.token_name,
                        "recipients": len(plan.recipients),
                        "total_amount": str(plan.total_amount())
                    }
                    for plan in plans
                ]
            }
    
        except Exception as e:
            error_msg = f"Multi-token airdrop failed: {str(e)}"
            self.logger.error(error_msg)
            self.notify_telegram_sync(f"❌ {error_msg}")
            return {"status": "failed", "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Multi-token airdrop tool')
    parser.add_argument('config', help='Path to distribution config JSON')
    parser.add_argument('--source', default='miners', 
                       help='Source of recipients (miners/path to file/Ergo address)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Validate without executing transaction')
    args = parser.parse_args()
    
    try:
        airdrop = MultiTokenAirdrop()
        result = airdrop.execute_multi_token_airdrop(
            config_file=args.config,
            source=args.source,
            dry_run=args.dry_run
        )
        
        if result["status"] not in ["completed", "dry_run"]:
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()