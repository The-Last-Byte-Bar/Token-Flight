#!/usr/bin/env python3
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to path to ensure imports work
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Import configuration and services
from src.config import load_config, AppConfig
from src.bonus_service import BonusService
from src.demurrage_service import DemurrageService
from src.telegram_notifier import notify_job_start, notify_job_result
from dotenv import load_dotenv

def setup_logging(verbose: bool) -> logging.Logger:
    """Configure logging with appropriate level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # More detailed format for debug mode
    if verbose:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    else:
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
    console_handler.setLevel(level)  # Ensure handler level matches root logger
    root_logger.addHandler(console_handler)
    
    # Set urllib3 and requests to WARNING level to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Make sure our loggers are at the right level
    app_logger = logging.getLogger('src')
    app_logger.setLevel(level)
    
    # Create and configure the distribution logger
    dist_logger = logging.getLogger('run_distribution')
    dist_logger.setLevel(level)
    
    # Log the initial debug state
    if verbose:
        dist_logger.debug("Debug logging enabled")
    
    return dist_logger

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Ergo Token Distribution CLI')
    
    # Service selection
    parser.add_argument(
        '--service',
        type=str,
        choices=['bonus', 'demurrage'],
        required=True,
        help='Type of distribution service to run (bonus or demurrage)'
    )
    
    # Common options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Run in dry-run mode to preview distribution without executing'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--env-file',
        type=str,
        help='Path to environment file (defaults to .env.bonus or .env.demurrage based on service)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='distributions',
        help='Directory to save distribution files (default: distributions)'
    )
    
    # Bonus service specific options
    parser.add_argument(
        '--config-file',
        type=str,
        help='Path to bonus configuration file (required for bonus service)'
    )
    
    # Demurrage service specific options
    parser.add_argument(
        '--run-once',
        action='store_true',
        default=False,
        help='Run once and exit instead of scheduling (for demurrage service)'
    )
    
    parser.add_argument(
        '--schedule',
        type=str,
        default='0 0 * * *',  # Default to daily at midnight
        help='Cron-style schedule for demurrage service (default: "0 0 * * *")'
    )
    
    return parser.parse_args()

def run_bonus_distribution(args, config: AppConfig, logger: logging.Logger) -> Dict[str, Any]:
    """Run the bonus token distribution service.
    
    Args:
        args: Parsed command line arguments
        config: Loaded AppConfig object
        logger: Logger instance
        
    Returns:
        Dict with result information
    """
    if not args.config_file:
        raise ValueError("--config-file is required for bonus distribution service")
    
    # Initialize bonus service with config file and AppConfig
    logger.info(f"Initializing bonus service with config file: {args.config_file}")
    service = BonusService(args.config_file, config=config)
    
    # Notify job start
    notify_job_start('bonus', config.dry_run, config)
    
    # Run the distribution
    result = service.execute_distribution()
    
    # Notify about the result
    notify_job_result('bonus', result, config)
    
    return result

def run_demurrage_distribution(args, config: AppConfig, logger: logging.Logger) -> Dict[str, Any]:
    """Run the demurrage distribution service.
    
    Args:
        args: Parsed command line arguments
        config: Loaded AppConfig object
        logger: Logger instance
        
    Returns:
        Dict with result information
    """
    # Log debug information about the configuration
    logger.debug(f"Running demurrage distribution with config: dry_run={config.dry_run}")
    logger.debug(f"Command line args: {vars(args)}")
    
    # Ensure output directory exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Import demurrage scheduler only if needed to avoid import errors
    if not args.run_once:
        from src.demurrage_scheduler import DemurrageScheduler
        
        logger.info("Initializing demurrage scheduler")
        scheduler = DemurrageScheduler(config=config)
        
        # Run the job once through the scheduler
        logger.info("Running demurrage job")
        scheduler.run_job()
        
        # This would normally continue running on a schedule, but for CLI return after first run
        logger.info("Demurrage job completed")
        
        # For CLI we don't have a result to return
        return {"status": "completed", "message": "Demurrage job executed through scheduler"}
    else:
        # For run-once mode, use the service directly
        logger.info("Initializing demurrage service for one-time run")
        service = DemurrageService(config=config)
        
        # Log service configuration
        logger.debug(f"DemurrageService initialized with dry_run={service.config.dry_run}")
        
        # Notify job start
        notify_job_start('demurrage', config.dry_run, config)
        
        # Get block heights
        block_heights = service.collector.get_blocks_since_last_outgoing()
        if not block_heights:
            logger.info("No blocks found since last outgoing transaction. Nothing to process.")
            return {
                "status": "completed", 
                "message": "No blocks to process since last transaction"
            }
            
        logger.info(f"Found {len(block_heights)} blocks to process since last outgoing transaction.")
        logger.debug(f"Block heights to process: {block_heights}")
        
        # Execute the distribution
        logger.debug("Executing distribution with dry_run=%s", config.dry_run)
        result = service.execute_distribution(block_heights)
        logger.debug(f"Distribution result: {result}")
        
        # Notify about the result
        notify_job_result('demurrage', result, config)
        
        # Handle dry run result
        if result.get('status') == 'dry_run' and result.get('distribution'):
            # Save distribution file in dry run mode
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = Path(args.output_dir) / f"dry_run_distribution_{len(block_heights)}_blocks_{timestamp}.json"
            try:
                # Use the service's collector to save the JSON
                service.collector.save_distribution_json(result.get('distribution', {}), output_file) 
                logger.info(f"Dry run distribution plan saved to {output_file}")
            except Exception as e:
                logger.error(f"Failed to save dry run distribution file: {e}", exc_info=True)
        
        return result

def main():
    """Main entry point for the distribution CLI."""
    # Parse command line arguments
    args = parse_args()
    
    try:
        # Set environment variables based on arguments BEFORE logging setup
        os.environ['DRY_RUN'] = str(args.dry_run).lower()
        os.environ['DEBUG'] = str(args.debug).lower()
        
        # Determine env file path if not specified
        if not args.env_file:
            if args.service == 'bonus':
                args.env_file = '.env.bonus'
            else:  # demurrage
                args.env_file = '.env.demurrage'
        
        # Load environment file
        if Path(args.env_file).exists():
            load_dotenv(args.env_file, override=True)
        
        # Setup logging AFTER environment variables are set
        logger = setup_logging(args.debug)
        logger.info(f"Starting {args.service} service with dry_run={args.dry_run}, debug={args.debug}")
        
        if not Path(args.env_file).exists():
            logger.warning(f"Environment file {args.env_file} not found. Using existing environment variables.")
        
        # Load configuration for the specified service
        config = load_config(service_type=args.service)
        logger.info(f"Loaded configuration for {args.service} service")
        logger.debug(f"Configuration dry_run setting: {config.dry_run}")
        
        # Run the appropriate service
        if args.service == 'bonus':
            result = run_bonus_distribution(args, config, logger)
        else:  # demurrage
            result = run_demurrage_distribution(args, config, logger)
        
        # Display result summary
        status = result.get('status', 'unknown')
        if status == 'completed':
            print("✅ Distribution completed successfully!")
            if 'tx_id' in result:
                print(f"Transaction ID: {result.get('tx_id')}")
                print(f"Explorer URL: {result.get('explorer_url')}")
            elif 'message' in result:
                print(result.get('message'))
        elif status == 'dry_run':
            print("🔍 Dry run completed successfully!")
            if 'message' in result:
                print(result.get('message'))
            if 'details' in result:
                print("Details:")
                print(result.get('details'))
        else:
            print(f"❌ Distribution failed: {result.get('message', 'Unknown error')}")
            sys.exit(1)
            
    except ValueError as e:
        # Since logger might not be defined in case of early failure
        if 'logger' in locals():
            logger.error(f"Validation error: {e}")
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 