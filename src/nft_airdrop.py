from typing import List, Dict, Optional, Union, Tuple
import logging

from src.base_airdrop import BaseAirdrop
from src.models import AirdropConfig, TokenConfig, WalletConfig, AirdropRecipient

class NFTAirdrop(BaseAirdrop):
    """Specialized airdrop class for NFT distributions"""
    
    def __init__(self, config: AirdropConfig):
        super().__init__(config)
        self.token_id_map = {}  # Cache for token ID mappings
        
    def set_token_id(self, token_name: str, token_id: str, decimals: int = 0):
        """Set token ID mapping for a given token name
        
        Args:
            token_name: Name of the token/collection
            token_id: The actual token ID from the blockchain
            decimals: Number of decimals for the token (usually 0 for NFTs)
        """
        self.token_id_map[token_name] = {
            'id': token_id,
            'decimals': decimals
        }
        
    def _get_token_data(self, token_name: str) -> Tuple[Optional[str], int]:
        """Override to use direct token ID mapping instead of CSV lookup"""
        if token_name.upper() in ['ERG', 'ERGO']:
            return None, 9
            
        if token_name not in self.token_id_map:
            raise ValueError(f"Token ID not set for {token_name}. Call set_token_id first.")
            
        token_data = self.token_id_map[token_name]
        return token_data['id'], token_data['decimals'] 