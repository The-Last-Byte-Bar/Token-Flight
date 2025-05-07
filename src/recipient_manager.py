from dataclasses import dataclass
from typing import List, Optional
import requests
import pandas as pd
import os
import logging

# Import the configuration model
from .config import AppConfig 

logger = logging.getLogger(__name__)

@dataclass
class AirdropRecipient:
    address: str
    amount: float
    hashrate: float = 0.0

class RecipientManager:
    """Manages different ways to create recipient lists"""
    # Removed hardcoded API URL
    # SIGSCORE_API = 'https://api.ergominers.com/sigscore/miners?pageSize=5000' 
    
    @staticmethod
    # Modified to accept AppConfig
    def from_miners(config: AppConfig, min_hashrate: float = 0) -> List[AirdropRecipient]: 
        """Fetch miners from SigScore API using configured settings."""
        # Get API key from config
        api_key = config.mining_wave_api_key 
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
        else:
            # Use the class logger, not instance logger for static method
            logger.warning("No MINING_WAVE_API_KEY found in config, making SigScore API request without authentication.") 

        # Get API URL from config
        sigscore_url = config.apis.sigscore_url 
        logger.debug(f"Fetching miners from {sigscore_url}")
        try:
            response = requests.get(sigscore_url, headers=headers, timeout=30)
            response.raise_for_status()
            miners = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching SigScore miners from {sigscore_url}: {e}", exc_info=True)
            return [] # Return empty list on error
        
        recipients = [
            AirdropRecipient(
                address=miner['address'],
                amount=0, # Amount is usually determined later
                hashrate=0 # Hashrate not directly available from this endpoint
            )
            for miner in miners
            if miner.get('address') # Ensure address exists
        ]
        logger.info(f"Retrieved {len(recipients)} miners from SigScore API.")
        return recipients
    
    @staticmethod
    def from_bonus_miners(config: AppConfig) -> List[AirdropRecipient]:
        """Fetch miners specifically from the bonus endpoint."""
        api_key = config.mining_wave_api_key
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
        else:
            logger.error("MINING_WAVE_API_KEY is required for the bonus miners endpoint but not found in config!")
            # Consider raising an error or returning empty based on requirements
            # For now, returning empty to prevent proceeding without auth
            return []
        
        bonus_miners_url = config.apis.miners_bonus_url
        logger.info(f"Fetching bonus miners from {bonus_miners_url}")
        try:
            response = requests.get(bonus_miners_url, headers=headers, timeout=30)
            response.raise_for_status()
            miners_data = response.json()
            
            # Assuming the API returns a list of objects, each with an 'address' field
            # Adjust based on the actual API response structure
            if not isinstance(miners_data, list):
                logger.error(f"Unexpected response format from bonus miners API. Expected list, got {type(miners_data).__name__}.")
                return []
                
            recipients = [
                AirdropRecipient(
                    address=miner['address'],
                    amount=0, # Amount calculated later
                    hashrate=0 # Hashrate likely not relevant/available here
                )
                for miner in miners_data
                if isinstance(miner, dict) and miner.get('address') # Basic validation
            ]
            
            logger.info(f"Retrieved {len(recipients)} miners from Bonus API.")
            return recipients
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching bonus miners from {bonus_miners_url}: {e}", exc_info=True)
            return [] # Return empty list on error
        except Exception as e:
            logger.error(f"Unexpected error processing bonus miners response: {e}", exc_info=True)
            return []
    
    @staticmethod
    def from_csv(file_path: str) -> List[AirdropRecipient]:
        """Create recipient list from CSV file."""
        logger.info(f"Loading recipients from CSV: {file_path}")
        try:
            df = pd.read_csv(file_path)
                # Basic validation
            if 'address' not in df.columns:
                raise ValueError("CSV file must contain an 'address' column.")
                
            recipients = [
            AirdropRecipient(
                address=row['address'],
                    amount=float(row.get('amount', 0)), # Ensure amount is float
                    hashrate=float(row.get('hashrate', 0)) # Ensure hashrate is float
            )
            for _, row in df.iterrows()
                if pd.notna(row['address']) # Skip rows with missing addresses
            ]
            logger.info(f"Loaded {len(recipients)} recipients from {file_path}")
            return recipients
        except FileNotFoundError:
            logger.error(f"CSV file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def from_list(addresses: List[str], amount: float = 0) -> List[AirdropRecipient]:
        """Create recipient list from address list."""
        logger.info(f"Creating recipient list from {len(addresses)} provided addresses.")
        return [
            AirdropRecipient(address=addr, amount=amount)
            for addr in addresses
            if isinstance(addr, str) and addr # Basic check for valid address strings
        ]
