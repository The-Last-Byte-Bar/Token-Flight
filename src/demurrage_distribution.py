import os
import requests
from typing import List, Dict
import json
from decimal import Decimal

ERG_TO_NANOERG = int(1e9)
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)
TX_FEE = int(0.001 * ERG_TO_NANOERG)

class BlockHeightCollector:
    def __init__(self, wallet_address: str = None):
        self.api_base = "https://api.ergoplatform.com/api/v1"
        self.wallet_address = wallet_address or os.getenv('WALLET_ADDRESS')

    def get_latest_outgoing_block(self) -> int:
        try:
            response = requests.get(
                f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                params={"offset": 0, "limit": 50}
            )
            response.raise_for_status()
            
            for tx in response.json()["items"]:
                if any(input_data.get("address") == self.wallet_address 
                       for input_data in tx.get("inputs", [])):
                    return tx["inclusionHeight"]
            return 0
        except Exception as e:
            print(f"Error finding latest outgoing transaction: {e}")
            return 0

    def get_blocks_since_last_outgoing(self) -> List[int]:
        try:
            min_block = self.get_latest_outgoing_block()
            
            if not min_block:
                return []
                
            all_blocks = set()
            current_offset = 0
            limit = 100
            
            while True:
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
                    break
                    
                for tx in data["items"]:
                    if tx.get("inclusionHeight", 0) > min_block:
                        all_blocks.add(tx["inclusionHeight"])
                        
                if len(data["items"]) < limit:
                    break
                    
                current_offset += limit
                
            return sorted(list(all_blocks))
        except Exception as e:
            print(f"Error fetching blocks: {e}")
            return []

    def fetch_miners_data(self, block_heights: List[int]) -> Dict:
        response = requests.get(
            "http://5.78.102.130:8000/sigscore/miners/average-participation",
            params={"blocks": ",".join(map(str, block_heights))}
        )
        response.raise_for_status()
        return response.json()

    def generate_distribution(self, miners_data: Dict, distribution_amount: float, token_name: str) -> Dict:
        if not miners_data.get('miners'):
            return {"distributions": [{"token_name": token_name, "recipients": []}]}

        total_percentage = sum(miner['avg_participation_percentage'] for miner in miners_data['miners'])
        
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

        return {
            "distributions": [{
                "token_name": token_name,
                "recipients": recipients
            }]
        }

    def save_distribution_json(self, distribution: Dict, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(distribution, f, indent=2)

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