from dataclasses import dataclass
from typing import List, Optional
import requests
import pandas as pd

@dataclass
class AirdropRecipient:
    address: str
    amount: float
    hashrate: float = 0.0

class RecipientManager:
    """Manages different ways to create recipient lists"""
    SIGSCORE_API = 'http://5.78.102.130:8000/sigscore/miners?pageSize=5000'
    
    @staticmethod
    def from_miners(min_hashrate: float = 0) -> List[AirdropRecipient]:
        """Fetch miners from SIGSCORE API."""
        response = requests.get(RecipientManager.SIGSCORE_API)
        response.raise_for_status()
        miners = response.json()
        
        return [
            AirdropRecipient(
                address=miner['address'],
                amount=0,
                hashrate=miner['hashrate']
            )
            for miner in miners
            if miner['hashrate'] >= min_hashrate
        ]
    
    @staticmethod
    def from_csv(file_path: str) -> List[AirdropRecipient]:
        """Create recipient list from CSV file."""
        df = pd.read_csv(file_path)
        return [
            AirdropRecipient(
                address=row['address'],
                amount=row.get('amount', 0),
                hashrate=row.get('hashrate', 0)
            )
            for _, row in df.iterrows()
        ]
    
    @staticmethod
    def from_list(addresses: List[str], amount: float = 0) -> List[AirdropRecipient]:
        """Create recipient list from address list."""
        return [
            AirdropRecipient(address=addr, amount=amount)
            for addr in addresses
        ]