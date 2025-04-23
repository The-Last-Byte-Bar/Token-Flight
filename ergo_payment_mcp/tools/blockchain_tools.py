from mcp.server.fastmcp import FastMCP
import os
import sys
import json
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the existing codebase modules if needed
from src.validate_address import validate_address

logger = logging.getLogger(__name__)

# Constants
ERG_TO_NANOERG = int(1e9)

def register_blockchain_tools(mcp: FastMCP):
    """Register blockchain analysis tools with the MCP server"""
    
    @mcp.tool()
    def get_address_info(address: str) -> str:
        """
        Get information about an Ergo address
        
        Args:
            address: Ergo blockchain address
            
        Returns:
            Information about the address
        """
        try:
            # This is a simplified validation since we don't have mnemonic to validate with
            if not address or not address.startswith('9'):
                return f"Invalid Ergo address format: {address}"
                
            # Use Ergo Explorer API to get address information
            api_url = "https://api.ergoplatform.com/api/v1"
            response = requests.get(f"{api_url}/addresses/{address}")
            response.raise_for_status()
            
            address_data = response.json()
            
            # Get transactions
            tx_response = requests.get(f"{api_url}/addresses/{address}/transactions?limit=5")
            tx_response.raise_for_status()
            tx_data = tx_response.json()
            
            # Format the output
            info = {
                "address": address,
                "balance": {
                    "confirmed": address_data.get('confirmed', {}).get('nanoErgs', 0) / ERG_TO_NANOERG,
                    "unconfirmed": address_data.get('unconfirmed', {}).get('nanoErgs', 0) / ERG_TO_NANOERG
                },
                "transactions": {
                    "total": address_data.get('transactionsCount', 0),
                    "recent": [
                        {
                            "id": tx.get('id'),
                            "timestamp": tx.get('timestamp'),
                            "confirmations": tx.get('numConfirmations', 0)
                        } for tx in tx_data.get('items', [])[:5]
                    ]
                }
            }
            
            return json.dumps(info, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting address info: {str(e)}")
            return f"Error getting address info: {str(e)}"
    
    @mcp.tool()
    def get_transaction_info(tx_id: str) -> str:
        """
        Get information about a transaction
        
        Args:
            tx_id: Transaction ID (hash)
            
        Returns:
            Information about the transaction
        """
        try:
            # Use Ergo Explorer API to get transaction information
            api_url = "https://api.ergoplatform.com/api/v1"
            response = requests.get(f"{api_url}/transactions/{tx_id}")
            response.raise_for_status()
            
            tx_data = response.json()
            
            # Format the output
            info = {
                "id": tx_data.get('id'),
                "timestamp": tx_data.get('timestamp'),
                "size": tx_data.get('size'),
                "confirmations": tx_data.get('numConfirmations', 0),
                "inputs": [
                    {
                        "address": input_box.get('address'),
                        "value": input_box.get('value', 0) / ERG_TO_NANOERG,
                    } for input_box in tx_data.get('inputs', [])
                ],
                "outputs": [
                    {
                        "address": output_box.get('address'),
                        "value": output_box.get('value', 0) / ERG_TO_NANOERG,
                        "assets": [
                            {
                                "tokenId": token.get('tokenId'),
                                "amount": token.get('amount', 0)
                            } for token in output_box.get('assets', [])
                        ]
                    } for output_box in tx_data.get('outputs', [])
                ]
            }
            
            return json.dumps(info, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting transaction info: {str(e)}")
            return f"Error getting transaction info: {str(e)}"
    
    @mcp.tool()
    def get_network_status() -> str:
        """
        Get current Ergo network status
        
        Returns:
            Information about the Ergo network
        """
        try:
            # Use Ergo Explorer API to get network information
            api_url = "https://api.ergoplatform.com/api/v1"
            info_response = requests.get(f"{api_url}/info")
            info_response.raise_for_status()
            
            # Get latest blocks
            blocks_response = requests.get(f"{api_url}/blocks?limit=5")
            blocks_response.raise_for_status()
            
            info_data = info_response.json()
            blocks_data = blocks_response.json()
            
            # Format the output
            info = {
                "network": info_data.get('network'),
                "current_height": info_data.get('currentHeight'),
                "latest_blocks": [
                    {
                        "height": block.get('height'),
                        "timestamp": block.get('timestamp'),
                        "transactions": block.get('transactionsCount', 0),
                        "miner": block.get('miner', {}).get('name', 'Unknown')
                    } for block in blocks_data.get('items', [])
                ]
            }
            
            return json.dumps(info, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting network status: {str(e)}")
            return f"Error getting network status: {str(e)}"
    
    @mcp.tool()
    def search_token(token_query: str) -> str:
        """
        Search for tokens on the Ergo blockchain
        
        Args:
            token_query: Token name or ID to search for
            
        Returns:
            Information about matching tokens
        """
        try:
            # Use Ergo Explorer API to search for tokens
            api_url = "https://api.ergoplatform.com/api/v1"
            
            # Try to search by ID first
            if len(token_query) > 40:  # Likely a token ID
                response = requests.get(f"{api_url}/tokens/{token_query}")
                if response.status_code == 200:
                    token_data = response.json()
                    return json.dumps({
                        "id": token_data.get('id'),
                        "name": token_data.get('name'),
                        "description": token_data.get('description'),
                        "decimals": token_data.get('decimals', 0),
                        "type": token_data.get('type'),
                        "emissionAmount": token_data.get('emissionAmount')
                    }, indent=2)
            
            # Otherwise search by name
            response = requests.get(f"{api_url}/tokens/search?query={token_query}")
            response.raise_for_status()
            
            tokens_data = response.json()
            
            # Format the output
            info = {
                "query": token_query,
                "results": [
                    {
                        "id": token.get('id'),
                        "name": token.get('name'),
                        "description": token.get('description'),
                        "decimals": token.get('decimals', 0)
                    } for token in tokens_data.get('items', [])[:10]  # Limit to 10 results
                ]
            }
            
            return json.dumps(info, indent=2)
            
        except Exception as e:
            logger.error(f"Error searching for token: {str(e)}")
            return f"Error searching for token: {str(e)}"

    return mcp 