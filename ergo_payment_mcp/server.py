from mcp.server.fastmcp import FastMCP, Context, Image
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the existing codebase modules
from src.models import AirdropConfig, TokenConfig, WalletConfig, AirdropRecipient, RecipientAmount
from src.base_airdrop import BaseAirdrop
from src.bonus_service import BonusService
from src.demurrage_service import DemurrageService
from src.multi_output_builder import MultiOutputBuilder

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create an MCP server
mcp = FastMCP("Ergo Payment Server", 
              description="MCP server for Ergo blockchain payments and distributions",
              dependencies=["typing", "logging", "requests", "pandas", "dataclasses"])

# Helper functions
def load_config(config_path: str) -> dict:
    """Load a configuration file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {str(e)}")
        raise

def get_wallet_config() -> WalletConfig:
    """Get wallet configuration from environment variables"""
    return WalletConfig(
        node_url=os.getenv('NODE_URL'),
        network_type=os.getenv('NETWORK_TYPE'),
        explorer_url=os.getenv('EXPLORER_URL'),
        wallet_mnemonic=os.getenv('WALLET_MNEMONIC'),
        mnemonic_password=os.getenv('MNEMONIC_PASSWORD', ''),
        node_wallet_address=os.getenv('WALLET_ADDRESS')
    )

# Resources
@mcp.resource("config://wallet")
def get_wallet_info() -> str:
    """Get wallet configuration info (without sensitive data)"""
    wallet_config = get_wallet_config()
    # Return non-sensitive data
    return json.dumps({
        "node_url": wallet_config.node_url,
        "network_type": wallet_config.network_type,
        "explorer_url": wallet_config.explorer_url,
        "wallet_address": wallet_config.node_wallet_address
    }, indent=2)

@mcp.resource("config://bonus")
def get_bonus_config() -> str:
    """Get bonus payment configuration"""
    try:
        return json.dumps(load_config("bonus_config.json"), indent=2)
    except Exception as e:
        return f"Error loading bonus config: {str(e)}"

@mcp.resource("config://{config_name}")
def get_config(config_name: str) -> str:
    """Get a configuration file by name"""
    try:
        return json.dumps(load_config(f"{config_name}.json"), indent=2)
    except Exception as e:
        return f"Error loading config {config_name}: {str(e)}"

@mcp.resource("balance://wallet")
def get_wallet_balance() -> str:
    """Get current wallet balance"""
    demurrage_service = DemurrageService(debug=False)
    balance = demurrage_service.get_wallet_balance()
    return f"Current wallet balance: {balance} ERG"

# Tools
@mcp.tool()
def send_payment(recipient_address: str, amount: float, token_id: Optional[str] = None) -> str:
    """
    Send a payment to a single recipient
    
    Args:
        recipient_address: Ergo blockchain address to send payment to
        amount: Amount to send (in ERG or token units)
        token_id: Optional token ID (if sending a token)
    
    Returns:
        Transaction ID or error message
    """
    try:
        wallet_config = get_wallet_config()
        
        # Create a simple airdrop config for single payment
        config = AirdropConfig(
            wallet_config=wallet_config,
            token_configs=[]
        )
        
        # Add token config if sending a token
        if token_id:
            token_config = TokenConfig(
                token_id=token_id,
                amount_per_recipient=amount,
                total_amount=amount,
                decimal_places=0  # This would need to be determined dynamically
            )
            config.token_configs.append(token_config)
        
        # Create airdrop with single recipient
        airdrop = BaseAirdrop(config)
        
        # Create recipient
        recipient = AirdropRecipient(
            address=recipient_address,
            amount=amount if not token_id else None  # Amount is ERG if no token_id
        )
        
        # Prepare outputs and execute
        outputs = airdrop.prepare_outputs([recipient], config.token_configs)
        result = airdrop.execute()
        
        if result.success:
            return f"Payment sent successfully. Transaction ID: {result.tx_id}"
        else:
            return f"Payment failed: {result.error_message}"
    
    except Exception as e:
        logger.error(f"Error sending payment: {str(e)}")
        return f"Error sending payment: {str(e)}"

@mcp.tool()
def send_bonus_payment(config_file: str = "bonus_config.json") -> str:
    """
    Send bonus payments based on a configuration file
    
    Args:
        config_file: Path to the bonus configuration file
        
    Returns:
        Transaction ID or error message
    """
    try:
        bonus_service = BonusService(config_file)
        tx_id = bonus_service.execute_distribution()
        
        if tx_id:
            return f"Bonus payments sent successfully. Transaction ID: {tx_id}"
        else:
            return "Bonus payments failed. See logs for details."
    
    except Exception as e:
        logger.error(f"Error sending bonus payments: {str(e)}")
        return f"Error sending bonus payments: {str(e)}"

@mcp.tool()
def send_demurrage_payment() -> str:
    """
    Execute demurrage payment distribution
    
    Returns:
        Transaction ID or error message
    """
    try:
        demurrage_service = DemurrageService(debug=False)
        # Get the last 10 block heights for simplicity
        # In a real scenario, you'd want to determine this differently
        block_heights = list(range(demurrage_service.collector.get_current_height() - 10, 
                                   demurrage_service.collector.get_current_height()))
        
        tx_id = demurrage_service.execute_distribution(block_heights)
        
        if tx_id:
            return f"Demurrage payments sent successfully. Transaction ID: {tx_id}"
        else:
            return "Demurrage payments failed. See logs for details."
    
    except Exception as e:
        logger.error(f"Error sending demurrage payments: {str(e)}")
        return f"Error sending demurrage payments: {str(e)}"

@mcp.tool()
def send_bulk_payments(recipient_file: str, token_id: Optional[str] = None) -> str:
    """
    Send payments to multiple recipients from a file
    
    Args:
        recipient_file: JSON file with recipient addresses and amounts
        token_id: Optional token ID if sending a token
        
    Returns:
        Transaction ID or error message
    """
    try:
        # Load recipients from file
        recipients_data = load_config(recipient_file)
        wallet_config = get_wallet_config()
        
        # Create config
        config = AirdropConfig(
            wallet_config=wallet_config,
            token_configs=[]
        )
        
        # Add token config if sending tokens
        if token_id:
            total_amount = sum(r.get("amount", 0) for r in recipients_data)
            token_config = TokenConfig(
                token_id=token_id,
                total_amount=total_amount,
                decimal_places=0  # This would need to be determined dynamically
            )
            config.token_configs.append(token_config)
        
        # Create airdrop
        airdrop = BaseAirdrop(config)
        
        # Create recipients
        recipients = []
        for r in recipients_data:
            recipient = AirdropRecipient(
                address=r.get("address"),
                amount=r.get("amount") if not token_id else None
            )
            recipients.append(recipient)
        
        # Prepare outputs and execute
        outputs = airdrop.prepare_outputs(recipients, config.token_configs)
        result = airdrop.execute()
        
        if result.success:
            return f"Bulk payments sent successfully. Transaction ID: {result.tx_id}"
        else:
            return f"Bulk payments failed: {result.error_message}"
    
    except Exception as e:
        logger.error(f"Error sending bulk payments: {str(e)}")
        return f"Error sending bulk payments: {str(e)}"

@mcp.tool()
def check_address_validity(address: str) -> str:
    """
    Check if an Ergo address is valid
    
    Args:
        address: Ergo blockchain address to validate
        
    Returns:
        Validation result
    """
    try:
        from src.validate_address import validate_ergo_address
        
        is_valid = validate_ergo_address(address)
        if is_valid:
            return f"The address {address} is a valid Ergo address."
        else:
            return f"The address {address} is NOT a valid Ergo address."
    
    except Exception as e:
        logger.error(f"Error validating address: {str(e)}")
        return f"Error validating address: {str(e)}"

@mcp.tool()
def create_config_file(config_name: str, config_data: Dict[str, Any]) -> str:
    """
    Create a new configuration file
    
    Args:
        config_name: Name of the configuration file (without extension)
        config_data: Configuration data in dictionary format
        
    Returns:
        Success message or error
    """
    try:
        filename = f"{config_name}.json"
        with open(filename, 'w') as f:
            json.dump(config_data, f, indent=2)
        return f"Configuration file {filename} created successfully."
    
    except Exception as e:
        logger.error(f"Error creating config file: {str(e)}")
        return f"Error creating config file: {str(e)}"

# Prompts
@mcp.prompt()
def send_payment_prompt() -> str:
    """Prompt for sending a payment"""
    return """
    I want to send a payment on the Ergo blockchain. Please help me with this process.
    
    I need to specify:
    1. The recipient's address
    2. The amount to send
    3. Whether I'm sending ERG or a token (if token, I'll need to provide the token ID)
    
    Once I provide this information, you can help me send the payment.
    """

@mcp.prompt()
def send_bulk_payments_prompt() -> str:
    """Prompt for sending bulk payments"""
    return """
    I need to send payments to multiple recipients on the Ergo blockchain.
    
    Please help me:
    1. Create a JSON file with recipient addresses and amounts
    2. Execute the bulk payment
    
    The file format should be a JSON array with objects containing "address" and "amount" fields.
    """

# Start the server if executed directly
if __name__ == "__main__":
    mcp.run() 