import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
import os
import requests
import pandas as pd
import asyncio
from telegram.ext import Application
import sys

from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.cyberpunk_ui import CyberpunkUI
from ui.space_ui import SpaceUI

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value

@dataclass
class AirdropRecipient:
    address: str
    amount: float
    hashrate: float = 0.0

class TokenAirdrop:
    SIGSCORE_API = 'http://5.78.102.130:8000/sigscore/miners?pageSize=5000'

    def __init__(self, theme: str = "cyberpunk"):
        load_dotenv()
        
        # Required environment variables check
        required_vars = [
            'NODE_URL', 'NODE_API_KEY', 'NETWORK_TYPE', 'EXPLORER_URL', 
            'WALLET_ADDRESS', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'
        ]
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(f"Missing required environment variable: {var}")
        
        # Node configuration
        self.node_url = os.getenv('NODE_URL')
        self.node_api_key = os.getenv('NODE_API_KEY')
        self.network_type = os.getenv('NETWORK_TYPE')
        self.explorer_url = os.getenv('EXPLORER_URL')
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        
        # Initialize builder and UI
        self.builder = MultiOutputBuilder(
            node_url=self.node_url,
            network_type=self.network_type,
            explorer_url=self.explorer_url,
            node_api_key=self.node_api_key
        )
        
        # Set UI theme
        self.ui = CyberpunkUI() if theme == "cyberpunk" else SpaceUI()
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Telegram setup
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if self.telegram_token:
            self.telegram = Application.builder().token(self.telegram_token).build()
        
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG

    def fetch_miners(self, min_hashrate: float = 0) -> List[AirdropRecipient]:
        """Fetch miners from SIGSCORE API."""
        try:
            response = requests.get(self.SIGSCORE_API)
            response.raise_for_status()
            miners = response.json()
            
            recipients = [
                AirdropRecipient(
                    address=miner['address'],
                    amount=0,
                    hashrate=miner['hashrate']
                )
                for miner in miners
                if miner['hashrate'] >= min_hashrate
            ]
            
            self.logger.info(f"Found {len(recipients)} eligible miners")
            return recipients
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch miners: {e}")
            raise

    def get_token_data(self, token_name: str) -> Tuple[str, int]:
        """Get token ID and decimals from supported tokens list."""
        df = pd.read_csv('https://raw.githubusercontent.com/marctheshark3/Mining-Reward-Tokens/main/supported-tokens.csv')
        token_row = df[df['Token Name'] == token_name]
        if token_row.empty:
            raise ValueError(f"Token {token_name} not found in supported tokens list.")
        
        token_id = token_row['Token ID'].values[0]
        decimals = int(token_row['Token decimals'].values[0])
        return token_id, decimals

    async def send_telegram_notification(self, message: str):
        """Send notification message to Telegram."""
        if self.telegram_token and self.telegram_chat_id:
            try:
                await self.telegram.bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                self.logger.error(f"Failed to send Telegram message: {e}")

    def send_telegram_message_sync(self, message: str):
        """Synchronous wrapper for telegram message sending."""
        if self.telegram_token:
            # asyncio.run(self.send_telegram_notification(message))
            pass

    def validate_recipients(self, recipients: List[AirdropRecipient]) -> bool:
        """Validate recipient list."""
        if not recipients:
            self.logger.error("No recipients provided")
            return False
        
        total_amount = sum(r.amount for r in recipients)
        if total_amount <= 0:
            self.logger.error("Total airdrop amount must be greater than 0")
            return False
            
        return True

    def execute_airdrop(self, token_name: str, amount_per_recipient: float, min_hashrate: float = 0, debug: bool = True) -> Dict:
        try:
            # self.ui.display_help()
            self.ui.display_assumptions()
            # to do add a sleep for about 10 seconds to give the user the time to read the assumptions
            
            self.ui.log_info("Initializing airdrop mission...")
            token_id, token_decimals = self.get_token_data(token_name)
            
            token_units = int(amount_per_recipient * (10 ** token_decimals))
            if token_units <= 0:
                raise ValueError(f"Token amount too small. Minimum is {1/(10 ** token_decimals)} {token_name}")
            
            recipients = self.fetch_miners(min_hashrate) 
            
            for recipient in recipients:
                recipient.amount = token_units
                
            if not self.validate_recipients(recipients):
                self.ui.log_error("Invalid recipients configuration")
                return {"status": "failed", "error": "invalid_recipients"}
    
            total_token_amount = sum(r.amount for r in recipients)
            total_erg_needed = self.builder.estimate_transaction_cost(len(recipients))
            human_readable_total = total_token_amount / (10 ** token_decimals)
            
            self.ui.display_summary(
                token_name=token_name,
                recipients_count=len(recipients),
                total_amount=human_readable_total,
                total_erg=total_erg_needed,
                total_hashrate=sum(r.hashrate for r in recipients),
                decimals=token_decimals
            )
    
            erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
            human_readable_balance = token_balances.get(token_id, 0) / (10 ** token_decimals)
            
            self.ui.display_wallet_balance(
                token_name=token_name,
                erg_balance=erg_balance,
                token_balance=human_readable_balance,
                decimals=token_decimals
            )
    
            if debug:
                self.ui.log_warning("Debug mode active - No transaction will be created")
                return {
                    "status": "debug",
                    "recipients": len(recipients),
                    "total_tokens": human_readable_total,
                    "total_erg": total_erg_needed,
                    "total_hashrate": sum(r.hashrate for r in recipients)
                }
    
            if not self.ui.display_confirmation_prompt(30):
                return {"status": "cancelled", "error": "user_cancelled"}
    
            try:
                self.ui.log_info("Preparing transaction outputs...")
                outputs = [
                    OutputBox(
                        address=recipient.address,
                        erg_value=self.min_box_value,
                        tokens=[{
                            'tokenId': token_id,
                            'amount': recipient.amount
                        }]
                    )
                    for recipient in recipients
                ]
    
                self.ui.log_info("Initiating transaction...")
                tx_id = self.builder.create_multi_output_tx(outputs, self.wallet_address)
                
                explorer_base = self.explorer_url.replace('/api/v1', '')
                explorer_link = f"{explorer_base}/transactions/{tx_id}"
                
                self.ui.display_success(tx_id, explorer_link)
                
                success_msg = f"""
<b>🚀 Airdrop Mission Complete</b>
<b>Token</b>: {token_name}
<b>Recipients</b>: {len(recipients)}
<b>Amount per recipient</b>: {amount_per_recipient:,.{token_decimals}f} {token_name}
<b>Total Amount</b>: {human_readable_total:,.{token_decimals}f} {token_name}
<b>Total ERG</b>: {total_erg_needed:,.4f} ERG
<b>Total Hashrate</b>: {sum(r.hashrate for r in recipients):,.0f}
<b>Transaction</b>: <a href="{explorer_link}">{tx_id[:6]}...{tx_id[-6:]}</a>
"""
                self.send_telegram_message_sync(success_msg)
    
                return {
                    "status": "completed",
                    "tx_id": tx_id,
                    "recipients": len(recipients),
                    "explorer_url": explorer_link
                }
    
            except Exception as e:
                self.ui.log_error(f"Transaction failed: {e}")
                self.send_telegram_message_sync(f"❌ Airdrop failed: {str(e)}")
                return {"status": "failed", "error": str(e)}
    
        except Exception as e:
            self.ui.log_error(f"Mission failed: {e}")
            self.send_telegram_message_sync(f"❌ Airdrop failed: {str(e)}")
            return {"status": "failed", "error": str(e)}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Airdrop tokens to miners.')
    parser.add_argument('token_name', help='Name of token to airdrop')
    parser.add_argument('amount_per_recipient', type=float, help='Amount per recipient')
    parser.add_argument('--min-hashrate', type=float, default=0, help='Minimum hashrate filter')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--theme', choices=['cyberpunk', 'space'], default='space', help='UI theme')
    
    args = parser.parse_args()
    
    try:
        airdrop = TokenAirdrop(theme=args.theme)
        result = airdrop.execute_airdrop(
            token_name=args.token_name,
            amount_per_recipient=args.amount_per_recipient,
            min_hashrate=args.min_hashrate,
            debug=args.debug
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()