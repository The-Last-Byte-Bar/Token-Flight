import time
import logging
from typing import List, Dict, Optional, Tuple
import requests
from dataclasses import dataclass
from demurrage_distribution import BlockHeightCollector
from airdrop import BaseAirdrop
from models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
import os
from decimal import Decimal, ROUND_DOWN

ERG_TO_NANOERG = int(1e9)
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)
TX_FEE = int(0.001 * ERG_TO_NANOERG)
WALLET_BUFFER = int(0.001 * ERG_TO_NANOERG)  # Keep some ERG for future transactions

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class DemurrageService:
    def __init__(self, debug: bool = False):
        self.api_url = "https://api.ergoplatform.com/api/v1"
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        
        # Configure wallet with mnemonic
        self.wallet_config = WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            wallet_mnemonic=os.getenv('WALLET_MNEMONIC'),
            mnemonic_password=os.getenv('MNEMONIC_PASSWORD', ''),
            node_wallet_address=os.getenv('WALLET_ADDRESS')
        )
        
        # Initialize collector with wallet address
        self.collector = BlockHeightCollector('9fE5o7913CKKe6wvNgM11vULjTuKiopPcvCaj7t2zcJWXM2gcLu')
        if not self.collector.wallet_address:
            raise ValueError("WALLET_ADDRESS environment variable is required")

    def get_wallet_balance(self) -> float:
        try:
            response = requests.get(
                f"{self.api_url}/addresses/{self.wallet_config.node_wallet_address}/balance/confirmed"
            )
            response.raise_for_status()
            return response.json().get('nanoErgs', 0) / ERG_TO_NANOERG
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {e}")
            return 0

    def calculate_transaction_costs(self, recipient_count: int) -> Tuple[float, float]:
        """Calculate transaction costs and available amount for distribution.
        
        Returns:
            Tuple[float, float]: (total_fees, min_box_total)
        """
        # Calculate minimum box values needed for all recipients
        min_box_total = MIN_BOX_VALUE * recipient_count
        
        # Total fees include:
        # 1. Minimum box values for all recipients
        # 2. Transaction fee
        # 3. Wallet buffer for future transactions
        # 4. Change box minimum value
        total_costs = min_box_total + TX_FEE + WALLET_BUFFER + MIN_BOX_VALUE  # Added MIN_BOX_VALUE for change box
        
        return total_costs / ERG_TO_NANOERG, min_box_total / ERG_TO_NANOERG

    def calculate_distribution_amount(self, recipient_count: int) -> float:
        wallet_balance = self.get_wallet_balance()
        self.logger.info(f"Current wallet balance: {wallet_balance} ERG")
        
        total_costs, min_box_total = self.calculate_transaction_costs(recipient_count)
        self.logger.info(f"Transaction costs breakdown:")
        self.logger.info(f"- Minimum box value per recipient: {MIN_BOX_VALUE/ERG_TO_NANOERG} ERG")
        self.logger.info(f"- Total minimum box values ({recipient_count} recipients): {min_box_total} ERG")
        self.logger.info(f"- Transaction fee: {TX_FEE/ERG_TO_NANOERG} ERG")
        self.logger.info(f"- Wallet buffer: {WALLET_BUFFER/ERG_TO_NANOERG} ERG")
        self.logger.info(f"- Total costs: {total_costs} ERG")
        
        # Convert to Decimal for precise calculation
        wallet_balance_dec = Decimal(str(wallet_balance))
        total_costs_dec = Decimal(str(total_costs))
        
        # This is the amount available for actual distribution (excluding min box values)
        available_for_distribution = float((wallet_balance_dec - total_costs_dec).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
        
        if available_for_distribution <= 0:
            raise ValueError(
                f"Insufficient balance for distribution.\n"
                f"Required: {total_costs} ERG (total costs)\n"
                f"Available: {wallet_balance} ERG"
            )
        
        self.logger.info(f"Available for distribution: {available_for_distribution} ERG")
        return available_for_distribution

    def execute_distribution(self, block_heights: List[int]) -> Optional[str]:
        try:
            self.logger.info("Starting distribution execution")
            miners_data = self.collector.fetch_miners_data(block_heights)
            recipient_count = len(miners_data.get('miners', []))
            
            if not recipient_count:
                self.logger.info("No eligible recipients found")
                return None
                
            self.logger.info(f"Found {recipient_count} eligible recipients")
            distribution_amount = self.calculate_distribution_amount(recipient_count)
            self.logger.info(f"Calculated distribution amount: {distribution_amount} ERG")
            
            distribution = self.collector.generate_distribution(miners_data, distribution_amount, "ERG")
            
            if not distribution['distributions'][0]['recipients']:
                self.logger.info("No recipients in distribution")
                return None
            
            # Convert recipients to RecipientAmount objects
            recipients = []
            for r in distribution['distributions'][0]['recipients']:
                # Just use the calculated share amount - min box value is already accounted for
                share_amount = float(Decimal(str(r['amount'])).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
                recipients.append(RecipientAmount(
                    address=r['address'],
                    amount=share_amount
                ))
            
            # Log some distribution statistics
            total_amount = sum(r.amount for r in recipients)
            min_amount = min(r.amount for r in recipients)
            max_amount = max(r.amount for r in recipients)
            self.logger.info(f"Distribution statistics:")
            self.logger.info(f"- Total recipients: {len(recipients)}")
            self.logger.info(f"- Total amount to be sent: {total_amount} ERG")
            self.logger.info(f"- Min amount per recipient: {min_amount} ERG")
            self.logger.info(f"- Max amount per recipient: {max_amount} ERG")
            self.logger.info(f"- Amount remaining after distribution: {WALLET_BUFFER/ERG_TO_NANOERG} ERG")
            
            # Configure airdrop
            token_config = TokenConfig(
                token_name="ERG",
                recipients=recipients
            )
            
            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=[token_config],
                headless=True,
                debug=self.debug
            )
            
            if self.debug:
                self.logger.info("Debug mode: Simulating transaction")
                self.logger.info("Distribution simulation completed successfully")
                return "debug-mode-no-tx"
            
            # Execute airdrop
            self.logger.info("Executing airdrop transaction")
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute()
            
            return result.tx_id if result.status == "completed" else None
            
        except Exception as e:
            self.logger.error(f"Error executing distribution: {e}")
            return None