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

# Import from src package
from src.demurrage_service import DemurrageService
from src.base_scheduler import BaseScheduler
from src.config import AppConfig, load_config
from src.telegram_notifier import notify_job_start, notify_job_result

# Keep this function for backward compatibility
def load_env_config(env_file='.env.demurrage'):
    """Load environment variables from specified env file and return a dict (for backward compatibility)."""
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logging.info(f"Loaded environment from {env_path}")
    else:
        logging.warning(f"Environment file {env_path} not found. Using existing environment variables.")
    
    # Return a simple dict of configured values
    return {
        'wallet_address': os.environ.get('WALLET_ADDRESS'),
        'node_url': os.environ.get('NODE_URL'),
        'explorer_url': os.environ.get('EXPLORER_URL'),
        'network_type': os.environ.get('NETWORK_TYPE')
    }

class DemurrageScheduler(BaseScheduler):
    def __init__(self, config: AppConfig = None, debug: bool = False):
        super().__init__(debug)
        # Use provided config or load with demurrage service type
        self.config = config or load_config(service_type='demurrage')
        # Initialize service with config (debug flag will be taken from config)
        self.service = DemurrageService(config=self.config)
        self.logger.info(f"Demurrage Scheduler initialized with debug: {self.config.debug}")

    def run_job(self):
        self.logger.info("Starting demurrage job execution")
        try:
            # Notify job start if configured
            notify_job_start('demurrage', self.config.dry_run, self.config)
            
            self.logger.info("Fetching blocks since last outgoing transaction")
            block_heights = self.service.collector.get_blocks_since_last_outgoing()
            
            if not block_heights:
                self.logger.info("No new blocks found since last outgoing transaction")
                return
                
            self.logger.info(f"Processing blocks: {block_heights}")
            
            # Execute distribution (will handle dry run internally)
            self.logger.info(f"Executing distribution {'(DRY RUN)' if self.config.dry_run else ''}")
            result = self.service.execute_distribution(block_heights)
            
            # Notify about the result
            notify_job_result('demurrage', result, self.config)
            
            # Log based on result status
            if result.get('status') == 'completed':
                self.logger.info(f"Distribution completed successfully. TX: {result.get('tx_id')}")
            elif result.get('status') == 'dry_run':
                self.logger.info("Dry run completed successfully.")
            else:
                self.logger.warning(f"Distribution failed: {result.get('error')}")
                
        except ValueError as e:
            self.logger.error(f"Validation error in demurrage job: {e}")
            # Notify about error
            notify_job_result('demurrage', {
                'status': 'failed',
                'error': str(e),
                'message': 'Validation error occurred'
            }, self.config)
        except Exception as e:
            self.logger.error(f"Error in demurrage job: {e}", exc_info=True)
            # Notify about error
            notify_job_result('demurrage', {
                'status': 'failed',
                'error': str(e),
                'message': 'Unexpected error occurred'
            }, self.config)

def setup_logging(verbose: bool):
    # Configure root logger
    level = logging.DEBUG if verbose else logging.INFO
    
    # Format with more detail
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set urllib3 and requests to WARNING level to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Make sure our loggers are at the right level
    logging.getLogger('src').setLevel(level)
    
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

def process_distribution(dry_run: bool, output_dir: str, logger: logging.Logger, env_file: str = '.env.demurrage'):
    try:
        # Set environment variables for the config system
        os.environ['DRY_RUN'] = str(dry_run).lower()
        
        # Load config with demurrage service type
        config = load_config(service_type='demurrage')
        
        logger.info(f"Starting distribution process {'(DRY RUN)' if config.dry_run else ''}")
        
        # Notify job start
        notify_job_start('demurrage', config.dry_run, config)
        
        # Initialize service with config
        service = DemurrageService(config=config)
        
        # Get block heights and check if there are any to process
        block_heights = service.collector.get_blocks_since_last_outgoing()
        if not block_heights:
            logger.info("No blocks found since last outgoing transaction. Nothing to process.")
            return
            
        logger.info(f"Found {len(block_heights)} blocks to process since last outgoing transaction.")
        
        # Execute distribution (service handles dry run internally)
        result = service.execute_distribution(block_heights)

        # Notify about the result
        notify_job_result('demurrage', result, config)

        # --- Handle result based on status ---
        if result.get('status') == 'dry_run':
            # In dry run, save the distribution plan
            logger.info("--- DRY RUN COMPLETE ---")
            
            # Save distribution file in dry run mode
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = Path(output_dir) / f"dry_run_distribution_{len(block_heights)}_blocks_{timestamp}.json"
            try:
                # Use the service's collector to save the JSON
                service.collector.save_distribution_json(result.get('distributions', {}), output_file) 
                logger.info(f"Dry run distribution plan saved to {output_file}")
            except Exception as e:
                logger.error(f"Failed to save dry run distribution file: {e}", exc_info=True)
                
        elif result.get('status') == 'completed':
            # Successful live distribution
            logger.info("--- DISTRIBUTION EXECUTED SUCCESSFULLY ---")
            logger.info(f"Transaction ID: {result.get('tx_id')}")
            
            # Optionally save the distribution details
            if 'distributions' in result:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = Path(output_dir) / f"distribution_{len(block_heights)}_blocks_{timestamp}.json"
                try:
                    service.collector.save_distribution_json(result.get('distributions', {}), output_file)
                    logger.info(f"Distribution details saved to {output_file}")
                except Exception as e:
                    logger.error(f"Failed to save distribution file: {e}", exc_info=True)
        else:
            # Failed distribution
            logger.error("--- DISTRIBUTION EXECUTION FAILED ---")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
            if 'message' in result:
                logger.error(f"Message: {result['message']}")
            
    except Exception as e:
        # Catch any unexpected errors during the process_distribution flow itself
        logger.error(f"Unexpected error during distribution processing: {e}", exc_info=True)
        
        # Notify about error
        try:
            config = load_config(service_type='demurrage')
            notify_job_result('demurrage', {
                'status': 'failed',
                'error': str(e),
                'message': 'Unexpected error in process_distribution'
            }, config)
        except Exception as notify_err:
            logger.error(f"Failed to send error notification: {notify_err}")

def main():
    args = parse_args()
    logger = setup_logging(args.verbose)
    
    # Set environment variables based on args
    os.environ['DRY_RUN'] = str(args.dry_run).lower()
    os.environ['DEBUG'] = str(args.verbose).lower()
    
    # Load configuration from the args env file
    load_dotenv(args.env_file, override=True)
    
    # Ensure output directory exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    if args.run_once:
        logger.info("Running single distribution process...")
        process_distribution(args.dry_run, args.output_dir, logger, args.env_file)
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
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        logger=logger,
        env_file=args.env_file
    )
    
    # Run immediately if configured
    if os.getenv('IMMEDIATE_RUN', 'false').lower() == 'true':
        logger.info("Running immediate distribution based on IMMEDIATE_RUN env var...")
        process_distribution(args.dry_run, args.output_dir, logger, args.env_file)
    
    # Keep the script running
    logger.info("Scheduler started. Waiting for scheduled jobs...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 