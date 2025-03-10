import os
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import argparse
import sys
from pathlib import Path

# Add the parent directory to sys.path when running as script
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).parent.parent))

from src.models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from src.base_airdrop import BaseAirdrop

class BonusService:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.setup_logging()
        self.validate_environment()
        self.wallet_config = self.load_wallet_config()

    def validate_environment(self):
        """Validate required environment variables are set"""
        required_vars = {
            'NODE_URL': os.getenv('NODE_URL'),
            'NETWORK_TYPE': os.getenv('NETWORK_TYPE'),
            'EXPLORER_URL': os.getenv('EXPLORER_URL'),
            'WALLET_MNEMONIC': os.getenv('WALLET_MNEMONIC')
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            self.logger.error(error_msg)
            self.logger.error("Please ensure you have set up your .env file correctly")
            raise ValueError(error_msg)

    def setup_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "bonus_airdrop.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_wallet_config(self) -> WalletConfig:
        return WalletConfig(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            wallet_mnemonic=os.getenv('WALLET_MNEMONIC')
        )

    def load_distribution_config(self) -> dict:
        self.logger.info(f"Loading distribution config from {self.config_file}")
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {str(e)}")
            raise

    def execute_distribution(self) -> Optional[str]:
        try:
            self.logger.info("Starting bonus distribution")
            start_time = datetime.now()

            config_data = self.load_distribution_config()
            self.logger.info(f"Loaded configuration with {len(config_data['distributions'])} token distributions")

            tokens = []
            for token_data in config_data['distributions']:
                self.logger.info(f"Processing distribution for {token_data['token_name']}")
                
                recipients = None
                if 'recipients' in token_data:
                    recipients = [
                        RecipientAmount(
                            address=r['address'],
                            amount=float(r['amount'])
                        )
                        for r in token_data['recipients']
                    ]
                    self.logger.info(f"Found {len(recipients)} recipients for {token_data['token_name']}")

                tokens.append(TokenConfig(
                    token_name=token_data['token_name'],
                    total_amount=token_data.get('total_amount'),
                    amount_per_recipient=token_data.get('amount_per_recipient'),
                    min_amount=token_data.get('min_amount', 0.001),
                    decimals=token_data.get('decimals', 0),
                    recipients=recipients
                ))

            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=tokens,
                headless=True
            )

            self.logger.info("Executing airdrop")
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute()

            duration = datetime.now() - start_time
            if result.status == "completed":
                self.logger.info(f"Distribution completed successfully in {duration}")
                self.logger.info(f"Transaction ID: {result.tx_id}")
                self.logger.info(f"Explorer URL: {result.explorer_url}")
                return result.tx_id
            else:
                self.logger.error(f"Distribution failed with status: {result.status}")
                if result.error:
                    self.logger.error(f"Error: {result.error}")
                return None

        except Exception as e:
            self.logger.error(f"Distribution failed with error: {str(e)}")
            return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bonus distribution service')
    parser.add_argument('config_file', help='Path to the configuration file')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit (no scheduling)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--env-file', default='.env.bonus', help='Path to environment file')
    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv
    if not load_dotenv(args.env_file):
        print(f"Error: Could not load environment file: {args.env_file}")
        sys.exit(1)

    try:
        service = BonusService(args.config_file)
        service.execute_distribution()
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)