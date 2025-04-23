import os
import sys
from pathlib import Path
from decimal import Decimal

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import schedule
import time
import logging
import argparse
from dotenv import load_dotenv
from datetime import datetime
import requests

# Now import from src package
from src.demurrage_distribution import (
    BlockHeightCollector, 
    load_env_config, 
    ERG_TO_NANOERG,
)
from src.demurrage_service import DemurrageService
from src.airdrop import BaseAirdrop
from src.base_scheduler import BaseScheduler


class DemurrageScheduler(BaseScheduler):
    def __init__(self, debug: bool = False):
        super().__init__(debug)
        self.service = DemurrageService(debug=debug)
        self.logger.info(f"Demurrage Scheduler initialized with debug: {debug}")

    def run_job(self):
        self.logger.info("Starting demurrage job execution")
        try:
            self.logger.info("Fetching blocks since last outgoing transaction")
            block_heights = self.service.collector.get_blocks_since_last_outgoing()
            
            if not block_heights:
                self.logger.info("No new blocks found since last outgoing transaction")
                return
                
            self.logger.info(f"Processing blocks: {block_heights}")
            
            if self.debug:
                self.logger.info("Debug mode - simulating distribution")
                wallet_balance = self.service.get_wallet_balance()
                self.logger.info(f"Current wallet balance: {wallet_balance} ERG")
                
                miners_data = self.service.collector.fetch_miners_data(block_heights)
                recipient_count = len(miners_data.get('miners', []))
                self.logger.info(f"Found {recipient_count} potential recipients")
                
                if recipient_count > 0:
                    distribution_amount = self.service.calculate_distribution_amount(recipient_count)
                    self.logger.info(f"Calculated distribution amount: {distribution_amount} ERG")
                else:
                    self.logger.info("No eligible recipients found")
                return
            
            # Execute actual distribution
            self.logger.info("Executing distribution")
            tx_id = self.service.execute_distribution(block_heights)
            if tx_id:
                self.logger.info(f"Distribution completed successfully. TX: {tx_id}")
            else:
                self.logger.warning("Distribution did not complete - no transaction ID returned")
                
        except ValueError as e:
            self.logger.error(f"Validation error in demurrage job: {e}")
        except Exception as e:
            self.logger.error(f"Error in demurrage job: {e}", exc_info=True)

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Schedule demurrage distributions')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Run in dry-run mode to preview distribution without executing'
    )
    parser.add_argument(
        '--run-once',
        action='store_true',
        default=False,
        help='Run once and exit instead of scheduling'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=False,
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--env-file',
        type=str,
        default='.env.demurrage',
        help='Path to environment file (default: .env.demurrage)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='distributions',
        help='Directory to save distribution files (default: distributions)'
    )
    parser.add_argument(
        '--schedule',
        type=str,
        default='0 0 * * *',  # Default to daily at midnight
        help='Cron-style schedule (default: "0 0 * * *")'
    )
    return parser.parse_args()

def process_distribution(config: dict, dry_run: bool, output_dir: str, logger: logging.Logger):
    try:
        logger.info(f"Starting distribution process {'(DRY RUN)' if dry_run else ''}")
        
        # Initialize service
        # Pass the dry_run flag to the service constructor
        service = DemurrageService(debug=dry_run) 
        
        # Get block heights and check if there are any to process
        block_heights = service.collector.get_blocks_since_last_outgoing()
        if not block_heights:
            logger.info("No blocks found since last outgoing transaction. Nothing to process.")
            return
            
        logger.info(f"Found {len(block_heights)} blocks to process since last outgoing transaction.")
        
        # Let the service handle fetching miners, calculating, logging details, and executing/simulating
        # The service now logs the detailed breakdown during its execution flow, including dry runs.
        # It returns the distribution dict on dry run, or tx_id/None otherwise.
        result = service.execute_distribution(block_heights)

        # --- Handling based on dry_run --- 
        if dry_run:
            # In dry run, the result should be the distribution dictionary
            if isinstance(result, dict) and 'distributions' in result:
                logger.info("--- DRY RUN COMPLETE ---")
                logger.info("Distribution simulation finished. Details logged above by the service.")
                
                # Save distribution file in dry run mode
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = Path(output_dir) / f"dry_run_distribution_{len(block_heights)}_blocks_{timestamp}.json"
                try:
                    # Use the service's collector to save the JSON (reuse existing method)
                    service.collector.save_distribution_json(result, output_file) 
                    logger.info(f"Dry run distribution plan saved to {output_file}")
                except Exception as e:
                    logger.error(f"Failed to save dry run distribution file: {e}", exc_info=True)
            elif result is None:
                 logger.warning("Dry run failed or resulted in no distribution (e.g., insufficient balance, no recipients). See logs above.")
            else:
                 logger.warning(f"Dry run finished, but execute_distribution returned unexpected type: {type(result)}. Expected dict.")
        else:
            # In actual run, the result should be a tx_id string or None
            if isinstance(result, str):
                logger.info(f"--- DISTRIBUTION EXECUTED SUCCESSFULLY ---")
                logger.info(f"Transaction ID: {result}")
                # Optionally save the distribution JSON after successful execution?
                # If needed, would require execute_distribution to return both tx_id and distribution data
                # or call a separate generation method first.
            else:
                logger.error("--- DISTRIBUTION EXECUTION FAILED ---")
                logger.error("Distribution execution failed or did not return a transaction ID. See logs above for details.")
            
    except Exception as e:
        # Catch any unexpected errors during the process_distribution flow itself
        logger.error(f"Unexpected error during distribution processing: {e}", exc_info=True)

def main():
    args = parse_args()
    logger = setup_logging(args.verbose)
    
    # Load configuration
    # load_env_config is still needed here to load the .env file specified
    # although the config dict itself isn't directly used by process_distribution anymore.
    config = load_env_config(args.env_file)
    
    # Ensure output directory exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    if args.run_once:
        logger.info("Running single distribution process...")
        process_distribution(config, args.dry_run, args.output_dir, logger)
        logger.info("Distribution process completed. Exiting...")
        return
    
    # Schedule the job
    schedule_str = os.getenv('DISTRIBUTION_SCHEDULE', args.schedule)
    logger.info(f"Setting up schedule: {schedule_str} {'(DRY RUN)' if args.dry_run else ''}")
    
    # TODO: Implement proper cron-style scheduling using a library that supports it (e.g., scheduleplus, apscheduler)
    # The current schedule library doesn't parse cron strings directly.
    # For simplicity, using daily at midnight as before.
    logger.warning(f"Note: Currently using schedule.every().day.at('00:00'). Custom schedule '{schedule_str}' NOT IMPLEMENTED.")
    schedule.every().day.at("00:00").do(
        process_distribution,
        config=config, # Pass config even if unused, for potential future use
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        logger=logger
    )
    
    # Run immediately if configured
    if os.getenv('IMMEDIATE_RUN', 'false').lower() == 'true':
        logger.info("Running immediate distribution based on IMMEDIATE_RUN env var...")
        process_distribution(config, args.dry_run, args.output_dir, logger)
    
    # Keep the script running
    logger.info("Scheduler started. Waiting for scheduled jobs...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 