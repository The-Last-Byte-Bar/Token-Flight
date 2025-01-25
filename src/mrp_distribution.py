import os
from dotenv import load_dotenv
import json
import requests
from typing import List, Dict
from decimal import Decimal

# Load environment variables
load_dotenv()

class MinerRightsProtocol:
    def __init__(self):
        self.emission_amount = float(os.getenv('TOTAL_EMISSION', '0'))
        self.rights_token_id = os.getenv('RIGHTS_TOKEN_ID')
        self.emission_token_name = os.getenv('EMISSION_TOKEN_NAME')
        self.output_file = os.getenv('OUTPUT_FILE', 'MRP.json')

    @staticmethod
    def check_wallet_balance(address: str, token_id: str) -> bool:
        try:
            response = requests.get(f"https://api.ergoplatform.com/api/v1/addresses/{address}/balance/confirmed")
            response.raise_for_status()
            return any(token['tokenId'] == token_id for token in response.json().get('tokens', []))
        except Exception as e:
            print(f"Error checking balance for {address}: {str(e)}")
            return False

    @staticmethod
    def fetch_miners_data(block_heights: List[int]) -> Dict:
        response = requests.get(f"http://5.78.102.130:8000/sigscore/miners/average-participation?blocks={','.join(map(str, block_heights))}")
        response.raise_for_status()
        return response.json()

    def generate_distribution(self, miners_data: Dict) -> Dict:
        eligible_miners = []
        total_eligible_percentage = Decimal('0')
        
        # Filter eligible miners
        for miner in miners_data['miners']:
            if self.check_wallet_balance(miner['miner_address'], self.rights_token_id):
                eligible_miners.append(miner)
                total_eligible_percentage += Decimal(str(miner['avg_participation_percentage']))
        
        recipients = []
        if total_eligible_percentage > 0:
            for miner in eligible_miners:
                adjusted_percentage = (Decimal(str(miner['avg_participation_percentage'])) / 
                                     total_eligible_percentage * 100)
                amount = round(float(Decimal(str(self.emission_amount)) * 
                                   (adjusted_percentage / Decimal('100'))), 8)
                
                if amount > 0:
                    # Create RecipientAmount compatible format
                    recipients.append({
                        "address": miner['miner_address'],
                        "amount": amount
                    })
        
        return {
            "distributions": [{
                "token_name": self.emission_token_name,
                "recipients": recipients
            }]
        }
    def save_distribution(self, distribution: Dict) -> None:
        with open(self.output_file, 'w') as f:
            json.dump(distribution, f, indent=2)

    def execute(self, block_heights: List[int]) -> Dict:
        miners_data = self.fetch_miners_data(block_heights)
        distribution = self.generate_distribution(miners_data)
        self.save_distribution(distribution)
        return distribution

# Example usage:
# mrp = MinerRightsProtocol()
# distribution = mrp.execute([1417531])