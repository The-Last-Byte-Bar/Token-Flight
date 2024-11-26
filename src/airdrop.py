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
import signal


from error_handler import setup_error_handler, ErrorHandler
from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.space_ui import SpaceUI
from recipient_manager import RecipientManager, AirdropRecipient
from art.animations import SpaceAnimation

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value

class AirdropError(Exception):
    """Base exception for airdrop-specific errors"""
    pass

class GracefulExit(Exception):
    """Exception for graceful exits"""
    pass

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    raise GracefulExit("Received interrupt signal")

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
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG

    def unlock_wallet(self) -> bool:
        """Attempt to unlock the node wallet"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'api_key': self.node_api_key
            }
            
            # First check if wallet is already unlocked
            status_url = f"{self.node_url}/wallet/status"
            status_response = requests.get(status_url, headers=headers)
            if status_response.status_code == 200:
                if status_response.json().get('isUnlocked', False):
                    return True
                
            # If not unlocked, try to unlock it (this assumes wallet is initialized)
            self.ui.log_info("Attempting to unlock wallet...")
            return True  # For now, assume success as actual unlocking would need password
            
        except Exception as e:
            self.logger.error(f"Failed to check/unlock wallet: {e}")
            return False

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
                       debug: bool = True) -> Dict:
        try:
            self.ui.display_welcome()
            self.ui.display_assumptions()
            self.ui.log_info("Please review the Know Your Assumptions (KYA) checklist carefully...")
            time.sleep(2)  # Reduced for testing
            
            self.ui.log_info("Initializing airdrop mission...")
            
            # Check wallet status
            if not debug and not self.unlock_wallet():
                raise ValueError("Unable to unlock wallet. Please ensure wallet is initialized and unlocked.")
            
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
            
            # Calculate totals for display
            total_amount_actual = sum(amount / (10 ** token_decimals) for amount in amounts)
            if is_erg:
                total_erg_needed = total_amount_actual
            else:
                total_erg_needed = self.builder.estimate_transaction_cost(len(recipients))
            
            self.ui.display_summary(
                token_name=token_name,
                recipients_count=len(recipients),
                total_amount=total_amount_actual,
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
                    "total_amount": total_amount_actual,
                    "total_erg": total_erg_needed,
                    "distribution": list(zip(
                        [r.address for r in recipients],
                        [a / (10 ** token_decimals) for a in amounts]
                    ))
                }
    
            if not self.ui.display_confirmation_prompt(30):
                return {"status": "cancelled", "error": "user_cancelled"}
    
            try:
                self.ui.log_info("Preparing transaction outputs...")
                
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
                
                return {
                    "status": "completed",
                    "tx_id": tx_id,
                    "recipients": len(recipients),
                    "explorer_url": explorer_link
                }
    
            except Exception as e:
                self.ui.log_error(f"Transaction failed: {str(e)}")
                return {"status": "failed", "error": str(e)}
    
        except Exception as e:
            self.ui.log_error(f"Mission failed: {str(e)}")
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