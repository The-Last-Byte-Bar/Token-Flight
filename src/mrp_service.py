# src/mrp_service.py
import time
import logging
from typing import List, Dict, Optional
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
        self.last_processed_height = int(os.getenv('STARTING_BLOCK_HEIGHT', '0'))
        self.min_confirmations = 1.0
        self.mrp = MinerRightsProtocol()
        self.logger = logging.getLogger(__name__)
        
        # Configure wallet
        self.wallet_config = WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            node_api_key=os.getenv('NODE_API_KEY'),
            node_wallet_address=os.getenv('WALLET_ADDRESS')
        )

    def get_new_confirmed_blocks(self) -> List[Block]:
        try:
            response = requests.get(self.api_url)
            blocks = response.json()
            
            confirmed_blocks = []
            for block in blocks:
                if block['blockheight'] <= self.last_processed_height:
                    continue
                    
                if block['confirmationprogress'] >= self.min_confirmations:
                    confirmed_blocks.append(Block(
                        height=block['blockheight'],
                        confirmation_progress=block['confirmationprogress'],
                        created=block['created']
                    ))
            
            confirmed_blocks.sort(key=lambda x: x.height)
            return confirmed_blocks
            
        except Exception as e:
            self.logger.error(f"Error fetching blocks: {e}")
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
        self.logger.info("Starting MRP Service...")
        
        while True:
            try:
                new_blocks = self.get_new_confirmed_blocks()
                
                for block in new_blocks:
                    self.logger.info(f"Processing block {block.height}")
                    tx_id = self.execute_distribution(block.height)
                    
                    if tx_id:
                        self.logger.info(f"Distribution completed for block {block.height}. TX: {tx_id}")
                    
                    self.last_processed_height = block.height
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = MRPService()
    service.run()