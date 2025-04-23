import os
import requests
from typing import List, Dict
import json
from decimal import Decimal, ROUND_DOWN
import logging
from pathlib import Path
from dotenv import load_dotenv
import time

ERG_TO_NANOERG = int(1e9)
MIN_BOX_VALUE = int(os.getenv('MIN_BOX_VALUE', 0.001 * ERG_TO_NANOERG))
TX_FEE = int(os.getenv('TX_FEE', 0.001 * ERG_TO_NANOERG))
DEFAULT_POOL_FEE_PERCENTAGE = '0.01'
DEFAULT_POOL_FEE_ADDRESS = "9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt"

class BlockHeightCollector:
    def __init__(self, wallet_address: str = None):
        self.api_base = os.getenv('ERGO_API_BASE', "https://api.ergoplatform.com/api/v1")
        self.miners_api_url = os.getenv('MINERS_API', "http://5.78.102.130:8000/sigscore/miners/average-participation")
        self.wallet_address = wallet_address or os.getenv('WALLET_ADDRESS')
        self.logger = logging.getLogger(__name__)
        
        if not self.wallet_address:
            raise ValueError("Wallet address must be provided either as an argument or via WALLET_ADDRESS environment variable")

    def get_latest_outgoing_block(self) -> int:
        try:
            self.logger.info(f"Fetching transactions for address: {self.wallet_address}")
            
            # Initial fetch with smaller limit for efficiency
            response = requests.get(
                f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                params={"offset": 0, "limit": 50}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("items"):
                self.logger.info("No transactions found")
                return 0
            
            # Check the first batch of transactions
            for tx in data["items"]:
                inputs = tx.get("inputs", [])
                if any(input_box.get("address") == self.wallet_address for input_box in inputs):
                    self.logger.info(f"Found latest outgoing block: {tx['inclusionHeight']}")
                    return tx["inclusionHeight"]
            
            # If we have more transactions than our initial fetch, paginate through them
            total_txs = data.get("total", 0)
            if total_txs > 50:
                self.logger.info(f"Found {total_txs} total transactions, checking more...")
                
                # Paginate through transactions in batches
                max_batches = min(10, (total_txs + 99) // 100)  # Limit to 10 batches (1000 txs) to avoid excessive API calls
                for batch in range(1, max_batches + 1):
                    offset = batch * 50
                    
                    # Add a small delay to avoid rate limiting
                    time.sleep(0.2)
                    
                    try:
                        response = requests.get(
                            f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                            params={"offset": offset, "limit": 50}
                        )
                        response.raise_for_status()
                        batch_data = response.json()
                        
                        for tx in batch_data.get("items", []):
                            inputs = tx.get("inputs", [])
                            if any(input_box.get("address") == self.wallet_address for input_box in inputs):
                                self.logger.info(f"Found latest outgoing block: {tx['inclusionHeight']}")
                                return tx["inclusionHeight"]
                    except requests.exceptions.RequestException as e:
                        self.logger.warning(f"Error fetching batch {batch}: {e}. Moving to next batch.")
                        continue
                
                self.logger.info(f"No outgoing transactions found after checking {max_batches * 50} transactions")
            else:
                self.logger.info("No outgoing transactions found in the first 50 transactions")
            
            return 0
        except Exception as e:
            self.logger.error(f"Error finding latest outgoing transaction: {e}", exc_info=True)
            raise

    def get_blocks_since_last_outgoing(self) -> List[int]:
        try:
            min_block = self.get_latest_outgoing_block()
            self.logger.info(f"Starting from block height: {min_block}")
            
            if min_block == 0:
                 self.logger.warning("No outgoing transaction found. Cannot determine starting block height.")
                 return []
                
            all_blocks = set()
            current_offset = 0
            limit = 100
            max_pages = 20
            page_count = 0

            while page_count < max_pages:
                self.logger.debug(f"Fetching transactions page {page_count + 1} with offset {current_offset}")
                try:
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
                except requests.exceptions.RequestException as e:
                     self.logger.error(f"API error fetching transactions: {e}. Stopping block fetch.")
                     break

                items = data.get("items", [])
                if not items:
                    self.logger.debug("No more transactions found")
                    break
                    
                new_blocks_found_in_page = False
                for tx in items:
                    height = tx.get("inclusionHeight", 0)
                    if height > min_block:
                        if height not in all_blocks:
                             all_blocks.add(height)
                             new_blocks_found_in_page = True

                total_txs = data.get("total", 0)
                if current_offset + len(items) >= total_txs:
                     self.logger.debug("Reached reported end of transactions based on total count.")
                     break

                current_offset += limit
                page_count += 1
                time.sleep(0.1)

            if page_count == max_pages:
                 self.logger.warning(f"Reached max page limit ({max_pages}) fetching transactions. Results might be incomplete.")

            result = sorted(list(all_blocks))
            self.logger.info(f"Found {len(result)} blocks since height {min_block}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching blocks: {e}", exc_info=True)
            return []

    def fetch_miners_data(self, block_heights: List[int]) -> Dict:
        if not block_heights:
             self.logger.warning("fetch_miners_data called with empty block_heights list.")
             return {'miners': []}
             
        try:
            self.logger.info(f"Fetching miners data for {len(block_heights)} blocks using {self.miners_api_url}")
            block_params = ",".join(map(str, block_heights))
            
            response = requests.get(
                self.miners_api_url,
                params={"blocks": block_params}
            )
            response.raise_for_status()
            data = response.json()
            miner_count = len(data.get('miners', []))
            self.logger.info(f"Found {miner_count} miners in response")
            return data
        except requests.exceptions.RequestException as e:
             self.logger.error(f"HTTP error fetching miners data: {e}", exc_info=True)
             return {'miners': []}
        except json.JSONDecodeError as e:
             self.logger.error(f"Error decoding JSON response from miners API: {e}", exc_info=True)
             return {'miners': []}
        except Exception as e:
            self.logger.error(f"Unexpected error fetching miners data: {e}", exc_info=True)
            raise

    def generate_distribution(self, miners_data: Dict, miner_distribution_amount: Decimal, token_name: str, pool_fee_amount: Decimal, pool_fee_address: str) -> Dict:
        miner_distribution_amount = Decimal(str(miner_distribution_amount))
        pool_fee_amount = Decimal(str(pool_fee_amount))
        
        miners = miners_data.get('miners', [])
        if not miners:
            self.logger.info("No miners data provided for distribution calculation.")
            recipients = []
            if pool_fee_amount > 0 and pool_fee_address:
                 recipients.append({
                     "address": pool_fee_address,
                     "amount": float(pool_fee_amount.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
                 })
            else:
                 self.logger.warning("Pool fee amount is zero or address is missing, not adding pool fee recipient.")
            return {"distributions": [{"token_name": token_name, "recipients": recipients}]}

        total_percentage = sum(Decimal(str(miner.get('avg_participation_percentage', 0))) for miner in miners)
        self.logger.info(f"Total participation percentage from miners data: {total_percentage}")
        
        recipients = []
        if total_percentage > 0 and miner_distribution_amount > 0:
            miner_dist_amount_dec = Decimal(str(miner_distribution_amount))
            
            allocated_sum = Decimal(0)
            
            for i, miner in enumerate(miners):
                address = miner.get('miner_address')
                percentage_str = str(miner.get('avg_participation_percentage', 0))
                
                if not address:
                    self.logger.warning(f"Miner data missing address at index {i}. Skipping.")
                    continue
                    
                percentage = Decimal(percentage_str)
                
                amount_dec = (miner_dist_amount_dec * (percentage / total_percentage)).quantize(
                    Decimal('0.00000001'), rounding=ROUND_DOWN
                )
                
                if amount_dec > 0:
                    recipients.append({
                        "address": address,
                        "amount": float(amount_dec)
                    })
                    allocated_sum += amount_dec
                else:
                    self.logger.debug(f"Calculated amount for {address} is zero or negative. Skipping.")

            if abs(allocated_sum - miner_dist_amount_dec) > Decimal('0.000001'):
                 self.logger.warning(f"Sum allocated to miners ({allocated_sum:.8f}) differs from target ({miner_dist_amount_dec:.8f}) due to rounding.")
                 
        elif miner_distribution_amount <= 0:
             self.logger.info("Miner distribution amount is zero or negative. No miners will receive funds from this pool.")
        else:
             self.logger.warning("Total participation percentage is zero. Cannot distribute based on participation.")

        # Add pool fee recipient if the amount is greater than 0 and address is valid
        self.logger.debug(f"Checking condition to add pool fee: Amount={pool_fee_amount:.8f} (>0?), Address='{pool_fee_address}' (non-empty?)")
        if pool_fee_amount > 0 and pool_fee_address:
             self.logger.debug(f"Condition TRUE. Adding pool fee recipient: {pool_fee_address}")
             recipients.append({
                 "address": pool_fee_address,
                 "amount": float(pool_fee_amount.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
             })
        elif pool_fee_amount > 0:
             self.logger.warning("Pool fee amount calculated but no pool fee address provided. Pool fee will not be included.")

        result = {
            "distributions": [{
                "token_name": token_name,
                "recipients": recipients
            }]
        }
        self.logger.info(f"Generated distribution for {len(recipients)} total recipients (miners + pool fee).")
        return result

    def save_distribution_json(self, distribution: Dict, filename: str | Path) -> None:
        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(distribution, f, indent=2)
            self.logger.info(f"Saved distribution to {filepath}")
        except IOError as e:
             self.logger.error(f"Error writing distribution file to {filepath}: {e}", exc_info=True)
        except Exception as e:
             self.logger.error(f"Unexpected error saving distribution JSON: {e}", exc_info=True)