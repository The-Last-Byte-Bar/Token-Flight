import os
import logging
import json
import random
from pathlib import Path
from typing import List, Dict, Optional
import requests

from src.models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from src.multi_output_builder import MultiOutputBuilder
from src.nft_airdrop import NFTAirdrop

class NFTService:
    def __init__(self, wallet_address: str):
        """Initialize NFT service
        
        Args:
            wallet_address: The wallet address containing the NFTs to distribute
        """
        self.wallet_address = wallet_address
        self.setup_logging()
        self.wallet_config = self.load_wallet_config()
        
        # Initialize builder with individual config values
        self.builder = MultiOutputBuilder(
            node_url=self.wallet_config.node_url,
            network_type=self.wallet_config.network_type,
            explorer_url=self.wallet_config.explorer_url,
            node_api_key=self.wallet_config.node_api_key,
            wallet_mnemonic=self.wallet_config.wallet_mnemonic
        )
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "nft_airdrop.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_wallet_config(self) -> WalletConfig:
        """Load wallet configuration from environment variables"""
        return WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            wallet_mnemonic=os.getenv('WALLET_MNEMONIC')
        )

    def get_token_info(self, token_id: str) -> Optional[Dict]:
        """Get token information from explorer API
        
        Args:
            token_id: The token ID to look up
            
        Returns:
            Token information or None if not found
        """
        try:
            explorer_url = self.wallet_config.explorer_url.rstrip('/')
            response = requests.get(f"{explorer_url}/tokens/{token_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching token info for {token_id}: {str(e)}")
            return None

    def get_nft_tokens(self, collection_name: str = "Ergobotz") -> List[Dict]:
        """Get NFT tokens from the specified wallet for a given collection
        
        Args:
            collection_name: Name of the NFT collection to filter
            
        Returns:
            List of NFT tokens with their IDs and metadata
        """
        try:
            # Get wallet balances using transaction builder
            erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
            
            # Filter for NFTs from the collection
            nft_tokens = []
            total_nfts = 0
            
            for token_id, amount in token_balances.items():
                # Get token info from explorer
                token_info = self.get_token_info(token_id)
                if token_info and token_info.get('name', '').startswith(collection_name):
                    nft_data = {
                        'tokenId': token_id,
                        'amount': amount,
                        'name': token_info.get('name'),
                        'decimals': token_info.get('decimals', 0)
                    }
                    # Add the NFT data multiple times based on amount
                    for _ in range(amount):
                        nft_tokens.append(nft_data.copy())
                    total_nfts += amount
                    self.logger.info(f"Found NFT: {token_info.get('name')} ({token_id}) - Amount: {amount}")
            
            self.logger.info(f"Found {len(set(t['tokenId'] for t in nft_tokens))} unique NFTs with total {total_nfts} tokens from collection {collection_name}")
            return nft_tokens
            
        except Exception as e:
            self.logger.error(f"Error fetching NFTs: {str(e)}")
            raise

    def prepare_nft_distribution(self, recipient_addresses: List[str], 
                               collection_name: str = "Ergobotz") -> Dict:
        """Prepare NFT distribution by randomly assigning NFTs to recipients
        
        Args:
            recipient_addresses: List of recipient addresses
            collection_name: Name of the NFT collection to distribute
            
        Returns:
            Distribution configuration compatible with the airdrop system
        """
        try:
            # Get available NFTs (this now includes duplicates based on amount)
            nft_tokens = self.get_nft_tokens(collection_name)
            
            if len(nft_tokens) < len(recipient_addresses):
                raise ValueError(
                    f"Not enough NFTs ({len(nft_tokens)} total tokens) "
                    f"for all recipients ({len(recipient_addresses)})"
                )
            
            # Randomly assign NFTs to recipients
            selected_nfts = random.sample(nft_tokens, len(recipient_addresses))
            
            # Create distribution configuration
            distribution = {
                "distributions": []
            }
            
            # Group recipients by token ID
            token_recipients = {}
            for address, nft in zip(recipient_addresses, selected_nfts):
                token_id = nft['tokenId']
                if token_id not in token_recipients:
                    token_recipients[token_id] = []
                token_recipients[token_id].append({
                    "address": address,
                    "amount": 1,
                    "token_id": token_id
                })
            
            # Create a distribution entry for each token ID
            for token_id, recipients in token_recipients.items():
                nft_info = next(nft for nft in nft_tokens if nft['tokenId'] == token_id)
                distribution["distributions"].append({
                    "token_name": collection_name,
                    "token_id": token_id,
                    "name": nft_info['name'],
                    "recipients": recipients
                })
            
            # Save distribution to file
            output_file = f"nft_distribution_{collection_name.lower().replace(' ', '_')}.json"
            with open(output_file, 'w') as f:
                json.dump(distribution, f, indent=2)
            
            self.logger.info(f"Distribution configuration saved to {output_file}")
            return distribution
            
        except Exception as e:
            self.logger.error(f"Error preparing NFT distribution: {str(e)}")
            raise

    def execute_nft_airdrop(self, recipient_addresses: List[str], 
                           collection_name: str = "Ergobotz",
                           debug: bool = False) -> Dict:
        """Execute NFT airdrop to recipients
        
        Args:
            recipient_addresses: List of recipient addresses
            collection_name: Name of the NFT collection to distribute
            debug: If True, run in debug mode without executing transaction
            
        Returns:
            Transaction result
        """
        try:
            # Prepare distribution
            distribution = self.prepare_nft_distribution(recipient_addresses, collection_name)
            
            # Configure airdrop
            tokens = []
            
            # Create token configs for each NFT distribution
            for dist in distribution['distributions']:
                token_id = dist['token_id']
                token_name = f"{collection_name} #{token_id}"  # Use unique name for each NFT
                
                # Create recipient list for this NFT
                recipients = [
                    RecipientAmount(
                        address=r['address'],
                        amount=r['amount']
                    )
                    for r in dist['recipients']
                ]
                
                # Add token config
                tokens.append(TokenConfig(
                    token_name=token_name,
                    token_id=token_id,
                    recipients=recipients
                ))
                
                self.logger.info(f"Prepared distribution for {dist['name']} to {len(recipients)} recipients")
            
            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=tokens,
                headless=True,
                debug=debug
            )
            
            # Execute airdrop using NFTAirdrop
            airdrop = NFTAirdrop(config=airdrop_config)
            
            # Set token IDs for each NFT
            for token in tokens:
                airdrop.set_token_id(token.token_name, token.token_id)
                self.logger.info(f"Set token ID mapping: {token.token_name} -> {token.token_id}")
            
            result = airdrop.execute()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing NFT airdrop: {str(e)}")
            raise 