import os
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Union, Any, List
import argparse
import sys
from pathlib import Path
from decimal import Decimal, ROUND_DOWN, getcontext

# Add the parent directory to sys.path when running as script
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).parent.parent))

from src.models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from src.base_airdrop import BaseAirdrop
# Import our new config module
from src.config import AppConfig, load_config
from src.recipient_manager import RecipientManager, AirdropRecipient # Import necessary classes

# Set precision for Decimal calculations if needed
# getcontext().prec = 18 

class BonusService:
    def __init__(self, config_file: str, config: AppConfig = None):
        self.config_file = config_file
        # Either use the provided config or load the bonus-specific one
        self.config = config or load_config(service_type='bonus')
        self.setup_logging()
        # No need to validate environment - config loader does validation
        self.wallet_config = self.create_wallet_config()

    def setup_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.DEBUG if self.config.debug else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "bonus_airdrop.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"BonusService initialized with config file: {self.config_file}")
        self.logger.info(f"Running with dry_run={self.config.dry_run}, debug={self.config.debug}")

    def create_wallet_config(self) -> WalletConfig:
        """Create a WalletConfig model instance from our AppConfig"""
        return WalletConfig(
            node_url=self.config.node.url,
            network_type=self.config.node.network_type,
            explorer_url=self.config.node.explorer_url,
            wallet_mnemonic=self.config.wallet.mnemonic,
            mnemonic_password=self.config.wallet.mnemonic_password
        )

    def load_distribution_config(self) -> dict:
        self.logger.info(f"Loading distribution config from {self.config_file}")
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except FileNotFoundError:
            error_msg = f"Distribution config file not found: {self.config_file}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in config file {self.config_file}: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) 
        except Exception as e:
            self.logger.error(f"Failed to load config: {str(e)}")
            raise

    def execute_distribution(self) -> Dict[str, Any]:
        """Execute the bonus distribution based on configuration.
        Fetches miners from the bonus API and distributes amounts from config file.
        
        Returns:
            Dict with results including status, transaction ID (if not dry run),
            and other details suitable for notifications.
        """
        try:
            dry_run = self.config.dry_run or self.config.debug
            run_type = "DRY RUN" if dry_run else "LIVE"
            self.logger.info(f"Starting bonus distribution - Mode: {run_type}")
            
            start_time = datetime.now()

            # --- Step 1: Fetch the single list of bonus miners --- 
            miner_recipients: List[AirdropRecipient] = RecipientManager.from_bonus_miners(self.config)
            miner_count = len(miner_recipients)
            
            if miner_count == 0:
                self.logger.error("Failed to fetch bonus miners or no miners returned from API. Cannot proceed.")
                return {
                    "status": "failed",
                    "error": "Failed to fetch bonus miners or list is empty",
                    "message": "Bonus distribution failed: Could not retrieve miner list."
                }
            self.logger.info(f"Successfully fetched {miner_count} bonus miners to receive distributions.")

            # --- Step 2: Load token distributions from config file --- 
            config_data = self.load_distribution_config()
            distribution_configs = config_data.get('distributions', [])
            
            if not distribution_configs:
                self.logger.warning("No token distributions found in config file")
                return {
                    "status": "failed",
                    "error": "No token distributions found in config file",
                    "message": "Bonus distribution failed: Config file contains no distributions"
                }
                
            self.logger.info(f"Loaded {len(distribution_configs)} token distributions from {self.config_file}")

            # --- Step 3: Prepare TokenConfig list for airdrop tool --- 
            tokens_to_airdrop: List[TokenConfig] = []
            total_recipient_deliveries = 0 # Counts recipient * token deliveries
            distributions_summary = []
            
            for token_data in distribution_configs:
                token_name = token_data.get('token_name')
                total_amount_str = str(token_data.get('total_amount', 0)) # Ensure string for Decimal
                
                if not token_name:
                    self.logger.warning(f"Skipping distribution entry missing 'token_name': {token_data}")
                    continue
                
                try:
                    total_amount_dec = Decimal(total_amount_str)
                    if total_amount_dec <= 0:
                        self.logger.warning(f"Skipping token {token_name} due to zero or negative total_amount: {total_amount_dec}")
                        continue
                except Exception as e:
                    self.logger.warning(f"Skipping token {token_name} due to invalid total_amount '{total_amount_str}': {e}")
                    continue
                    
                self.logger.info(f"Processing distribution for {token_name}: Total {total_amount_dec} to {miner_count} miners")
                
                # Calculate amount per recipient
                # Use Decimal for precision during calculation
                amount_per_recipient_dec = (total_amount_dec / Decimal(miner_count)).quantize(
                    # Quantize based on token decimals if provided, else use a high precision
                    # Note: BaseAirdrop might need adjustment for very high decimal tokens
                    Decimal('1e-8'), # Default to 8 decimal places for division precision
                    rounding=ROUND_DOWN 
                )
                
                # Ensure calculated amount isn't zero due to division
                if amount_per_recipient_dec <= 0:
                    self.logger.warning(f"Calculated amount per recipient for {token_name} is zero or less ({amount_per_recipient_dec}). Skipping token.")
                    continue
                    
                # Convert back to float for RecipientAmount model (as currently defined)
                amount_per_recipient_float = float(amount_per_recipient_dec)
                
                # Create the recipient list for this specific token
                token_recipients = [
                    RecipientAmount(
                        address=miner.address,
                        amount=amount_per_recipient_float
                    )
                    for miner in miner_recipients
                ]
                
                tokens_to_airdrop.append(TokenConfig(
                    token_name=token_name,
                    recipients=token_recipients,
                    # Pass other relevant fields if needed by BaseAirdrop
                    decimals=token_data.get('decimals', 0) # Example: Carry over decimals
                ))
                
                total_recipient_deliveries += len(token_recipients)
                distributions_summary.append({
                    "token": token_name,
                    "recipients": len(token_recipients),
                    "total_distributed": float(amount_per_recipient_dec * Decimal(len(token_recipients))),
                    "amount_per": amount_per_recipient_float
                })

            # If no valid tokens were processed, exit
            if not tokens_to_airdrop:
                self.logger.error("No valid token distributions could be prepared.")
                return {
                    "status": "failed",
                    "error": "No valid token distributions prepared",
                    "message": "Bonus distribution failed: Could not prepare any valid token distributions based on config and miners."
                }

            # --- Step 4: Prepare and Execute/Simulate Airdrop --- 
            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=tokens_to_airdrop,
                headless=True,
                debug=dry_run # Pass the dry_run flag to BaseAirdrop
            )

            self.logger.info(f"Prepared airdrop with {len(tokens_to_airdrop)} token distributions to {miner_count} miners each ({total_recipient_deliveries} total recipient deliveries).")
            
            if dry_run:
                self.logger.info("--- DRY RUN MODE: SIMULATING TRANSACTION ---")
                # Format distribution info for dry run results
                token_summaries = []
                for dist in distributions_summary:
                    token_summaries.append(
                        f"{dist['token']}: {dist['amount_per']} each to {dist['recipients']} recipients (Total: {dist['total_distributed']})"
                    )
                
                return {
                    "status": "dry_run",
                    "distributions": distributions_summary,
                    "token_count": len(tokens_to_airdrop),
                    "recipient_count": miner_count, # Unique recipients
                    "message": f"Dry run completed. Would distribute {len(tokens_to_airdrop)} tokens to {miner_count} miners.",
                    "details": "\n".join(token_summaries)
                }
            
            # Execute live airdrop
            self.logger.info("Executing airdrop transaction...")
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute()

            duration = datetime.now() - start_time
            if result.status == "completed":
                self.logger.info(f"Distribution completed successfully in {duration}")
                self.logger.info(f"Transaction ID: {result.tx_id}")
                explorer_url = f"{self.config.node.explorer_url}/transactions/{result.tx_id}"
                self.logger.info(f"Explorer URL: {explorer_url}")
                
                return {
                    "status": "completed",
                    "tx_id": result.tx_id,
                    "explorer_url": explorer_url,
                    "duration_seconds": duration.total_seconds(),
                    "distributions": distributions_summary,
                    "token_count": len(tokens_to_airdrop),
                    "recipient_count": miner_count,
                    "message": f"Bonus distribution completed successfully in {duration}. TX: {result.tx_id}"
                }
            else:
                error_msg = f"Distribution failed with status: {result.status}"
                if result.error:
                    error_msg += f" - Error: {result.error}"
                self.logger.error(error_msg)
                
                return {
                    "status": "failed",
                    "error": result.error if result.error else "Transaction failed",
                    "distributions": distributions_summary,
                    "message": error_msg
                }

        except ValueError as ve:
            error_msg = f"Distribution failed with validation error: {str(ve)}"
            self.logger.error(error_msg)
            return {
                "status": "failed",
                "error": str(ve),
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"Distribution failed with unexpected error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "message": error_msg
            }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bonus distribution service')
    parser.add_argument('config_file', help='Path to the configuration file')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit (no scheduling)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate execution without sending transactions')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--env-file', default='.env.bonus', help='Path to environment file')
    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv
    if not load_dotenv(args.env_file):
        print(f"Error: Could not load environment file: {args.env_file}")
        sys.exit(1)

    # Load config with any CLI-provided overrides
    os.environ['DRY_RUN'] = 'true' if args.dry_run else os.environ.get('DRY_RUN', 'false')
    os.environ['DEBUG'] = 'true' if args.debug else os.environ.get('DEBUG', 'false')
    
    config = load_config(service_type='bonus')

    try:
        service = BonusService(args.config_file, config=config)
        result = service.execute_distribution()
        
        # Display result summary
        status = result.get('status', 'unknown')
        if status == 'completed':
            print(f"Distribution completed successfully!")
            print(f"Transaction ID: {result.get('tx_id')}")
            print(f"Explorer URL: {result.get('explorer_url')}")
        elif status == 'dry_run':
            print("Dry run completed successfully!")
            print(f"Would distribute {result.get('token_count', 0)} tokens to {result.get('recipient_count', 0)} recipients.")
            if result.get('details'):
                print("Details:")
                print(result.get('details'))
        else:
            print(f"Distribution failed: {result.get('message', 'Unknown error')}")
            sys.exit(1)
            
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)