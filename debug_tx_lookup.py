#!/usr/bin/env python3
"""
Debug script for transaction lookup

This script was created to help debug issues with the Block Heights Collection process in the
demurrage distribution code. Specifically, it addresses the discrepancy between finding 4 blocks
versus 54 blocks when starting from the same height.

Key findings:
1. The API returns transactions in reverse chronological order (newest first).
2. The 4 blocks originally found (1509846, 1509996, 1510211, 1510299) are in transactions 51-54
   on the first page of results.
3. When only 50 transactions were processed per page, these 4 blocks were missed.
4. When all 100 transactions were processed, all 54 blocks were found.

The root cause appears to be a limit on the number of transactions processed.
"""

import os
import sys
import logging
import argparse
from typing import List
from pathlib import Path
import requests
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.demurrage_distribution import BlockHeightCollector

def setup_debug_logging():
    """Configure detailed logging for debugging."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    
    # Silence some noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Set root logger to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create a logger for this script
    logger = logging.getLogger("debug_tx_lookup")
    logger.setLevel(logging.INFO)
    
    return logger

def get_blocks_with_limited_data(collector, min_block: int, max_tx_per_page: int, verbose: bool = False, search_blocks: List[int] = None) -> List[int]:
    """Custom implementation that limits the number of transactions processed per page"""
    logger = logging.getLogger("debug_tx_lookup")
    logger.info(f"Using limited transactions (max {max_tx_per_page} per page)")
    
    if search_blocks:
        logger.info(f"Searching for specific blocks: {search_blocks}")
    
    all_blocks = set()
    current_offset = 0
    limit = 100  # API request limit
    max_pages = 20
    page_count = 0

    logger.debug(f"Searching for blocks after height {min_block} from transactions of {collector.wallet_address}")

    while page_count < max_pages:
        logger.debug(f"Fetching transactions page {page_count + 1} with offset {current_offset}")
        try:
            response = requests.get(
                f"{collector.api_base}/addresses/{collector.wallet_address}/transactions",
                params={
                    "offset": current_offset,
                    "limit": limit,
                    "concise": True
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Debug: Print information about the first few transactions
            items = data.get("items", [])
            if items and verbose:
                logger.info(f"API returned {len(items)} transactions on page {page_count + 1}")
                for i, tx in enumerate(items[:5]):  # Show first 5 transactions
                    tx_id = tx.get("id", "unknown")
                    height = tx.get("inclusionHeight", "unknown")
                    logger.info(f"  Transaction {i+1}: ID={tx_id[:8]}, Height={height}")
                    
            if not items:
                logger.debug("No more transactions found")
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"API error fetching transactions: {e}. Stopping block fetch.")
            break

        # Only process max_tx_per_page transactions
        limited_items = items[:max_tx_per_page]
        logger.debug(f"Processing {len(limited_items)} transactions from page {page_count + 1} (limited from {len(items)})")
            
        new_blocks_found_in_page = False
        blocks_in_page = []
        
        # If verbose, we'll track which transactions yield blocks
        tx_block_map = {} if verbose else None
        
        # If search_blocks is provided, we'll track matches
        search_matches = {}
        
        for i, tx in enumerate(limited_items):
            height = tx.get("inclusionHeight", 0)
            
            # If we're searching for specific blocks, check if this is one
            if search_blocks and height in search_blocks:
                tx_id = tx.get("id", "unknown")[:8]  # First 8 chars of tx ID
                tx_idx = i + 1  # 1-indexed for readability
                if height not in search_matches:
                    search_matches[height] = []
                search_matches[height].append((tx_idx, tx_id))
            
            if height > min_block:
                blocks_in_page.append(height)
                if height not in all_blocks:
                    all_blocks.add(height)
                    new_blocks_found_in_page = True
                    if verbose:
                        tx_id = tx.get("id", "unknown")[:8]  # First 8 chars of tx ID
                        tx_idx = i + 1  # 1-indexed for readability
                        if height not in tx_block_map:
                            tx_block_map[height] = []
                        tx_block_map[height].append((tx_idx, tx_id))
        
        # If we're searching for specific blocks and found matches, log them
        if search_blocks and search_matches:
            logger.info(f"Found searched blocks in page {page_count + 1}:")
            for block_height in sorted(search_matches.keys()):
                sources = search_matches[block_height]
                sources_str = ", ".join([f"tx#{idx}({tx_id})" for idx, tx_id in sources])
                logger.info(f"  Block {block_height} from {sources_str}")
        
        if blocks_in_page:
            logger.debug(f"Page {page_count + 1} contained blocks: {sorted(blocks_in_page)}")
            logger.debug(f"Found {len(blocks_in_page)} blocks in this page, {len(all_blocks)} unique blocks so far")
            
            # If verbose, show which transactions yielded which blocks
            if verbose and tx_block_map:
                logger.info(f"Block sources in page {page_count + 1}:")
                for block_height in sorted(tx_block_map.keys()):
                    sources = tx_block_map[block_height]
                    sources_str = ", ".join([f"tx#{idx}({tx_id})" for idx, tx_id in sources])
                    logger.info(f"  Block {block_height} from {sources_str}")
        else:
            logger.debug(f"No eligible blocks found in page {page_count + 1}")

        total_txs = data.get("total", 0)
        if current_offset + len(items) >= total_txs:
            logger.debug(f"Reached end of transactions (processed {current_offset + len(limited_items)} of {total_txs})")
            break

        current_offset += limit
        page_count += 1

    if page_count == max_pages:
        logger.warning(f"Reached max page limit ({max_pages}) fetching transactions. Results might be incomplete.")

    result = sorted(list(all_blocks))
    logger.info(f"Found {len(result)} blocks since height {min_block}")
    if result:
        logger.debug(f"Block heights: {result}")
    return result

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Debug transaction lookup")
    parser.add_argument('--test-height', type=int, help='Override minimum block height for testing')
    parser.add_argument('--max-tx', type=int, help='Maximum transactions to process per page (to reproduce limited data issues)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information about which transactions yield blocks')
    parser.add_argument('--search-blocks', type=str, help='Comma-separated list of block heights to search for')
    args = parser.parse_args()
    
    logger = setup_debug_logging()
    
    # Load environment from .env file
    env_loaded = False
    if os.path.exists(".env.demurrage"):
        load_dotenv(".env.demurrage")
        env_loaded = True
        logger.info("Loaded environment from .env.demurrage")
    elif os.path.exists(".env"):
        load_dotenv(".env")
        env_loaded = True
        logger.info("Loaded environment from .env")
    
    if not env_loaded:
        logger.error("No .env or .env.demurrage file found")
        sys.exit(1)
    
    # Check required environment variables
    wallet_address = os.getenv("WALLET_ADDRESS")
    if not wallet_address:
        logger.error("WALLET_ADDRESS not found in environment")
        sys.exit(1)
    
    logger.info(f"Using wallet address: {wallet_address}")
    
    # Initialize BlockHeightCollector
    collector = BlockHeightCollector()
    
    # Parse search blocks if provided
    search_blocks = None
    if args.search_blocks:
        try:
            search_blocks = [int(height.strip()) for height in args.search_blocks.split(',')]
            logger.info(f"Will search for blocks: {search_blocks}")
        except ValueError:
            logger.error("Invalid format for --search-blocks. Use comma-separated integers.")
            sys.exit(1)
    
    # Get blocks since the last outgoing transaction
    try:
        # Use the provided test height if specified
        if args.test_height:
            test_height = args.test_height
            logger.info(f"Using override test height: {test_height}")
            
            if args.max_tx:
                # Use our custom function with limited transactions
                blocks = get_blocks_with_limited_data(collector, test_height, args.max_tx, args.verbose, search_blocks)
            else:
                # Use the original implementation
                blocks = collector.get_blocks_since_last_outgoing(override_min_block=test_height)
                
            logger.info(f"Found {len(blocks)} blocks since height {test_height}")
        else:
            # Get the latest outgoing block height and then the blocks
            latest_height = collector.get_latest_outgoing_block()
            
            if args.max_tx:
                # Use our custom function with limited transactions
                blocks = get_blocks_with_limited_data(collector, latest_height, args.max_tx, args.verbose, search_blocks)
            else:
                # Use the original implementation
                blocks = collector.get_blocks_since_last_outgoing()
                
            logger.info(f"Found {len(blocks)} blocks since height {latest_height}")
        
        logger.info(f"Block heights: {blocks}")
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 