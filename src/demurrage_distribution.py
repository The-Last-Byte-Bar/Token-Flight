import os
import requests
from typing import List, Dict
import json
from decimal import Decimal
import logging

ERG_TO_NANOERG = int(1e9)
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)
TX_FEE = int(0.001 * ERG_TO_NANOERG)

class BlockHeightCollector:
    def __init__(self, wallet_address: str = None):
        self.api_base = "https://api.ergoplatform.com/api/v1"
        self.wallet_address = wallet_address or os.getenv('WALLET_ADDRESS')
        self.logger = logging.getLogger(__name__)
        
        if not self.wallet_address:
            raise ValueError("Wallet address must be provided")

    def get_latest_outgoing_block(self) -> int:
        try:
            self.logger.info(f"Fetching transactions for address: {self.wallet_address}")
            response = requests.get(
                f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                params={"offset": 0, "limit": 50}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("items"):
                self.logger.info("No transactions found")
                return 0
            
            for tx in data["items"]:
                if any(input_data.get("address") == self.wallet_address 
                       for input_data in tx.get("inputs", [])):
                    self.logger.info(f"Found latest outgoing block: {tx['inclusionHeight']}")
                    return tx["inclusionHeight"]
                    
            self.logger.info("No outgoing transactions found")
            return 0
        except Exception as e:
            self.logger.error(f"Error finding latest outgoing transaction: {e}", exc_info=True)
            raise

    def get_blocks_since_last_outgoing(self) -> List[int]:
        try:
            min_block = self.get_latest_outgoing_block()
            self.logger.info(f"Starting from block height: {min_block}")
            
            if not min_block:
                self.logger.info("No minimum block height found")
                return []
                
            all_blocks = set()
            current_offset = 0
            limit = 100
            
            while True:
                self.logger.debug(f"Fetching transactions with offset {current_offset}")
                response = requests.get(
                    f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                    params={
                        "offset": current_offset,
                        "limit": limit,
                        "concise": True
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if not data["items"]:
                    self.logger.debug("No more transactions found")
                    break
                    
                for tx in data["items"]:
                    height = tx.get("inclusionHeight", 0)
                    if height > min_block:
                        all_blocks.add(height)
                        
                if len(data["items"]) < limit:
                    self.logger.debug("Reached end of transactions")
                    break
                    
                current_offset += limit
                
            result = sorted(list(all_blocks))
            self.logger.info(f"Found {len(result)} blocks since height {min_block}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching blocks: {e}", exc_info=True)
            raise

    def fetch_miners_data(self, block_heights: List[int]) -> Dict:
        try:
            self.logger.info(f"Fetching miners data for blocks: {block_heights}")
            response = requests.get(
                "http://5.78.102.130:8000/sigscore/miners/average-participation",
                params={"blocks": ",".join(map(str, block_heights))}
            )
            response.raise_for_status()
            data = response.json()
            self.logger.info(f"Found {len(data.get('miners', []))} miners")
            return data
        except Exception as e:
            self.logger.error(f"Error fetching miners data: {e}", exc_info=True)
            raise

    def generate_distribution(self, miners_data: Dict, distribution_amount: float, token_name: str) -> Dict:
        if not miners_data.get('miners'):
            self.logger.info("No miners data available for distribution")
            return {"distributions": [{"token_name": token_name, "recipients": []}]}

        total_percentage = sum(miner['avg_participation_percentage'] for miner in miners_data['miners'])
        self.logger.info(f"Total participation percentage: {total_percentage}")
        
        recipients = []
        if total_percentage > 0:
            for miner in miners_data['miners']:
                percentage = miner['avg_participation_percentage'] / total_percentage
                amount = round(distribution_amount * percentage, 8)
                
                if amount > 0:
                    recipients.append({
                        "address": miner['miner_address'],
                        "amount": amount
                    })

        result = {
            "distributions": [{
                "token_name": token_name,
                "recipients": recipients
            }]
        }
        self.logger.info(f"Generated distribution for {len(recipients)} recipients")
        return result

    def save_distribution_json(self, distribution: Dict, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(distribution, f, indent=2)
        self.logger.info(f"Saved distribution to {filename}")

def main():
    collector = BlockHeightCollector()
    block_heights = collector.get_blocks_since_last_outgoing()
    
    if not block_heights:
        print("No blocks found since last outgoing transaction")
        return
    
    try:
        miners_data = collector.fetch_miners_data(block_heights)
        
        # Calculate available amount for distribution
        response = requests.get(
            f"{collector.api_base}/addresses/{collector.wallet_address}/balance/confirmed"
        )
        wallet_balance = response.json().get('nanoErgs', 0) / ERG_TO_NANOERG
        recipient_count = len(miners_data.get('miners', []))
        total_fees = (TX_FEE + (MIN_BOX_VALUE * recipient_count)) / ERG_TO_NANOERG
        distribution_amount = wallet_balance - total_fees

        if distribution_amount <= 0:
            print(f"Insufficient balance for distribution. Need {total_fees} ERG for fees")
            return

        distribution = collector.generate_distribution(miners_data, distribution_amount, "ERG")
        output_file = f"distribution_{len(block_heights)}_blocks.json"
        collector.save_distribution_json(distribution, output_file)
        print(f"Distribution saved to {output_file}")
        
    except Exception as e:
        print(f"Error processing distribution: {e}")

if __name__ == "__main__":
    main()