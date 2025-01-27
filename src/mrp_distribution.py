# src/mrp_distribution.py
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
        self.emission_amount = float(os.getenv('BLOCK_REWARD', '0'))
        self.rights_token_id = os.getenv('RIGHTS_TOKEN_ID')
        self.emission_token_name = os.getenv('EMISSION_TOKEN_NAME')
        self.output_file = os.getenv('OUTPUT_FILE', 'MRP.json')
        self.pool_fee_percent = float(os.getenv('POOL_FEE_PERCENT', '1.0'))
        self.protocol_fee_percent = float(os.getenv('PROTOCOL_FEE_PERCENT', '1.0'))
        self.pool_address = os.getenv('POOL_ADDRESS')
        self.protocol_address = os.getenv('PROTOCOL_ADDRESS')

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

    def calculate_fees(self) -> tuple[float, float, float]:
        pool_fee = self.emission_amount * (self.pool_fee_percent / 100)
        protocol_fee = self.emission_amount * (self.protocol_fee_percent / 100)
        remaining_amount = self.emission_amount - pool_fee - protocol_fee
        return pool_fee, protocol_fee, remaining_amount

    def generate_distribution(self, miners_data: Dict) -> Dict:
        pool_fee, protocol_fee, remaining_amount = self.calculate_fees()
        
        eligible_miners = []
        total_eligible_percentage = Decimal('0')
        
        # Filter eligible miners
        for miner in miners_data['miners']:
            if self.check_wallet_balance(miner['miner_address'], self.rights_token_id):
                eligible_miners.append(miner)
                total_eligible_percentage += Decimal(str(miner['avg_participation_percentage']))
        
        recipients = []
        
        # Add pool fee recipient if configured
        if self.pool_address and pool_fee > 0:
            recipients.append({
                "address": self.pool_address,
                "amount": pool_fee
            })
            
        # Add protocol fee recipient if configured
        if self.protocol_address and protocol_fee > 0:
            recipients.append({
                "address": self.protocol_address,
                "amount": protocol_fee
            })

        if total_eligible_percentage > 0:
            for miner in eligible_miners:
                adjusted_percentage = (Decimal(str(miner['avg_participation_percentage'])) / 
                                     total_eligible_percentage * 100)
                amount = round(float(Decimal(str(remaining_amount)) * 
                                   (adjusted_percentage / Decimal('100'))), 8)
                
                if amount > 0:
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