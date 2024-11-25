import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv
import os
import json
from rich.prompt import Prompt, Confirm
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue
import time
import sys
from ui.space_ui import SpaceUI
from art.animations import SpaceAnimation

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value
FEE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG fee

@dataclass
class TokenConfig:
    name: str
    description: str
    amount: int
    decimals: int
    register_list: Optional[List[str]] = None  # Additional R4-R9 registers
    erg_value: float = MIN_BOX_VALUE / ERG_TO_NANOERG

class TokenMinter:
    def __init__(self):
        load_dotenv()
        
        required_vars = [
            'NODE_URL', 'NODE_API_KEY', 'NETWORK_TYPE', 'EXPLORER_URL', 
            'WALLET_ADDRESS'
        ]
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(f"Missing required environment variable: {var}")
        
        self.node_url = os.getenv('NODE_URL')
        self.node_api_key = os.getenv('NODE_API_KEY')
        self.network_type = os.getenv('NETWORK_TYPE')
        self.explorer_url = os.getenv('EXPLORER_URL')
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        
        # Initialize ErgoAppKit with positional arguments
        self.ergo = ErgoAppKit(
            self.node_url,
            self.network_type,
            self.explorer_url,
            self.node_api_key
        )
        
        self.ui = SpaceUI()
        self.animator = SpaceAnimation(self.ui.console)
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def get_token_config_from_user(self) -> TokenConfig:
        """Interactive prompt to get token configuration from user."""
        self.ui.log_info("🎨 Creating New Token Configuration")
        self.ui.log_info("==================================")
        
        # Basic token info
        name = Prompt.ask("📝 Enter token name")
        description = Prompt.ask("📋 Enter token description")
        
        # Amount and decimals with validation
        while True:
            try:
                amount = int(Prompt.ask("💰 Enter total token supply"))
                if amount <= 0:
                    self.ui.log_error("Supply must be greater than 0")
                    continue
                break
            except ValueError:
                self.ui.log_error("Please enter a valid number")
        
        while True:
            try:
                decimals = int(Prompt.ask("🔢 Enter number of decimals (0-18)"))
                if not 0 <= decimals <= 18:
                    self.ui.log_error("Decimals must be between 0 and 18")
                    continue
                break
            except ValueError:
                self.ui.log_error("Please enter a valid number")

        # Optional registers
        register_list = []
        if Confirm.ask("📦 Would you like to add additional register data?"):
            self.ui.log_info("Enter register values (leave blank to skip):")
            for i in range(4, 10):  # R4 to R9
                value = Prompt.ask(f"R{i} value", default="")
                if value:
                    register_list.append(value)

        return TokenConfig(
            name=name,
            description=description,
            amount=amount,
            decimals=decimals,
            register_list=register_list if register_list else None
        )
        
    def create_token_box(self, config: TokenConfig):
        """Create token issuance box using native ErgoAppKit token format."""
        try:
            # First, create the basic box with ERG value
            outbox_value = int(config.erg_value * ERG_TO_NANOERG)
            
            # Create the token with correct parameters
            initial_box = self.ergo.mintToken(
                outbox_value,  # Value in nanoERG
                f"{config.name} - {config.description}",  # Token description
                config.amount,  # Mint amount
                config.decimals,  # Decimals
                self.ergo.contractFromAddress(self.wallet_address)  # Contract
            )
            
            return initial_box
        
        except Exception as e:
            self.ui.log_error(f"Error creating token box: {e}")
            raise
        
    def mint_token(self, config: TokenConfig, debug: bool = True) -> Dict:
        """Execute token minting transaction."""
        try:
            self.ui.display_welcome()
            self.ui.log_info("🚀 Initiating Token Creation Sequence")
            
            # Display configuration summary
            # self.ui.display_token_summary(config)
            
            if debug:
                self.ui.log_warning("🔧 Debug mode active - No transaction will be created")
                try:
                    self.animator.launch_animation()
                    time.sleep(2)
                    return {
                        "status": "debug",
                        "config": vars(config)
                    }
                except Exception as e:
                    self.ui.log_error(f"Animation error in debug mode: {str(e)}")
                    return {
                        "status": "debug_error",
                        "error": str(e)
                    }
            
            # Get confirmation
            if not self.ui.display_confirmation_prompt(30):
                return {"status": "cancelled", "error": "user_cancelled"}
            
            try:
                self.ui.log_info("🔧 Preparing token issuance box...")
                token_box = self.create_token_box(config)
                
                self.ui.log_info("📝 Building transaction...")
                
                # Get input boxes for the transaction
                input_boxes = self.ergo.getUnspentBoxes(self.wallet_address)
                
                # Build the unsigned transaction
                unsigned_tx = self.ergo.buildUnsignedTransaction(
                    input_boxes,
                    [token_box],
                    FEE,
                    self.ergo.contractFromAddress(self.wallet_address).getErgoAddress()
                )
                
                self.ui.log_info("🔐 Signing transaction...")
                signed_tx = self.ergo.signTransactionWithNode(unsigned_tx)
                
                self.ui.log_info("📡 Submitting transaction...")
                tx_id = self.ergo.sendTransaction(signed_tx)
                
                # Show success animation and information
                try:
                    self.animator.launch_animation()
                    
                    explorer_base = self.explorer_url.rstrip('/').replace('/api/v1', '')
                    explorer_link = f"{explorer_base}/transactions/{tx_id}"
                    
                    self.ui.display_success(tx_id, explorer_link)
                    self.animator.success_animation()
                except Exception as e:
                    self.ui.log_error(f"Animation error: {str(e)}")
                
                # Prepare success message
                success_msg = f"""
    <b>🚀 Token Minting Complete</b>
    <b>Token Name</b>: {config.name}
    <b>Amount</b>: {config.amount:,}
    <b>Decimals</b>: {config.decimals}
    <b>Transaction</b>: <a href="{explorer_link}">{tx_id[:6]}...{tx_id[-6:]}</a>
    """
                self.send_telegram_message_sync(success_msg)
                
                return {
                    "status": "completed",
                    "tx_id": tx_id,
                    "explorer_url": explorer_link,
                    "token_config": vars(config)
                }
                
            except Exception as e:
                self.ui.log_error(f"Transaction failed: {str(e)}")
                return {"status": "failed", "error": str(e)}
                
        except Exception as e:
            self.ui.log_error(f"Token minting failed: {str(e)}")
            return {"status": "failed", "error": str(e)}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Mint new tokens on Ergo blockchain.')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--config', help='Path to JSON config file (optional)')
    args = parser.parse_args()
    
    try:
        minter = TokenMinter()
        
        # Get token configuration
        if args.config:
            with open(args.config) as f:
                config_data = json.load(f)
                config = TokenConfig(**config_data)
        else:
            config = minter.get_token_config_from_user()
        
        # Execute minting
        result = minter.mint_token(config, debug=args.debug)
        
        if result["status"] not in ["completed", "debug"]:
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()