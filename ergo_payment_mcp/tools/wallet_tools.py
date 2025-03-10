from mcp.server.fastmcp import FastMCP
import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any, Tuple

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the existing codebase modules
from src.multi_output_builder import MultiOutputBuilder
from src.validate_address import validate_address
from src.nautilus_wallet import NautilusWallet

logger = logging.getLogger(__name__)

def register_wallet_tools(mcp: FastMCP):
    """Register wallet management tools with the MCP server"""
    
    @mcp.tool()
    def estimate_transaction_fee(recipient_count: int) -> str:
        """
        Estimate the transaction fee for a payment
        
        Args:
            recipient_count: Number of recipients in the transaction
            
        Returns:
            Estimated transaction fee
        """
        try:
            # Constants for fee calculation
            ERG_TO_NANOERG = int(1e9)
            BASE_FEE = 0.001  # ERG
            FEE_PER_RECIPIENT = 0.0001  # ERG
            
            # Calculate fee
            fee = BASE_FEE + (FEE_PER_RECIPIENT * max(0, recipient_count - 1))
            
            # Format output
            return json.dumps({
                "recipients": recipient_count,
                "estimated_fee": fee,
                "estimated_fee_nano": int(fee * ERG_TO_NANOERG),
                "note": "This is an estimate and actual fees may vary"
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Error estimating transaction fee: {str(e)}")
            return f"Error estimating transaction fee: {str(e)}"
    
    @mcp.tool()
    def create_wallet_config(node_url: str, network_type: str, explorer_url: str, wallet_address: str) -> str:
        """
        Create wallet configuration for use in payment operations
        
        Args:
            node_url: URL of the Ergo node
            network_type: Network type (mainnet or testnet)
            explorer_url: URL of the Ergo explorer
            wallet_address: Wallet address
            
        Returns:
            Wallet configuration in JSON format
        """
        try:
            # Simple validation instead of using validate_address which requires a mnemonic
            if not wallet_address or not wallet_address.startswith('9'):
                return f"Invalid Ergo address format: {wallet_address}"
                
            # Create configuration
            config = {
                "wallet": {
                    "node_url": node_url,
                    "network_type": network_type,
                    "explorer_url": explorer_url,
                    "wallet_address": wallet_address
                }
            }
            
            # Save config to a temporary file
            temp_config_file = "temp_wallet_config.json"
            with open(temp_config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            return f"Wallet configuration created and saved to {temp_config_file}. Please add 'WALLET_MNEMONIC' to your environment variables for full functionality."
            
        except Exception as e:
            logger.error(f"Error creating wallet config: {str(e)}")
            return f"Error creating wallet config: {str(e)}"
    
    @mcp.tool()
    def create_transaction_manifest(recipients: List[Dict[str, Any]], 
                                   token_id: Optional[str] = None,
                                   save_to_file: str = "transaction_manifest.json") -> str:
        """
        Create a transaction manifest for bulk payments
        
        Args:
            recipients: List of recipient dictionaries with 'address' and 'amount' keys
            token_id: Optional token ID if sending a token
            save_to_file: Filename to save the manifest
            
        Returns:
            Success message or error
        """
        try:
            # Validate recipients
            for i, recipient in enumerate(recipients):
                address = recipient.get('address', '')
                amount = recipient.get('amount', 0)
                
                # Simple validation instead of using validate_address which requires a mnemonic
                if not address or not address.startswith('9'):
                    return f"Invalid Ergo address format at index {i}: {address}"
                    
                if amount <= 0:
                    return f"Invalid amount at index {i}: {amount}"
            
            # Create manifest
            manifest = {
                "transaction_type": "token" if token_id else "erg",
                "token_id": token_id,
                "recipients": recipients
            }
            
            # Save manifest to file
            with open(save_to_file, 'w') as f:
                json.dump(manifest, f, indent=2)
                
            return f"Transaction manifest created and saved to {save_to_file}"
            
        except Exception as e:
            logger.error(f"Error creating transaction manifest: {str(e)}")
            return f"Error creating transaction manifest: {str(e)}"
    
    @mcp.tool()
    def generate_wallet_backup_instructions() -> str:
        """
        Generate instructions for backing up an Ergo wallet
        
        Returns:
            Wallet backup instructions
        """
        instructions = """
        # Ergo Wallet Backup Instructions

        ## Mnemonic Backup (Most Important)

        1. **Find your mnemonic phrase**: This is a list of 15 words that can restore your wallet.
        2. **Write it down on paper**: Never store it digitally or take a screenshot.
        3. **Store it securely**: Use a safe, safe deposit box, or other secure location.
        4. **Create multiple copies**: Store them in different secure locations.
        5. **Never share your mnemonic**: Anyone with your mnemonic has full access to your funds.

        ## Nautilus Wallet Specific Instructions

        1. Open Nautilus wallet
        2. Click on the settings (gear icon)
        3. Select "Security"
        4. Choose "Backup Wallet"
        5. Enter your password if prompted
        6. Write down the 15 words in the exact order shown
        7. Verify your backup by following the verification steps

        Remember that the mnemonic phrase is all that's needed to restore your wallet on any device.
        """
        
        return instructions

    @mcp.resource("config://wallet_types")
    def get_wallet_types() -> str:
        """Get available wallet types for Ergo"""
        wallet_types = {
            "wallet_types": [
                {
                    "name": "Nautilus",
                    "description": "Browser extension wallet for Ergo",
                    "website": "https://nautilus.cloud/",
                    "supported_features": ["Tokens", "dApps", "NFTs"]
                },
                {
                    "name": "Node Wallet",
                    "description": "Built-in wallet in Ergo node",
                    "supported_features": ["Advanced features", "Scripting"]
                },
                {
                    "name": "Mobile Wallet",
                    "description": "Official Ergo mobile wallet",
                    "website": "https://ergoplatform.org/en/wallets/",
                    "supported_features": ["Mobile access", "Basic transactions"]
                }
            ]
        }
        
        return json.dumps(wallet_types, indent=2)

    return mcp 