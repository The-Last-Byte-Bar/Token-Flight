# src/mrp_service.py
import time
import logging
from typing import List, Dict, Optional, Tuple
import requests
from dataclasses import dataclass
from mrp_distribution import MinerRightsProtocol
from airdrop import BaseAirdrop
from models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
import os

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class MRPService:
    def __init__(self):
        self.api_url = "http://5.78.102.130:8000/miningcore/blocks"
        self.height_file = "last_height.txt"
        self.min_confirmations = 1.0
        self.check_interval = 1200  # 20 minutes
        self.mrp = MinerRightsProtocol()
        self.logger = logging.getLogger(__name__)
        
        # Load last processed height
        self.last_processed_height = self._load_last_height()
        
        # Configure wallet
        self.wallet_config = WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            node_api_key=os.getenv('NODE_API_KEY'),
            node_wallet_address=os.getenv('WALLET_ADDRESS')
        )

    def _load_last_height(self) -> int:
        try:
            if os.path.exists(self.height_file):
                with open(self.height_file, 'r') as f:
                    return int(f.read().strip())
            return int(os.getenv('STARTING_BLOCK_HEIGHT', '0'))
        except Exception as e:
            self.logger.error(f"Error loading height: {e}")
            return int(os.getenv('STARTING_BLOCK_HEIGHT', '0'))

    def _save_last_height(self, height: int):
        try:
            with open(self.height_file, 'w') as f:
                f.write(str(height))
        except Exception as e:
            self.logger.error(f"Error saving height: {e}")

    def get_new_confirmed_blocks(self) -> List[Block]:
        try:
            response = requests.get(self.api_url)
            blocks_data = response.json()
            
            # Add debug logging
            self.logger.debug(f"API Response: {blocks_data}")
            
            confirmed_blocks = []
            # Handle both list and dictionary response formats
            blocks = blocks_data if isinstance(blocks_data, list) else blocks_data.get('blocks', [])
            
            for block in blocks:
                # Safely access fields with get()
                height = block.get('blockheight') or block.get('height')
                progress = block.get('confirmationprogress') or block.get('confirmations', 0)
                created = block.get('created') or block.get('timestamp')
                
                if not height or height <= self.last_processed_height:
                    continue
                    
                if progress >= self.min_confirmations:
                    confirmed_blocks.append(Block(
                        height=height,
                        confirmation_progress=float(progress),
                        created=created
                    ))
            
            confirmed_blocks.sort(key=lambda x: x.height)
            return confirmed_blocks
                
        except Exception as e:
            self.logger.error(f"Error fetching blocks: {str(e)}", exc_info=True)
            return []

    def execute_distribution(self, block_height: int) -> Optional[str]:
        try:
            # Generate MRP distribution
            distribution = self.mrp.execute([block_height])
            
            if not distribution['distributions'][0]['recipients']:
                self.logger.info("No eligible recipients found")
                return None
            
            # Convert recipients to RecipientAmount objects
            recipients = [
                RecipientAmount(
                    address=r['address'],
                    amount=float(r['amount'])
                )
                for r in distribution['distributions'][0]['recipients']
            ]
            
            # Configure airdrop
            token_config = TokenConfig(
                token_name=os.getenv('EMISSION_TOKEN_NAME'),
                recipients=recipients
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

    def run(self):
        self.logger.info(f"Starting MRP Service... Last processed height: {self.last_processed_height}")
        
        while True:
            try:
                new_blocks = self.get_new_confirmed_blocks()
                
                if not new_blocks:
                    self.logger.info(f"No new confirmed blocks found above height {self.last_processed_height}")
                    time.sleep(self.check_interval)
                    continue
                
                for block in new_blocks:
                    self.logger.info(f"Processing block {block.height}")
                    tx_id = self.execute_distribution(block.height)
                    
                    if tx_id:
                        self.logger.info(f"Distribution completed for block {block.height}. TX: {tx_id}")
                        self.last_processed_height = block.height
                        self._save_last_height(block.height)
                    
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = MRPService()
    service.run()