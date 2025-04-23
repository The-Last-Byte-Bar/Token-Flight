import time
from typing import List, Dict
import requests
from dataclasses import dataclass

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class BlockMonitor:
    def __init__(self, api_url: str, last_processed_height: int = 0):
        self.api_url = api_url
        self.last_processed_height = last_processed_height
        self.min_confirmations = 1.0
        
    def get_new_confirmed_blocks(self) -> List[Block]:
        try:
            response = requests.get(self.api_url)
            blocks = response.json()
            
            confirmed_blocks = []
            for block in blocks:
                # Skip if already processed
                if block['blockheight'] <= self.last_processed_height:
                    continue
                    
                # Check confirmation progress
                if block['confirmationprogress'] >= self.min_confirmations:
                    confirmed_blocks.append(Block(
                        height=block['blockheight'],
                        confirmation_progress=block['confirmationprogress'],
                        created=block['created']
                    ))
            
            # Sort by height to ensure proper order
            confirmed_blocks.sort(key=lambda x: x.height)
            return confirmed_blocks
            
    def process_blocks(self):
        while True:
            new_blocks = self.get_new_confirmed_blocks()
            
            for block in new_blocks:
                # Process block with MRP
                print(f"Processing block {block.height}")
                
                # Your MRP code here
                # 1. Get participation data
                # 2. Check token holdings
                # 3. Calculate distribution
                # 4. Execute airdrop
                
                # Update last processed height
                self.last_processed_height = block.height
            
            time.sleep(60)  # Check every minute

# Usage
monitor = BlockMonitor(
    api_url="http://5.78.102.130:8000/miningcore/blocks",
    last_processed_height=1446000  # Starting height
)
monitor.process_blocks()