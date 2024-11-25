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
import time
import argparse

from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.space_ui import SpaceUI
from recipient_manager import RecipientManager, AirdropRecipient
from art.animations import SpaceAnimation
from token_distributor import TokenDistributor, DistributionConfig

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value

class TokenAirdrop:
    def __init__(self):
        load_dotenv()
        
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
        
        self.builder = MultiOutputBuilder(
            node_url=self.node_url,
            network_type=self.network_type,
            explorer_url=self.explorer_url,
            node_api_key=self.node_api_key
        )
        
        self.ui = SpaceUI()
        self.animator = SpaceAnimation(self.ui.console)
        self.distributor = TokenDistributor()
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if self.telegram_token:
            self.telegram = Application.builder().token(self.telegram_token).build()
        
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG

    async def send_telegram_notification(self, message: str):
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
        if self.telegram_token:
            asyncio.run(self.send_telegram_notification(message))

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

    def prepare_distribution(self, token_name: str, recipients: List[AirdropRecipient],
                           total_amount: Optional[float] = None,
                           amount_per_recipient: Optional[float] = None) -> List[AirdropRecipient]:
        """Prepare token distribution using the TokenDistributor."""
        token_id, decimals = self.get_token_data(token_name)
        
        # Create distribution config
        config = DistributionConfig(
            token_name=token_name,
            total_amount=total_amount,
            amount_per_recipient=amount_per_recipient,
            decimals=decimals,
            min_amount=self.min_box_value if token_name.upper() in ['ERG', 'ERGO'] else 1
        )
        
        # Calculate distribution amounts
        amounts = self.distributor.calculate_distribution(
            config=config,
            recipient_count=len(recipients)
        )
        
        # Update recipient amounts
        for recipient, amount in zip(recipients, amounts):
            recipient.amount = amount
            
        return recipients

    def execute_airdrop(self, token_name: str, recipients: List[AirdropRecipient], 
                       total_amount: Optional[float] = None,
                       amount_per_recipient: Optional[float] = None,
                       debug: bool = True) -> Dict:
        try:
            self.ui.display_welcome()
            self.ui.display_assumptions()
            self.ui.log_info("Please review the Know Your Assumptions (KYA) checklist carefully...")
            time.sleep(10)
            
            self.ui.log_info("Initializing airdrop mission...")
            
            # Check if we're dealing with ERG or a token
            is_erg = token_name.upper() in ['ERG', 'ERGO']
            token_id, token_decimals = self.get_token_data(token_name)
            
            # Prepare distribution
            recipients = self.prepare_distribution(
                token_name=token_name,
                recipients=recipients,
                total_amount=total_amount,
                amount_per_recipient=amount_per_recipient
            )
            
            # Preview distribution
            preview = self.distributor.preview_distribution(
                config=DistributionConfig(
                    token_name=token_name,
                    total_amount=total_amount,
                    amount_per_recipient=amount_per_recipient,
                    decimals=token_decimals
                ),
                recipient_count=len(recipients)
            )
            
            total_amount = preview['total_amount']
            
            # Calculate total ERG needed
            if is_erg:
                total_erg_needed = total_amount
            else:
                total_erg_needed = self.builder.estimate_transaction_cost(len(recipients))
            
            self.ui.display_summary(
                token_name=token_name,
                recipients_count=len(recipients),
                total_amount=total_amount,
                total_erg=total_erg_needed,
                total_hashrate=sum(r.hashrate for r in recipients),
                decimals=token_decimals
            )
    
            # Check balances
            erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
            if is_erg:
                human_readable_balance = erg_balance
            else:
                human_readable_balance = token_balances.get(token_id, 0) / (10 ** token_decimals)
            
            self.ui.display_wallet_balance(
                token_name=token_name,
                erg_balance=erg_balance,
                token_balance=human_readable_balance,
                decimals=token_decimals
            )
    
            if debug:
                self.ui.log_warning("Debug mode active - No transaction will be created")
                try:
                    self.ui.log_info("Testing animations...")
                    self.animator.launch_animation()
                    self.ui.display_success("DEBUG_TX_ID", "https://explorer.ergoplatform.com/")
                    self.animator.success_animation()
                except Exception as e:
                    self.ui.log_error(f"Animation test error: {str(e)}")
                
                return {
                    "status": "debug",
                    "recipients": len(recipients),
                    "total_amount": total_amount,
                    "total_erg": total_erg_needed,
                    "total_hashrate": sum(r.hashrate for r in recipients),
                    "distribution_preview": preview
                }
    
            if not self.ui.display_confirmation_prompt(30):
                return {"status": "cancelled", "error": "user_cancelled"}
    
            try:
                self.ui.log_info("Preparing transaction outputs...")
                
                # Create outputs differently for ERG vs tokens
                if is_erg:
                    outputs = [
                        OutputBox(
                            address=recipient.address,
                            erg_value=recipient.amount / ERG_TO_NANOERG,
                            tokens=None
                        )
                        for recipient in recipients
                    ]
                else:
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
                
                explorer_base = self.explorer_url.rstrip('/').replace('/api/v1', '')
                explorer_link = f"{explorer_base}/transactions/{tx_id}"
                
                try:
                    self.animator.launch_animation()
                    self.ui.display_success(tx_id, explorer_link)
                    self.animator.success_animation()
                except Exception as e:
                    self.ui.log_error(f"Animation error: {e}")
                
                success_msg = f"""
<b>🚀 Airdrop Mission Complete</b>
<b>{token_name}</b>: {token_name}
<b>Recipients</b>: {len(recipients)}
<b>Total Amount</b>: {total_amount:,.{token_decimals}f} {token_name}
<b>Total ERG Cost</b>: {total_erg_needed:,.4f} ERG
<b>Total Hashrate</b>: {sum(r.hashrate for r in recipients):,.0f}
<b>Transaction</b>: <a href="{explorer_link}">{tx_id[:6]}...{tx_id[-6:]}</a>
"""
                self.send_telegram_message_sync(success_msg)
    
                return {
                    "status": "completed",
                    "tx_id": tx_id,
                    "recipients": len(recipients),
                    "explorer_url": explorer_link,
                    "distribution_preview": preview
                }
    
            except Exception as e:
                self.ui.log_error(f"Transaction failed: {str(e)}")
                self.send_telegram_message_sync(f"❌ Airdrop failed: {str(e)}")
                return {"status": "failed", "error": str(e)}
    
        except Exception as e:
            self.ui.log_error(f"Mission failed: {str(e)}")
            self.send_telegram_message_sync(f"❌ Airdrop failed: {str(e)}")
            return {"status": "failed", "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Airdrop ERG or tokens to recipients.')
    parser.add_argument('token_name', help='Name of token to airdrop (use "ERG" for Ergo coin)')
    
    # Add mutually exclusive group for amount specification
    amount_group = parser.add_mutually_exclusive_group(required=True)
    amount_group.add_argument('--total-amount', type=float, help='Total amount to distribute')
    amount_group.add_argument('--amount-per-recipient', type=float, help='Amount per recipient')
    
    parser.add_argument('--min-hashrate', type=float, default=0, help='Minimum hashrate filter')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--recipient-list', help='Path to CSV file with recipients')
    parser.add_argument('--addresses', nargs='+', help='List of recipient addresses')
    args = parser.parse_args()
    
    try:
        airdrop = TokenAirdrop()
        
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
            debug=args.debug
        )
        
        if result["status"] not in ["completed", "debug"]:
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()