from mcp.server.fastmcp import FastMCP
import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any, Tuple

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

def register_payment_resources(mcp: FastMCP):
    """Register payment-related resources with the MCP server"""
    
    @mcp.resource("payments://templates")
    def get_payment_templates() -> str:
        """Get available payment templates"""
        templates = {
            "templates": [
                {
                    "name": "single_payment",
                    "description": "Send a payment to a single recipient",
                    "parameters": [
                        {
                            "name": "recipient_address",
                            "type": "string",
                            "description": "Ergo address of the recipient"
                        },
                        {
                            "name": "amount",
                            "type": "number",
                            "description": "Amount to send"
                        },
                        {
                            "name": "token_id",
                            "type": "string",
                            "description": "Optional token ID if sending a token",
                            "required": False
                        }
                    ]
                },
                {
                    "name": "bonus_payment",
                    "description": "Send bonus payments according to configuration",
                    "parameters": [
                        {
                            "name": "config_file",
                            "type": "string",
                            "description": "Path to the bonus configuration file",
                            "default": "bonus_config.json"
                        }
                    ]
                },
                {
                    "name": "demurrage_payment",
                    "description": "Execute demurrage payment distribution",
                    "parameters": []
                },
                {
                    "name": "bulk_payment",
                    "description": "Send payments to multiple recipients",
                    "parameters": [
                        {
                            "name": "recipient_file",
                            "type": "string",
                            "description": "JSON file with recipient addresses and amounts"
                        },
                        {
                            "name": "token_id",
                            "type": "string",
                            "description": "Optional token ID if sending a token",
                            "required": False
                        }
                    ]
                }
            ]
        }
        
        return json.dumps(templates, indent=2)
    
    @mcp.resource("payments://bonus/schema")
    def get_bonus_schema() -> str:
        """Get the schema for bonus payment configuration"""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Bonus Payment Configuration",
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "Token ID to distribute as bonus (optional)",
                    "examples": ["0cd8c9f416e5b1ca9f986a7f10a84191dfb85941619e49e53c0dc30ebf83324b"]
                },
                "decimal_places": {
                    "type": "integer",
                    "description": "Number of decimal places for the token",
                    "default": 0,
                    "minimum": 0
                },
                "recipients": {
                    "type": "array",
                    "description": "List of recipients to receive bonus payments",
                    "items": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "Ergo address of the recipient"
                            },
                            "amount": {
                                "type": "number",
                                "description": "Amount to send to this recipient"
                            }
                        },
                        "required": ["address", "amount"]
                    }
                }
            },
            "required": ["recipients"]
        }
        
        return json.dumps(schema, indent=2)
    
    @mcp.resource("payments://demurrage/schema")
    def get_demurrage_schema() -> str:
        """Get the schema for demurrage payment configuration"""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Demurrage Payment Configuration",
            "type": "object",
            "properties": {
                "collector_address": {
                    "type": "string",
                    "description": "Address collecting the demurrage fees"
                },
                "blocks_per_distribution": {
                    "type": "integer",
                    "description": "Number of blocks per distribution cycle",
                    "default": 10,
                    "minimum": 1
                },
                "distribution_percentage": {
                    "type": "number",
                    "description": "Percentage of collected fees to distribute",
                    "default": 90,
                    "minimum": 0,
                    "maximum": 100
                },
                "recipient_addresses": {
                    "type": "array",
                    "description": "List of recipient addresses for distribution",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["collector_address", "recipient_addresses"]
        }
        
        return json.dumps(schema, indent=2)
    
    @mcp.resource("payments://sample/bonus")
    def get_sample_bonus_config() -> str:
        """Get a sample bonus payment configuration"""
        sample = {
            "token_id": "0cd8c9f416e5b1ca9f986a7f10a84191dfb85941619e49e53c0dc30ebf83324b",
            "decimal_places": 0,
            "recipients": [
                {
                    "address": "9fLf54PVmRiy7DTNEsNTK2hWwTaB9rrJkgHYgjy8tJeSkQJPx6F",
                    "amount": 10
                },
                {
                    "address": "9gYxoYyDDo8r8yvWE8QTQCxHqVvcuL4me7nU8NbUXnwLrGgL3bK",
                    "amount": 15
                },
                {
                    "address": "9hNBoM3Dur8EhKnxdmS121HDJbA3q1TCFsGzTz5hKoJmRxR3LgL",
                    "amount": 20
                }
            ]
        }
        
        return json.dumps(sample, indent=2)
    
    @mcp.resource("payments://sample/demurrage")
    def get_sample_demurrage_config() -> str:
        """Get a sample demurrage payment configuration"""
        sample = {
            "collector_address": "9fE5o7913CKKe6wvNgM11vULjTuKiopPcvCaj7t2zcJWXM2gcLu",
            "blocks_per_distribution": 10,
            "distribution_percentage": 90,
            "recipient_addresses": [
                "9fLf54PVmRiy7DTNEsNTK2hWwTaB9rrJkgHYgjy8tJeSkQJPx6F",
                "9gYxoYyDDo8r8yvWE8QTQCxHqVvcuL4me7nU8NbUXnwLrGgL3bK",
                "9hNBoM3Dur8EhKnxdmS121HDJbA3q1TCFsGzTz5hKoJmRxR3LgL"
            ]
        }
        
        return json.dumps(sample, indent=2)
    
    @mcp.resource("payments://history")
    def get_payment_history() -> str:
        """Get payment history (placeholder - would need real implementation)"""
        # This is a placeholder - in a real implementation this would read from a database
        history = {
            "history": [
                {
                    "id": "tx1",
                    "type": "single_payment",
                    "timestamp": "2023-07-15T14:32:21Z",
                    "recipient": "9fLf54PVmRiy7DTNEsNTK2hWwTaB9rrJkgHYgjy8tJeSkQJPx6F",
                    "amount": 1.5,
                    "status": "confirmed"
                },
                {
                    "id": "tx2",
                    "type": "bonus_payment",
                    "timestamp": "2023-07-10T09:15:43Z",
                    "recipients": 3,
                    "total_amount": 45,
                    "token_id": "0cd8c9f416e5b1ca9f986a7f10a84191dfb85941619e49e53c0dc30ebf83324b",
                    "status": "confirmed"
                },
                {
                    "id": "tx3",
                    "type": "demurrage_payment",
                    "timestamp": "2023-07-05T18:03:12Z",
                    "recipients": 3,
                    "total_amount": 0.75,
                    "status": "confirmed"
                }
            ]
        }
        
        return json.dumps(history, indent=2)

    return mcp 