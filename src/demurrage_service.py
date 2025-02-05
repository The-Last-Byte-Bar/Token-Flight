import time
import logging
from typing import List, Dict, Optional
import requests
from dataclasses import dataclass
from demurrage_distribution import BlockHeightCollector
from airdrop import BaseAirdrop
from models import AirdropConfig, TokenConfig, WalletConfig
import os
from decimal import Decimal

ERG_TO_NANOERG = int(1e9)
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)
TX_FEE = int(0.001 * ERG_TO_NANOERG)

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class DemurrageService:
    def __init__(self, debug: bool = False):
        self.api_url = "https://api.ergoplatform.com/api/v1"
        self.collector = BlockHeightCollector()
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        self.last_run_time = 0  # Track last execution time
        
        # Configure wallet with mnemonic
        self.wallet_config = WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            wallet_mnemonic=os.getenv('WALLET_MNEMONIC'),
            mnemonic_password=os.getenv('MNEMONIC_PASSWORD', ''),
            address=os.getenv('WALLET_ADDRESS')
        )
        )

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

    def calculate_distribution_amount(self, recipient_count: int) -> float:
        wallet_balance = self.get_wallet_balance()
        total_fees = (TX_FEE + (MIN_BOX_VALUE * recipient_count)) / ERG_TO_NANOERG
        available_for_distribution = wallet_balance - total_fees
        
        if available_for_distribution <= 0:
            raise ValueError(f"Insufficient balance for distribution. Need {total_fees} ERG for fees")
            
        return available_for_distribution

    def execute_distribution(self, block_heights: List[int]) -> Optional[str]:
        try:
            miners_data = self.collector.fetch_miners_data(block_heights)
            recipient_count = len(miners_data.get('miners', []))
            
            if not recipient_count:
                self.logger.info("No eligible recipients found")
                return None
                
            distribution_amount = self.calculate_distribution_amount(recipient_count)
            distribution = self.collector.generate_distribution(miners_data, distribution_amount, "ERG")
            
            if not distribution['distributions'][0]['recipients']:
                self.logger.info("No recipients in distribution")
                return None
            
            # Configure airdrop
            token_config = TokenConfig(
                token_name="ERG",
                recipients=distribution['distributions'][0]['recipients']
            )
            
            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=[token_config],
                headless=True
            )
            
            # Execute airdrop
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute()
            
            return result.tx_id if result.status == "completed" else None
            
        except Exception as e:
            self.logger.error(f"Error executing distribution: {e}")
            return None

    def should_execute(self) -> bool:
        current_time = time.time()
        week_in_seconds = 7 * 24 * 60 * 60
        
        if current_time - self.last_run_time >= week_in_seconds:
            self.last_run_time = current_time
            return True
        return False

    def run(self):
        self.logger.info(f"Starting Demurrage Service in {'debug' if self.debug else 'production'} mode...")
        
        while True:
            try:
                if self.should_execute():
                    block_heights = self.collector.get_blocks_since_last_outgoing()
                    
                    if block_heights:
                        self.logger.info(f"Processing blocks: {block_heights}")
                        
                        if self.debug:
                            self.logger.info("Debug mode - simulating distribution")
                            wallet_balance = self.get_wallet_balance()
                            miners_data = self.collector.fetch_miners_data(block_heights)
                            recipient_count = len(miners_data.get('miners', []))
                            distribution_amount = self.calculate_distribution_amount(recipient_count)
                            
                            self.logger.info(f"Wallet balance: {wallet_balance} ERG")
                            self.logger.info(f"Recipients: {recipient_count}")
                            self.logger.info(f"Distribution amount: {distribution_amount} ERG")
                            continue
                            
                        tx_id = self.execute_distribution(block_heights)
                        if tx_id:
                            self.logger.info(f"Distribution completed. TX: {tx_id}")
                    
                time.sleep(3600)  # Check every hour
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(300)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = DemurrageService()
    service.run()