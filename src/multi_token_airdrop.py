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

from recipient_manager import RecipientManager, AirdropRecipient
from token_distributor import TokenDistributor, DistributionConfig
from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.space_ui import SpaceUI
from art.animations import SpaceAnimation

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

class MultiTokenAirdrop:
    def __init__(self, log_dir: str = "logs"):
        load_dotenv()
        self._setup_logging(log_dir)
        self._validate_env()

        self.ui = SpaceUI()
        self.animator = SpaceAnimation(self.ui.console)
        self.console = Console()
        
        self.builder = MultiOutputBuilder(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            node_api_key=os.getenv('NODE_API_KEY')
        )
        
        self.distributor = TokenDistributor(logger=self.logger)
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG
        
        # Initialize Telegram if configured
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.telegram = None
        if self.telegram_token and self.telegram_chat_id:
            from telegram.ext import Application
            self.telegram = Application.builder().token(self.telegram_token).build()

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

    def _validate_env(self):
        """Validate required environment variables"""
        required_vars = [
            'NODE_URL', 'NODE_API_KEY', 'NETWORK_TYPE', 
            'EXPLORER_URL', 'WALLET_ADDRESS'
        ]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

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

    def _get_token_data(self, token_name: str) -> tuple[Optional[str], int]:
        """Get token ID and decimals"""
        if token_name.upper() in ['ERG', 'ERGO']:
            return None, 9
            
        import pandas as pd
        df = pd.read_csv('https://raw.githubusercontent.com/marctheshark3/Mining-Reward-Tokens/main/supported-tokens.csv')
        token_row = df[df['Token Name'] == token_name]
        if token_row.empty:
            raise ValueError(f"Token {token_name} not found in supported tokens list.")
        
        return token_row['Token ID'].values[0], int(token_row['Token decimals'].values[0])

    def get_recipients(self, source: str) -> Tuple[List[str], List[float]]:
        """Get recipients and their hashrates from specified source"""
        try:
            if source == "miners":
                response = requests.get('http://5.78.102.130:8000/sigscore/miners?pageSize=5000')
                response.raise_for_status()
                miners = response.json()
                addresses = [m['address'] for m in miners]
                hashrates = [m['hashrate'] for m in miners]
            else:
                # Assume source is a file path
                if not os.path.exists(source):
                    raise FileNotFoundError(f"Recipients file not found: {source}")
                    
                if source.endswith('.json'):
                    with open(source) as f:
                        data = json.load(f)
                        addresses = [r['address'] for r in data]
                        hashrates = [r.get('hashrate', 0) for r in data]
                else:  # Assume CSV
                    import pandas as pd
                    df = pd.read_csv(source)
                    addresses = df['address'].tolist()
                    hashrates = df.get('hashrate', [0] * len(addresses)).tolist()

            self.logger.info(f"Found {len(addresses)} recipients from source")
            return addresses, hashrates
            
        except Exception as e:
            self.logger.error(f"Failed to get recipients: {e}")
            raise

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

            # Create distribution plans
            plans = []
            for dist in config['distributions']:
                token_name = dist['token_name']
                token_id, decimals = self._get_token_data(token_name)
                
                # Calculate amounts
                distribution_config = DistributionConfig(
                    token_name=token_name,
                    total_amount=dist.get('total_amount'),
                    amount_per_recipient=dist.get('amount_per_recipient'),
                    decimals=decimals
                )
                
                amounts = self.distributor.calculate_distribution(
                    config=distribution_config,
                    recipient_count=len(recipients)
                )
                
                plans.append(TokenDistributionPlan(
                    token_name=token_name,
                    token_id=token_id,
                    decimals=decimals,
                    recipients=recipients,
                    amounts=amounts,
                    hashrates=hashrates
                ))

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
            for recipient, *amounts in zip(recipients, *(plan.amounts for plan in plans)):
                tokens = []
                erg_value = self.min_box_value
                
                for plan, amount in zip(plans, amounts):
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-token airdrop tool')
    parser.add_argument('config', help='Path to distribution config JSON')
    parser.add_argument('--source', default='miners', 
                       help='Source of recipients (miners/path to file)')
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