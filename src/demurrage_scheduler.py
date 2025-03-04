import os
import sys
from pathlib import Path

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
    ERG_TO_NANOERG
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
        service = DemurrageService(debug=dry_run)
        
        # Get block heights and check if there are any to process
        block_heights = service.collector.get_blocks_since_last_outgoing()
        if not block_heights:
            logger.info("No blocks found since last outgoing transaction")
            return
            
        logger.info(f"Processing {len(block_heights)} blocks")
        
        # Get miners data
        miners_data = service.collector.fetch_miners_data(block_heights)
        recipient_count = len(miners_data.get('miners', []))
        
        if recipient_count == 0:
            logger.info("No miners found in the blocks")
            return
            
        # Calculate distribution amount
        try:
            distribution_amount = service.calculate_distribution_amount(recipient_count)
        except ValueError as e:
            logger.warning(str(e))
            return
            
        # Generate distribution
        distribution = service.collector.generate_distribution(miners_data, distribution_amount, "ERG")
        
        if dry_run:
            wallet_balance = service.get_wallet_balance()
            total_costs, min_box_total = service.calculate_transaction_costs(recipient_count)
            
            logger.info("\n=== DRY RUN RESULTS ===")
            logger.info(f"Total blocks processed: {len(block_heights)}")
            logger.info(f"Total miners: {recipient_count}")
            logger.info(f"Wallet balance: {wallet_balance:.8f} ERG")
            logger.info(f"Total fees required: {total_costs:.8f} ERG")
            logger.info(f"Distribution amount: {distribution_amount:.8f} ERG")
            logger.info("\nDistribution breakdown:")
            for dist in distribution['distributions']:
                logger.info(f"\nToken: {dist['token_name']}")
                for recipient in dist['recipients']:
                    logger.info(f"Address: {recipient['address'][:15]}... Amount: {recipient['amount']:.8f} ERG")
            return

        # Save distribution file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = Path(output_dir) / f"distribution_{len(block_heights)}_blocks_{timestamp}.json"
        service.collector.save_distribution_json(distribution, output_file)
        logger.info(f"Distribution saved to {output_file}")

        # Execute the distribution
        logger.info("Executing distribution transaction...")
        tx_id = service.execute_distribution(block_heights)
        
        if tx_id:
            logger.info(f"Distribution executed successfully. Transaction ID: {tx_id}")
        else:
            logger.error("Distribution execution failed - no transaction ID returned")
            
    except Exception as e:
        logger.error(f"Error in distribution process: {e}", exc_info=True)

def main():
    args = parse_args()
    logger = setup_logging(args.verbose)
    
    # Load configuration
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
    
    schedule.every().day.at("00:00").do(
        process_distribution,
        config=config,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        logger=logger
    )
    
    # Run immediately if configured
    if os.getenv('IMMEDIATE_RUN', 'false').lower() == 'true':
        logger.info("Running immediate distribution...")
        process_distribution(config, args.dry_run, args.output_dir, logger)
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 