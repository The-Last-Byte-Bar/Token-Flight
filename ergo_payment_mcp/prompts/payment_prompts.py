from mcp.server.fastmcp import FastMCP
import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from mcp.server.models import Message, UserMessage, AssistantMessage

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

def register_payment_prompts(mcp: FastMCP):
    """Register payment-related prompts with the MCP server"""
    
    @mcp.prompt()
    def single_payment_prompt(recipient_address: str = "", amount: float = 0, token_id: Optional[str] = None) -> List[Message]:
        """Prompt for sending a single payment"""
        
        # Create basic prompt content
        prompt_content = f"""I want to send a payment on the Ergo blockchain.
        
Recipient address: {recipient_address or "[ENTER RECIPIENT ADDRESS]"}
Amount: {amount or "[ENTER AMOUNT]"}
"""
        
        # Add token info if provided
        if token_id:
            prompt_content += f"Token ID: {token_id}"
        else:
            prompt_content += "Payment type: ERG (native currency)"
        
        # Create formatted messages
        messages = [
            UserMessage(prompt_content),
            AssistantMessage("I'll help you send this Ergo payment. Let me check the details you've provided.")
        ]
        
        return messages
    
    @mcp.prompt()
    def bonus_payment_prompt(config_file: str = "bonus_config.json") -> List[Message]:
        """Prompt for sending bonus payments"""
        
        prompt_content = f"""I want to send bonus payments based on the configuration in {config_file}.

Please:
1. Verify the configuration file contents
2. Confirm the recipients and amounts
3. Execute the bonus payment

If you notice any issues with the configuration, please let me know before proceeding.
"""
        
        messages = [
            UserMessage(prompt_content),
            AssistantMessage("I'll help you send these bonus payments. Let me check the configuration file first.")
        ]
        
        return messages
    
    @mcp.prompt()
    def demurrage_payment_prompt() -> List[Message]:
        """Prompt for executing demurrage payments"""
        
        prompt_content = """I want to execute the demurrage payment distribution.

Please:
1. Check the current wallet balance
2. Verify the demurrage configuration
3. Execute the distribution

If there are any issues or concerns, please let me know before proceeding.
"""
        
        messages = [
            UserMessage(prompt_content),
            AssistantMessage("I'll help you execute the demurrage payment distribution. Let me check the current status first.")
        ]
        
        return messages
    
    @mcp.prompt()
    def bulk_payment_prompt(recipient_file: str = "", token_id: Optional[str] = None) -> List[Message]:
        """Prompt for sending bulk payments"""
        
        prompt_content = f"""I want to send bulk payments to multiple recipients.

Recipient file: {recipient_file or "[ENTER RECIPIENT FILE PATH]"}
"""
        
        # Add token info if provided
        if token_id:
            prompt_content += f"\nToken ID: {token_id} (sending tokens)"
        else:
            prompt_content += "\nPayment type: ERG (native currency)"
        
        prompt_content += """

Please:
1. Verify the recipient file contents
2. Confirm the total amount and number of recipients
3. Execute the bulk payment

If you notice any issues, please let me know before proceeding.
"""
        
        messages = [
            UserMessage(prompt_content),
            AssistantMessage("I'll help you send these bulk payments. Let me check the recipient file first.")
        ]
        
        return messages
    
    @mcp.prompt()
    def create_config_prompt(config_type: str = "bonus") -> List[Message]:
        """Prompt for creating a payment configuration"""
        
        if config_type.lower() == "bonus":
            prompt_content = """I want to create a bonus payment configuration.

Please help me:
1. Specify the token ID (if distributing tokens)
2. Define recipients and their amounts
3. Create and save the configuration file

The configuration should follow the structure from the bonus config schema.
"""
        elif config_type.lower() == "demurrage":
            prompt_content = """I want to create a demurrage payment configuration.

Please help me:
1. Specify the collector address
2. Define the blocks per distribution cycle
3. Set the distribution percentage
4. List recipient addresses
5. Create and save the configuration file

The configuration should follow the structure from the demurrage config schema.
"""
        else:  # Generic config
            prompt_content = f"""I want to create a {config_type} payment configuration.

Please help me define the necessary parameters and create the configuration file.
"""
        
        messages = [
            UserMessage(prompt_content),
            AssistantMessage(f"I'll help you create a {config_type} payment configuration. Let's start by reviewing the necessary parameters.")
        ]
        
        return messages
    
    @mcp.prompt()
    def wallet_setup_prompt() -> List[Message]:
        """Prompt for setting up a wallet configuration"""
        
        prompt_content = """I want to set up my wallet configuration for Ergo payments.

Please help me:
1. Configure the node URL
2. Set the network type (mainnet or testnet)
3. Configure the explorer URL
4. Set my wallet address
5. Create the wallet configuration file

I'll need to separately set up my wallet mnemonic as an environment variable for security.
"""
        
        messages = [
            UserMessage(prompt_content),
            AssistantMessage("I'll help you set up your wallet configuration for Ergo payments. Let's go through the required parameters.")
        ]
        
        return messages

    return mcp 