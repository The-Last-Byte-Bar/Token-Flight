import os
import requests
from typing import List, Dict
import json
from decimal import Decimal, ROUND_DOWN
import logging
from pathlib import Path
import time
from datetime import datetime, timezone

# Import the configuration model
from .config import AppConfig 

# Define a consistent limit for transaction fetching
# IMPORTANT: Do not lower this value below 200 as it affects block height collection
# Block heights 1509846, 1509996, 1510211, 1510299 appear at transactions 51-54
TRANSACTION_PAGE_LIMIT = 200

class BlockHeightCollector:
    # Modify __init__ to accept AppConfig
    def __init__(self, config: AppConfig): 
        # Set attributes from config object
        self.config = config
        self.api_base = config.apis.ergo_api_base
        self.miners_api_url = config.apis.miners_participation_url
        self.wallet_address = config.wallet.address
        self.logger = logging.getLogger(__name__)
        self.miners_api_key = config.mining_wave_api_key
        self.min_confirmations = config.service.min_confirmations
        
        # Validate required wallet address from config
        if not self.wallet_address:
            raise ValueError("Wallet address (WALLET_ADDRESS) must be configured in the environment or .env file")
            
        # Log warning if API key is missing (from config)
        if not self.miners_api_key:
             self.logger.warning("MINING_WAVE_API_KEY not found in config. Requests to the miners API might fail if authentication is required.")

    def get_latest_outgoing_block(self) -> int:
        # Uses self.api_base and self.wallet_address which are now set from config
        try:
            self.logger.info(f"Fetching transactions for address: {self.wallet_address}")
            
            # Initial fetch with smaller limit for efficiency
            response = requests.get(
                f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                params={"offset": 0, "limit": TRANSACTION_PAGE_LIMIT}
            )
            response.raise_for_status()
            data = response.json()
            
            self.logger.debug(f"API Response structure: {list(data.keys())}")
            
            if not data.get("items"):
                self.logger.info("No transactions found")
                return 0
                
            self.logger.info(f"Found {len(data.get('items', []))} transactions in initial batch, {data.get('total', 0)} total")
            
            # Check the first batch of transactions
            self.logger.debug(f"Checking initial {len(data.get('items', []))} transactions...")
            
            # Debug: log the first transaction's structure to understand the data format
            if data.get('items') and len(data.get('items')) > 0:
                first_tx = data['items'][0]
                self.logger.debug(f"First transaction structure: {list(first_tx.keys())}")
                self.logger.debug(f"First transaction inputs structure: {list(first_tx.get('inputs', [{}])[0].keys()) if first_tx.get('inputs') else 'No inputs'}")
            
            outgoing_count = 0
            for tx_index, tx in enumerate(data["items"]):
                tx_id = tx.get('id', 'unknown_id')
                height = tx.get('inclusionHeight', 'N/A')
                self.logger.debug(f"[{tx_index}] Checking tx {tx_id} at height: {height}")
                
                inputs = tx.get("inputs", [])
                if not inputs:
                    self.logger.debug(f"[{tx_index}] No inputs found for this transaction")
                    continue
                    
                # Log input addresses to verify what we're actually checking
                input_addresses = [input_box.get("address", "no_address") for input_box in inputs]
                self.logger.debug(f"[{tx_index}] Transaction input addresses: {input_addresses}")
                self.logger.debug(f"[{tx_index}] Looking for wallet address: {self.wallet_address}")
                
                if any(input_box.get("address") == self.wallet_address for input_box in inputs):
                    outgoing_count += 1
                    self.logger.info(f"Found outgoing tx: {tx_id} at block height: {tx['inclusionHeight']}")
                    return tx["inclusionHeight"]
                else:
                    self.logger.debug(f"[{tx_index}] Not an outgoing transaction (wallet address not found in inputs)")
            
            self.logger.info(f"No outgoing transactions found in initial batch. Found {outgoing_count} matching our criteria.")
            
            # If we have more transactions than our initial fetch, paginate through them
            total_txs = data.get("total", 0)
            if total_txs > TRANSACTION_PAGE_LIMIT:
                self.logger.info(f"Found {total_txs} total transactions, checking more...")
                
                # Paginate through transactions in batches
                # Limit batches slightly more aggressively
                max_batches = min(10, (total_txs + TRANSACTION_PAGE_LIMIT - 1) // TRANSACTION_PAGE_LIMIT) 
                self.logger.debug(f"Checking up to {max_batches} additional batches.")
                
                for batch in range(1, max_batches + 1): # Start from batch 1 (offset TRANSACTION_PAGE_LIMIT)
                    offset = batch * TRANSACTION_PAGE_LIMIT
                    
                    # Add a small delay to avoid rate limiting
                    time.sleep(0.2)
                    
                    try:
                        self.logger.debug(f"Fetching batch {batch} with offset {offset}")
                        response = requests.get(
                            f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                            params={"offset": offset, "limit": TRANSACTION_PAGE_LIMIT}
                        )
                        response.raise_for_status()
                        batch_data = response.json()
                        
                        batch_items = batch_data.get("items", [])
                        if not batch_items:
                            self.logger.info(f"No more transactions found at offset {offset}")
                            break # Stop if a batch returns empty
                            
                        self.logger.debug(f"  Checking {len(batch_items)} txs from batch offset {offset}")
                        
                        batch_outgoing_count = 0
                        for tx_index, tx in enumerate(batch_items):
                            tx_id = tx.get('id', 'unknown_id')
                            height = tx.get('inclusionHeight', 'N/A')
                            self.logger.debug(f"Batch[{batch}][{tx_index}] Checking tx {tx_id} at height: {height}")
                            
                            inputs = tx.get("inputs", [])
                            if not inputs:
                                self.logger.debug(f"Batch[{batch}][{tx_index}] No inputs found for this transaction")
                                continue
                                
                            # Log input addresses for this batch too
                            input_addresses = [input_box.get("address", "no_address") for input_box in inputs]
                            self.logger.debug(f"Batch[{batch}][{tx_index}] Transaction input addresses: {input_addresses}")
                            
                            if any(input_box.get("address") == self.wallet_address for input_box in inputs):
                                batch_outgoing_count += 1
                                self.logger.info(f"Found outgoing tx in batch {batch}: {tx_id} at height: {tx['inclusionHeight']}")
                                return tx["inclusionHeight"]
                            else:
                                self.logger.debug(f"Batch[{batch}][{tx_index}] Not an outgoing transaction")
                                
                        self.logger.debug(f"Batch {batch} complete. Found {batch_outgoing_count} outgoing transactions in this batch.")
                    except requests.exceptions.RequestException as e:
                        self.logger.warning(f"Error fetching batch {batch} (offset {offset}): {e}. Stopping pagination.")
                        break # Stop pagination on error
                
                self.logger.info(f"No outgoing transactions found after checking up to {max_batches} additional batches.")
            else:
                # This case means total_txs <= TRANSACTION_PAGE_LIMIT and none were outgoing
                self.logger.info(f"No outgoing transactions found within the first {total_txs} transactions.") 
            
            return 0
        except Exception as e:
            self.logger.error(f"Error finding latest outgoing transaction: {e}", exc_info=True)
            raise

    def get_blocks_since_last_outgoing(self, override_min_block: int = None) -> List[int]:
        # Uses self.api_base and self.wallet_address internally via get_latest_outgoing_block()
        try:
            # Use the override value if provided (for testing), otherwise get from API
            min_block = override_min_block if override_min_block is not None else self.get_latest_outgoing_block()
            self.logger.info(f"Starting from block height: {min_block}")
            
            if min_block == 0:
                 self.logger.warning("No outgoing transaction found. Cannot determine starting block height.")
                 
                 # Add debug information about the wallet activity (using self.api_base)
                 try:
                     response = requests.get(
                         f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                         params={"offset": 0, "limit": 5}
                     )
                     response.raise_for_status()
                     data = response.json()
                     
                     if data.get("items"):
                         self.logger.debug(f"Wallet has {data.get('total', 0)} total transactions")
                         self.logger.debug(f"Sample most recent transactions:")
                         for i, tx in enumerate(data.get("items", [])[:5]):
                             tx_id = tx.get('id', 'unknown_id')
                             height = tx.get('inclusionHeight', 'N/A')
                             tx_type = "Outgoing" if any(input_box.get("address") == self.wallet_address for input_box in tx.get("inputs", [])) else "Incoming/Other"
                             self.logger.debug(f"  {i+1}. {tx_type} TX {tx_id} at height {height}")
                     else:
                         self.logger.debug("No transactions found for this wallet")
                 except Exception as e:
                     self.logger.debug(f"Could not fetch sample transactions for diagnostics: {e}")
                 
                 return []
                
            all_blocks = set()
            current_offset = 0
            limit = TRANSACTION_PAGE_LIMIT  # Use the constant
            max_pages = 20 # Keep pagination limit reasonable
            page_count = 0

            self.logger.debug(f"Searching for blocks after height {min_block} from transactions of {self.wallet_address}")

            while page_count < max_pages:
                self.logger.debug(f"Fetching transactions page {page_count + 1} with offset {current_offset}")
                try:
                    response = requests.get(
                        f"{self.api_base}/addresses/{self.wallet_address}/transactions",
                        params={
                            "offset": current_offset,
                            "limit": limit,
                            "concise": True # Use concise=True if API supports it for less data
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                except requests.exceptions.RequestException as e:
                     self.logger.error(f"API error fetching transactions page {page_count+1}: {e}. Stopping block fetch.")
                     break # Stop on API error

                items = data.get("items", [])
                if not items:
                    self.logger.debug("No more transactions found")
                    break
                
                self.logger.debug(f"Processing {len(items)} transactions from page {page_count + 1}")
                    
                new_blocks_found_in_page = False
                blocks_in_page = []
                stop_searching = False
                for tx in items:
                    height = tx.get("inclusionHeight", 0)
                    # We can stop if we see transactions at or below min_block
                    # This assumes transactions are roughly ordered by height descending
                    if height <= min_block:
                         self.logger.debug(f"Reached transaction at or below target height {min_block}. Stopping search.")
                         stop_searching = True
                         break
                         
                    blocks_in_page.append(height)
                    if height not in all_blocks:
                            all_blocks.add(height)
                            new_blocks_found_in_page = True
                
                if blocks_in_page:
                    self.logger.debug(f"Page {page_count + 1} contained blocks > {min_block}: {sorted(blocks_in_page)}")
                    self.logger.debug(f"Found {len(blocks_in_page)} blocks in this page, {len(all_blocks)} unique blocks so far")
                else:
                    self.logger.debug(f"No eligible blocks (> {min_block}) found in page {page_count + 1}")

                if stop_searching:
                     break

                total_txs = data.get("total", 0) # Note: total might be inaccurate with concise?
                # Check if we've processed all items reported by this page
                if len(items) < limit:
                     self.logger.debug(f"Received less than limit items ({len(items)} < {limit}), assuming end of transactions.")
                     break # Assume we reached the end if API returns fewer than requested

                current_offset += limit
                page_count += 1
                time.sleep(0.1) # Keep small delay

            if page_count == max_pages:
                 self.logger.warning(f"Reached max page limit ({max_pages}) fetching transactions. Results might be incomplete.")

            result = sorted(list(all_blocks))
            self.logger.info(f"Found {len(result)} unique blocks since height {min_block}")
            if result:
                self.logger.debug(f"Block heights: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching blocks: {e}", exc_info=True)
            return []

    def fetch_miners_data(self, block_heights: List[int]) -> Dict:
        # Uses self.miners_api_url and self.miners_api_key from config
        if not block_heights:
             self.logger.warning("fetch_miners_data called with empty block_heights list.")
             return {'miners': []}
             
        try:
            headers = {}
            if self.miners_api_key:
                 headers['X-API-Key'] = self.miners_api_key
                 self.logger.debug("Using API key for miners API")
            # No warning here, already warned in __init__

            self.logger.info(f"Fetching miners data for {len(block_heights)} blocks using {self.miners_api_url}")
            block_params = ",".join(map(str, block_heights))
            
            # Log the first few block heights for debugging
            sample_blocks = block_heights[:5] if len(block_heights) > 5 else block_heights
            self.logger.debug(f"Sample block heights: {sample_blocks}...")
            
            # Prepare the full URL for logging
            full_url = f"{self.miners_api_url}?blocks={block_params}"
            self.logger.debug(f"Requesting URL: {full_url[:150]}... (truncated if long)")
            
            start_time = time.time()
            response = requests.get(
                self.miners_api_url,
                params={"blocks": block_params},
                headers=headers,
                timeout=60 # Add a timeout for potentially long requests
            )
            elapsed_time = time.time() - start_time
            
            self.logger.debug(f"API Response status code: {response.status_code}, Time: {elapsed_time:.2f}s")
            
            # Check for potential issues with the response
            if response.status_code != 200:
                self.logger.error(f"API Error: Status {response.status_code}, Response: {response.text[:500]}")
                response.raise_for_status() # Raise exception for bad status codes
                
            data = response.json()
            
            # Log the response structure
            if isinstance(data, dict):
                self.logger.debug(f"Response data structure keys: {list(data.keys())}")
                miner_count = len(data.get('miners', []))
                self.logger.info(f"Found {miner_count} miners in response")
                
                # Sample the first few miners
                if miner_count > 0:
                    sample_size = min(3, miner_count)
                    sample_miners = data.get('miners', [])[:sample_size]
                    self.logger.debug(f"Sample miners data (first {sample_size}):")
                    for i, miner in enumerate(sample_miners):
                        addr = miner.get('miner_address', 'no_address')
                        pct = miner.get('avg_participation_percentage', 0)
                        self.logger.debug(f"  {i+1}. Address: {addr[:10]}..., Participation: {pct}%")
            else:
                self.logger.error(f"Unexpected response format from miners API. Expected dict, got {type(data).__name__}")
                self.logger.debug(f"Response data preview: {str(data)[:500]}")
                return {'miners': []} # Return empty structure on format error
                
            return data
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout fetching miners data from {self.miners_api_url}", exc_info=True)
            return {'miners': []} # Return empty on timeout
        except requests.exceptions.RequestException as e:
             self.logger.error(f"HTTP error fetching miners data: {e}", exc_info=True)
             self.logger.debug(f"Request details: URL={self.miners_api_url}, Headers={headers}, Blocks count={len(block_heights)}")
             return {'miners': []} # Return empty on request error
        except json.JSONDecodeError as e:
             self.logger.error(f"Error decoding JSON response from miners API: {e}", exc_info=True)
             # Try to log the raw response for debugging
             try:
                 self.logger.debug(f"Raw response: {response.text[:1000]} (truncated)")
             except Exception:
                 self.logger.debug("Could not access raw response text after JSON error")
             return {'miners': []} # Return empty on JSON error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching miners data: {e}", exc_info=True)
            # Don't re-raise, return empty structure to allow service to potentially continue
            return {'miners': []} 

    def generate_distribution(self, miners_data: Dict, miner_distribution_amount: Decimal, token_name: str, pool_fee_amount: Decimal, pool_fee_address: str) -> Dict:
        # This method primarily performs calculations and doesn't directly use config
        # Ensure input types are Decimal for precision
        try:
            miner_distribution_amount = Decimal(str(miner_distribution_amount))
            pool_fee_amount = Decimal(str(pool_fee_amount))
        except Exception as e:
             self.logger.error(f"Invalid decimal amount provided to generate_distribution: {e}", exc_info=True)
             # Return empty distribution if amounts are invalid
             return {"distributions": []} 
        
        miners = miners_data.get('miners', [])
        if not miners:
            self.logger.info("No miners data provided for distribution calculation.")
            recipients = []
            if pool_fee_amount > 0 and pool_fee_address:
                 # Ensure amount is converted to float for the final structure
                 recipients.append({
                     "address": pool_fee_address,
                     "amount": float(pool_fee_amount.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
                 })
                 self.logger.info(f"Only pool fee recipient added: {pool_fee_address} with {pool_fee_amount:.8f}")
            else:
                 self.logger.warning("No miners and pool fee amount is zero or address is missing. No recipients generated.")
            return {"distributions": [{"token_name": token_name, "recipients": recipients}]}

        # Calculate total percentage using Decimal for accuracy
        total_percentage = Decimal(0)
        valid_miners = []
        for miner in miners:
             try:
                 # Ensure participation is treated as string before Decimal conversion
                 participation_str = str(miner.get('avg_participation_percentage', 0))
                 percentage = Decimal(participation_str)
                 if percentage < 0:
                      self.logger.warning(f"Miner {miner.get('miner_address', 'unknown')} has negative participation ({percentage}). Skipping.")
                      continue
                 if not miner.get('miner_address'):
                     self.logger.warning(f"Miner data missing address. Participation: {percentage}. Skipping.")
                     continue
                     
                 total_percentage += percentage
                 valid_miners.append(miner) # Store only miners with valid participation and address
             except Exception as e:
                 self.logger.warning(f"Could not parse participation for miner {miner.get('miner_address', 'unknown')}: {miner.get('avg_participation_percentage')}. Error: {e}. Skipping.")
                 continue
                 
        self.logger.info(f"Total valid participation percentage from {len(valid_miners)} miners: {total_percentage}")
        
        recipients = []
        if total_percentage > 0 and miner_distribution_amount > 0:
            self.logger.info(f"Distributing {miner_distribution_amount:.8f} {token_name} among {len(valid_miners)} miners based on participation.")
            allocated_sum = Decimal(0)
            
            for i, miner in enumerate(valid_miners):
                address = miner.get('miner_address') # Already validated this exists
                # Use the already validated Decimal percentage
                try:
                    participation_str = str(miner.get('avg_participation_percentage', 0))
                    percentage = Decimal(participation_str)
                except: # Should not happen due to pre-filtering, but as safety
                    self.logger.error(f"Error re-parsing percentage for {address}. Skipping.")
                    continue
                    
                # Calculate amount using Decimal division
                amount_dec = (miner_distribution_amount * (percentage / total_percentage)).quantize(
                    Decimal('0.00000001'), rounding=ROUND_DOWN
                )
                
                if amount_dec > 0:
                    # Convert final amount to float for the structure
                    recipients.append({
                        "address": address,
                        "amount": float(amount_dec)
                    })
                    allocated_sum += amount_dec
                else:
                    # This might happen with very small percentages or amounts
                    self.logger.debug(f"Calculated amount for {address} is zero or negative ({amount_dec:.8f}). Skipping.") 

            if abs(allocated_sum - miner_distribution_amount) > Decimal('0.000001'):
                 # This difference is expected due to ROUND_DOWN quantization
                 dust = miner_distribution_amount - allocated_sum
                 self.logger.warning(f"Sum allocated to miners ({allocated_sum:.8f}) differs from target ({miner_distribution_amount:.8f}). Remainder (dust): {dust:.8f}")
                 
        elif miner_distribution_amount <= 0:
             self.logger.info("Miner distribution amount is zero or negative. No miners will receive funds from this pool.")
        else: # total_percentage is 0
             self.logger.warning("Total valid participation percentage is zero. Cannot distribute miner funds based on participation.")

        # Add pool fee recipient if the amount is greater than 0 and address is valid
        self.logger.debug(f"Checking condition to add pool fee: Amount={pool_fee_amount:.8f} (>0?), Address='{pool_fee_address}' (non-empty?) - Type: {type(pool_fee_address)}")
        if pool_fee_amount > 0 and pool_fee_address and isinstance(pool_fee_address, str) and pool_fee_address.strip():
             pool_fee_address_clean = pool_fee_address.strip()
             self.logger.info(f"Adding pool fee recipient: {pool_fee_address_clean} with {pool_fee_amount:.8f} {token_name}")
             recipients.append({
                 "address": pool_fee_address_clean,
                 "amount": float(pool_fee_amount.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN))
             })
        elif pool_fee_amount > 0:
             self.logger.warning("Pool fee amount > 0 but no valid pool fee address provided. Pool fee will not be included.")

        result = {
            "distributions": [{
                "token_name": token_name,
                "recipients": recipients
            }]
        }
        self.logger.info(f"Generated distribution for {len(recipients)} total recipients.")
        return result

    def save_distribution_json(self, distribution: Dict, filename: str | Path) -> None:
        filepath = Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Add timestamp to the data
            distribution_with_meta = distribution.copy()
            # Ensure nested structure is copied if needed, though not strictly necessary here
            distribution_with_meta["generated_at"] = datetime.now(timezone.utc).isoformat()
            distribution_with_meta["wallet_address_used"] = self.wallet_address # Add context
            
            with open(filepath, 'w') as f:
                json.dump(distribution_with_meta, f, indent=2)
            self.logger.info(f"Saved distribution to {filepath}")
        except IOError as e:
             self.logger.error(f"Error writing distribution file to {filepath}: {e}", exc_info=True)
        except Exception as e:
             self.logger.error(f"Unexpected error saving distribution JSON: {e}", exc_info=True)