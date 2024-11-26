import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
import os
import requests
import pandas as pd
import sys
import time
import argparse
import json
from datetime import datetime
from pathlib import Path
import asyncio
from telegram.ext import Application

from multi_output_builder import MultiOutputBuilder, OutputBox, WalletLockedException
from recipient_manager import RecipientManager, AirdropRecipient

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value

class HeadlessAirdrop:
    def __init__(self, log_dir: str = "logs"):
        load_dotenv()
        
        # Set up logging
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        log_file = self.log_dir / f"airdrop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.setup_logging(log_file)
        
        self.logger = logging.getLogger(__name__)
        
        # Validate environment variables
        required_vars = [
            'NODE_URL', 'NODE_API_KEY', 'NETWORK_TYPE', 'EXPLORER_URL', 
            'WALLET_ADDRESS'
        ]
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(f"Missing required environment variable: {var}")
        
        self.node_url = os.getenv('NODE_URL')
        self.node_api_key = os.getenv('NODE_API_KEY')
        self.network_type = os.getenv('NETWORK_TYPE')
        self.explorer_url = os.getenv('EXPLORER_URL')
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        
        # Initialize Telegram if configured
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.telegram = None
        if self.telegram_token and self.telegram_chat_id:
            self.telegram = Application.builder().token(self.telegram_token).build()
        
        self.builder = MultiOutputBuilder(
            node_url=self.node_url,
            network_type=self.network_type,
            explorer_url=self.explorer_url,
            node_api_key=self.node_api_key
        )
        
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG

    def setup_logging(self, log_file: Path):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

    async def send_telegram_notification(self, message: str):
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

    def notify_telegram(self, message: str):
        """Synchronous wrapper for sending Telegram notifications"""
        if self.telegram:
            try:
                asyncio.run(self.send_telegram_notification(message))
            except Exception as e:
                self.logger.error(f"Failed to send Telegram notification: {e}")

    def save_transaction_record(self, tx_data: Dict):
        """Save transaction details to JSON file"""
        tx_file = self.log_dir / f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(tx_file, 'w') as f:
            json.dump(tx_data, f, indent=2)
        self.logger.info(f"Transaction record saved to {tx_file}")

    def prepare_amounts(self, total_amount: Optional[float], amount_per_recipient: Optional[float], 
                       recipient_count: int, decimals: int) -> List[int]:
        """Calculate distribution amounts properly handling decimals"""
        if amount_per_recipient is not None:
            # Fixed amount per recipient
            amount_in_smallest = int(amount_per_recipient * (10 ** decimals))
            return [amount_in_smallest] * recipient_count
        else:
            # Split total amount
            total_in_smallest = int(total_amount * (10 ** decimals))
            base_amount = total_in_smallest // recipient_count
            remainder = total_in_smallest % recipient_count
            
            amounts = [base_amount] * recipient_count
            # Distribute remainder to first N recipients
            for i in range(remainder):
                amounts[i] += 1
                
            return amounts

    def get_token_data(self, token_name: str) -> Tuple[Optional[str], int]:
        """Get token ID and decimals. Returns (None, 9) for ERG."""
        if token_name.upper() in ['ERG', 'ERGO']:
            return None, 9  # ERG has 9 decimals
            
        df = pd.read_csv('https://raw.githubusercontent.com/marctheshark3/Mining-Reward-Tokens/main/supported-tokens.csv')
        token_row = df[df['Token Name'] == token_name]
        if token_row.empty:
            raise ValueError(f"Token {token_name} not found in supported tokens list.")
        
        token_id = token_row['Token ID'].values[0]
        decimals = int(token_row['Token decimals'].values[0])
        return token_id, decimals

    def execute_airdrop(self, token_name: str, recipients: List[AirdropRecipient], 
                       total_amount: Optional[float] = None,
                       amount_per_recipient: Optional[float] = None,
                       dry_run: bool = False) -> Dict:
        try:
            self.logger.info(f"Starting airdrop for {token_name}")
            self.notify_telegram(f"🚀 Starting {token_name} airdrop to {len(recipients)} recipients")
            
            # Check if we're dealing with ERG or a token
            is_erg = token_name.upper() in ['ERG', 'ERGO']
            token_id, token_decimals = self.get_token_data(token_name)
            
            # Calculate amounts for each recipient
            amounts = self.prepare_amounts(
                total_amount=total_amount,
                amount_per_recipient=amount_per_recipient,
                recipient_count=len(recipients),
                decimals=token_decimals
            )
            
            # Create output boxes
            outputs = []
            for recipient, amount in zip(recipients, amounts):
                if is_erg:
                    outputs.append(OutputBox(
                        address=recipient.address,
                        erg_value=amount / ERG_TO_NANOERG,
                        tokens=None
                    ))
                else:
                    outputs.append(OutputBox(
                        address=recipient.address,
                        erg_value=self.min_box_value,
                        tokens=[{
                            'tokenId': token_id,
                            'amount': amount
                        }]
                    ))
            
            # Calculate totals
            total_amount_actual = sum(amount / (10 ** token_decimals) for amount in amounts)
            if is_erg:
                total_erg_needed = total_amount_actual
            else:
                total_erg_needed = self.builder.estimate_transaction_cost(len(recipients))
            
            # Check balances
            erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
            if is_erg:
                token_balance = erg_balance
            else:
                token_balance = token_balances.get(token_id, 0) / (10 ** token_decimals)
            
            # Log distribution summary
            self.logger.info(f"Distribution Summary:")
            summary_msg = f"""
<b>📊 Airdrop Summary</b>
<b>Token</b>: {token_name}
<b>Recipients</b>: {len(recipients)}
<b>Total Amount</b>: {total_amount_actual:,.{token_decimals}f} {token_name}
<b>Required ERG</b>: {total_erg_needed:,.4f}
<b>Current ERG Balance</b>: {erg_balance:,.4f}
<b>Current Token Balance</b>: {token_balance:,.{token_decimals}f}
"""
            self.notify_telegram(summary_msg)
            
            # Validate balances
            if erg_balance < total_erg_needed:
                error_msg = f"Insufficient ERG. Required: {total_erg_needed:,.4f}, Available: {erg_balance:,.4f}"
                self.notify_telegram(f"❌ Airdrop failed: {error_msg}")
                raise ValueError(error_msg)
            
            if not is_erg and token_balance < total_amount_actual:
                error_msg = (f"Insufficient {token_name}. Required: {total_amount_actual:,.{token_decimals}f}, "
                           f"Available: {token_balance:,.{token_decimals}f}")
                self.notify_telegram(f"❌ Airdrop failed: {error_msg}")
                raise ValueError(error_msg)
            
            if dry_run:
                self.logger.info("Dry run completed successfully")
                self.notify_telegram("✅ Dry run completed successfully")
                tx_data = {
                    "status": "dry_run",
                    "token_name": token_name,
                    "recipients": len(recipients),
                    "total_amount": total_amount_actual,
                    "total_erg": total_erg_needed,
                    "timestamp": datetime.now().isoformat(),
                    "distribution": [
                        {
                            "address": r.address,
                            "amount": a / (10 ** token_decimals)
                        }
                        for r, a in zip(recipients, amounts)
                    ]
                }
                self.save_transaction_record(tx_data)
                return tx_data
    
            try:
                self.logger.info("Creating transaction...")
                self.notify_telegram("🔄 Creating transaction...")
                tx_id = self.builder.create_multi_output_tx(outputs, self.wallet_address)
                
                explorer_base = self.explorer_url.rstrip('/').replace('/api/v1', '')
                explorer_link = f"{explorer_base}/transactions/{tx_id}"
                
                success_msg = f"""
<b>✅ Airdrop Successful!</b>
<b>Token</b>: {token_name}
<b>Recipients</b>: {len(recipients)}
<b>Total Amount</b>: {total_amount_actual:,.{token_decimals}f} {token_name}
<b>Total ERG Cost</b>: {total_erg_needed:,.4f} ERG
<b>Transaction</b>: <a href="{explorer_link}">{tx_id[:6]}...{tx_id[-6:]}</a>
"""
                self.notify_telegram(success_msg)
                self.logger.info(f"Transaction successful: {explorer_link}")
                
                tx_data = {
                    "status": "completed",
                    "tx_id": tx_id,
                    "explorer_url": explorer_link,
                    "token_name": token_name,
                    "recipients": len(recipients),
                    "total_amount": total_amount_actual,
                    "total_erg": total_erg_needed,
                    "timestamp": datetime.now().isoformat(),
                    "distribution": [
                        {
                            "address": r.address,
                            "amount": a / (10 ** token_decimals)
                        }
                        for r, a in zip(recipients, amounts)
                    ]
                }
                self.save_transaction_record(tx_data)
                return tx_data
    
            except WalletLockedException as e:
                error_msg = f"Wallet is locked: {str(e)}"
                self.notify_telegram(f"🔒 Airdrop failed: {error_msg}")
                return {"status": "failed", "error": "wallet_locked", "details": str(e)}
                
            except Exception as e:
                error_msg = f"Transaction failed: {str(e)}"
                self.notify_telegram(f"❌ Airdrop failed: {error_msg}")
                return {"status": "failed", "error": "transaction_failed", "details": str(e)}
    
        except Exception as e:
            error_msg = f"Airdrop failed: {str(e)}"
            self.notify_telegram(f"❌ {error_msg}")
            return {"status": "failed", "error": "airdrop_failed", "details": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Headless token airdrop for automated execution.')
    parser.add_argument('token_name', help='Name of token to airdrop (use "ERG" for Ergo coin)')
    
    # Add mutually exclusive group for amount specification
    amount_group = parser.add_mutually_exclusive_group(required=True)
    amount_group.add_argument('--total-amount', type=float, help='Total amount to distribute')
    amount_group.add_argument('--amount-per-recipient', type=float, help='Amount per recipient')
    
    parser.add_argument('--min-hashrate', type=float, default=0, help='Minimum hashrate filter')
    parser.add_argument('--dry-run', action='store_true', help='Validate without executing transaction')
    parser.add_argument('--recipient-list', help='Path to CSV file with recipients')
    parser.add_argument('--addresses', nargs='+', help='List of recipient addresses')
    parser.add_argument('--log-dir', default='logs', help='Directory for log files')
    
    args = parser.parse_args()
    
    try:
        airdrop = HeadlessAirdrop(log_dir=args.log_dir)
        
        if args.recipient_list:
            recipients = RecipientManager.from_csv(args.recipient_list)
        elif args.addresses:
            recipients = RecipientManager.from_list(args.addresses)
        else:
            recipients = RecipientManager.from_miners(args.min_hashrate)
        
        result = airdrop.execute_airdrop(
            token_name=args.token_name,
            recipients=recipients,
            total_amount=args.total_amount,
            amount_per_recipient=args.amount_per_recipient,
            dry_run=args.dry_run
        )
        
        if result["status"] not in ["completed", "dry_run"]:
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()