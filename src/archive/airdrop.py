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
from decimal import Decimal
from env_config import EnvironmentConfig
from error_handler import setup_error_handler, ErrorHandler
from multi_output_builder import MultiOutputBuilder, OutputBox
from ui.space_ui import SpaceUI
from recipient_manager import RecipientManager, AirdropRecipient
from art.animations import SpaceAnimation
from wallet_manager import WalletManager

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
        
        # Set up logging first
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Load and validate config
        self.config = EnvironmentConfig.load()
        self.logger.debug("Environment config loaded")
        
        # Store configuration  
        self.node_url = self.config['node_url']
        self.network_type = self.config['network_type']
        self.explorer_url = self.config['explorer_url']
        
        # Initialize builder based on available credentials
        self.builder = MultiOutputBuilder(
            node_url=self.config['node_url'],
            network_type=self.config['network_type'],
            explorer_url=self.config['explorer_url']
        )
        
        # Configure wallet based on available credentials
        self._configure_wallet()
        
        # Set up UI components
        self.ui = SpaceUI()
        self.animator = SpaceAnimation(self.ui.console)
        self.min_box_value = MIN_BOX_VALUE / ERG_TO_NANOERG

    def _configure_wallet(self):
        """Configure wallet based on available credentials"""
        # Start with checking for mnemonic
        mnemonic = self.config.get('wallet_mnemonic')
        if mnemonic:
            self.logger.info("Configuring wallet with mnemonic...")
            self.builder.wallet_manager.configure_mnemonic(
                mnemonic=mnemonic,
                password=self.config.get('mnemonic_password', '')
            )
            _, self.wallet_address = self.builder.wallet_manager.get_signing_config()
            return

        # Fall back to node wallet if available
        node_api_key = self.config.get('node_api_key')
        node_wallet_address = self.config.get('node_wallet_address')
        if node_api_key and node_wallet_address:
            self.logger.info("Configuring wallet with node...")
            self.builder.ergo.apiKey = node_api_key
            self.builder.wallet_manager.configure_node_address(node_wallet_address)
            self.wallet_address = node_wallet_address
            return

        raise ValueError(
            "No valid wallet configuration found. Please provide either:\n"
            "1. WALLET_MNEMONIC (and optionally MNEMONIC_PASSWORD) or\n"
            "2. NODE_API_KEY and NODE_WALLET_ADDRESS"
        )

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
        """Execute the airdrop with the given parameters."""
        try:
            self.logger.debug(f"Starting airdrop execution for {token_name}")
            self.ui.display_welcome()
            self.ui.display_assumptions()
            
            # Get wallet configuration
            use_node, active_address = self.builder.wallet_manager.get_signing_config()
            self.logger.debug(f"Using {'node' if use_node else 'mnemonic'} signing with address: {active_address}")
            
            # Get token details
            is_erg = token_name.upper() in ['ERG', 'ERGO']
            token_id, token_decimals = self.get_token_data(token_name)
            self.logger.debug(f"Token details - ID: {token_id}, Decimals: {token_decimals}")
            
            # Calculate amounts
            self.logger.debug("Calculating distribution amounts...")
            amounts = self.prepare_amounts(
                total_amount=total_amount,
                amount_per_recipient=amount_per_recipient,
                recipient_count=len(recipients),
                decimals=token_decimals
            )
            
            # Create output boxes
            self.logger.debug("Creating output boxes...")
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
            
            # Calculate and display totals
            total_amount_actual = sum(amount / (10 ** token_decimals) for amount in amounts)
            total_erg_needed = total_amount_actual if is_erg else self.builder.estimate_transaction_cost(len(recipients))
            
            self.logger.debug(f"Total amount: {total_amount_actual} {token_name}")
            self.logger.debug(f"Total ERG needed: {total_erg_needed}")
            
            self.ui.display_summary(
                token_name=token_name,
                recipients_count=len(recipients),
                total_amount=total_amount_actual,
                total_erg=total_erg_needed,
                total_hashrate=sum(r.hashrate for r in recipients),
                decimals=token_decimals
            )
            
            # Check balances
            self.logger.debug("Checking wallet balances...")
            erg_balance, token_balances = self.builder.get_wallet_balances(active_address)
            human_readable_balance = (
                erg_balance if is_erg 
                else token_balances.get(token_id, 0) / (10 ** token_decimals)
            )
            
            self.logger.debug(f"ERG Balance: {erg_balance}")
            self.logger.debug(f"Token Balance: {human_readable_balance}")
            
            self.ui.display_wallet_balance(
                token_name=token_name,
                erg_balance=erg_balance,
                token_balance=human_readable_balance,
                decimals=token_decimals
            )
            
            if debug:
                self.logger.info("Running in debug mode - no transaction will be created")
                return {
                    "status": "debug",
                    "recipients": len(recipients),
                    "total_amount": total_amount_actual,
                    "total_erg": total_erg_needed,
                    "signing_method": "node" if use_node else "mnemonic",
                    "active_address": active_address,
                    "distribution": list(zip(
                        [r.address for r in recipients],
                        [a / (10 ** token_decimals) for a in amounts]
                    ))
                }
            
            # Check balances against required amounts
            if erg_balance < total_erg_needed:
                raise ValueError(
                    f"Insufficient ERG balance. Required: {total_erg_needed:.4f}, "
                    f"Available: {erg_balance:.4f}"
                )
            
            if not is_erg and human_readable_balance < total_amount_actual:
                raise ValueError(
                    f"Insufficient {token_name} balance. Required: {total_amount_actual:,.{token_decimals}f}, "
                    f"Available: {human_readable_balance:,.{token_decimals}f}"
                )
            
            if not self.ui.display_confirmation_prompt(30):
                return {"status": "cancelled", "error": "user_cancelled"}
            
            self.logger.debug("Creating transaction...")
            tx_id = self.builder.create_multi_output_tx(outputs, active_address)
            
            explorer_base = self.explorer_url.rstrip('/').replace('/api/v1', '')
            explorer_link = f"{explorer_base}/transactions/{tx_id}"
            
            self.logger.info(f"Transaction created successfully: {tx_id}")
            self.ui.display_success(tx_id, explorer_link)
            
            return {
                "status": "completed",
                "tx_id": tx_id,
                "recipients": len(recipients),
                "explorer_url": explorer_link,
                "signing_method": "node" if use_node else "mnemonic",
                "active_address": active_address
            }
            
        except Exception as e:
            self.logger.error(f"Airdrop execution failed: {str(e)}", exc_info=True)
            self.ui.display_error(f"Mission failed: {str(e)}")
            return {
                "status": "failed", 
                "error": str(e), 
                "signing_method": "node" if 'use_node' in locals() else "unknown",
                "active_address": active_address if 'active_address' in locals() else None
            }

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
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize error handler
        error_handler = setup_error_handler()
        
        # Initialize airdrop
        airdrop = TokenAirdrop()
        
        # Get recipients based on input method
        if args.recipient_list:
            recipients = RecipientManager.from_csv(args.recipient_list)
        elif args.addresses:
            recipients = RecipientManager.from_list(args.addresses)
        else:
            recipients = RecipientManager.from_miners(args.min_hashrate)
        
        # Execute airdrop
        result = airdrop.execute_airdrop(
            token_name=args.token_name,
            recipients=recipients,
            total_amount=args.total_amount,
            amount_per_recipient=args.amount_per_recipient,
            debug=args.debug
        )
        
        if result["status"] not in ["completed", "debug"]:
            sys.exit(1)
            
    except GracefulExit as e:
        print(f"\nGracefully exiting: {str(e)}")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()