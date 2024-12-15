import logging
from typing import List, Dict, Optional, Union
import sys
import time
from decimal import Decimal
import asyncio
from datetime import datetime
from pathlib import Path

from base_airdrop import BaseAirdrop
from models import (
    AirdropRecipient, DistributionConfig, AirdropError,
    ERG_TO_NANOERG, MIN_BOX_VALUE
)
from recipient_manager import RecipientManager
from ui.space_ui import SpaceUI
from art.animations import SpaceAnimation

class SingleTokenAirdrop(BaseAirdrop):
    """Handles distribution of a single token to multiple recipients"""
    
    def __init__(self, log_dir: str = "logs"):
        # Initialize base class first
        super().__init__()
        
        # Configure additional logging
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        log_file = self.log_dir / f"airdrop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        
        # Initialize additional components
        self.animator = SpaceAnimation(self.ui.console)
        
        # Initialize optional Telegram notifications if configured
        self.telegram_token = self.config.get('telegram_bot_token')
        self.telegram_chat_id = self.config.get('telegram_chat_id')
        self.telegram = None
        if self.telegram_token and self.telegram_chat_id:
            from telegram.ext import Application
            self.telegram = Application.builder().token(self.telegram_token).build()

    async def notify_telegram(self, message: str):
        """Send notification to Telegram"""
        if self.telegram and self.telegram_chat_id:
            try:
                await self.telegram.bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                self.logger.error(f"Failed to send Telegram message: {e}")

    def notify_telegram_sync(self, message: str):
        """Synchronous wrapper for sending Telegram notifications"""
        if self.telegram:
            try:
                asyncio.run(self.notify_telegram(message))
            except Exception as e:
                self.logger.error(f"Failed to send Telegram notification: {e}")

    def save_transaction_record(self, tx_data: Dict):
        """Save transaction details to JSON file"""
        import json
        tx_file = self.log_dir / f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(tx_file, 'w') as f:
            json.dump(tx_data, f, indent=2)
        self.logger.info(f"Transaction record saved to {tx_file}")

    def execute_airdrop(self, token_name: str, recipients: List[AirdropRecipient],
                       total_amount: Optional[float] = None,
                       amount_per_recipient: Optional[float] = None,
                       debug: bool = False) -> Dict:
        """
        Execute single token airdrop.
        
        Args:
            token_name: Name of token to distribute
            recipients: List of recipients
            total_amount: Total amount to distribute
            amount_per_recipient: Amount per recipient
            debug: If True, validate without executing transaction
            
        Returns:
            Dict containing transaction results
        """
        try:
            self.logger.info(f"Starting airdrop for {token_name}")
            self.notify_telegram_sync(f"🚀 Starting {token_name} airdrop to {len(recipients)} recipients")
            
            # Display welcome screens
            self.ui.display_welcome()
            self.ui.display_assumptions()
            
            # Get wallet configuration
            use_node, active_address = self.builder.wallet_manager.get_signing_config()
            self.logger.debug(f"Using {'node' if use_node else 'mnemonic'} signing with address: {active_address}")
            
            # Get token details
            token_id, token_decimals = self.get_token_data(token_name)
            is_erg = token_id is None
            self.logger.debug(f"Token details - ID: {token_id}, Decimals: {token_decimals}")
            
            # Calculate amounts
            self.logger.debug("Calculating distribution amounts...")
            amounts = self.prepare_amounts(
                total_amount=total_amount,
                amount_per_recipient=amount_per_recipient,
                recipient_count=len(recipients),
                decimals=token_decimals
            )
            
            # Create output boxes
            self.logger.debug("Creating output boxes...")
            outputs = self.create_output_boxes(recipients, amounts, token_id)
            
            # Calculate totals
            total_amount_actual = sum(amount / (10 ** token_decimals) for amount in amounts)
            total_erg_needed = (
                total_amount_actual if is_erg 
                else self.builder.estimate_transaction_cost(len(recipients))
            )
            
            self.logger.debug(f"Total amount: {total_amount_actual} {token_name}")
            self.logger.debug(f"Total ERG needed: {total_erg_needed}")
            
            # Display distribution summary
            self.ui.display_summary(
                token_name=token_name,
                recipients_count=len(recipients),
                total_amount=total_amount_actual,
                total_erg=total_erg_needed,
                total_hashrate=sum(r.hashrate for r in recipients),
                decimals=token_decimals
            )
            
            # Check balances
            self.logger.debug("Checking wallet balances...")
            erg_balance, token_balances = self.builder.get_wallet_balances(active_address)
            token_balance = (
                erg_balance if is_erg 
                else token_balances.get(token_id, 0) / (10 ** token_decimals)
            )
            
            self.logger.debug(f"ERG Balance: {erg_balance}")
            self.logger.debug(f"Token Balance: {token_balance}")
            
            # Display current balances
            self.ui.display_wallet_balance(
                token_name=token_name,
                erg_balance=erg_balance,
                token_balance=token_balance,
                decimals=token_decimals
            )
            
            # Validate balances
            self.validate_transaction_resources(
                erg_balance=erg_balance,
                token_balance=token_balance,
                required_erg=total_erg_needed,
                required_tokens=total_amount_actual,
                token_name=token_name,
                decimals=token_decimals
            )
            
            if debug:
                self.logger.info("Debug mode - No transaction will be created")
                debug_data = {
                    "status": "debug",
                    "recipients": len(recipients),
                    "total_amount": total_amount_actual,
                    "total_erg": total_erg_needed,
                    "signing_method": "node" if use_node else "mnemonic",
                    "active_address": active_address,
                    "distribution": [
                        {
                            "address": r.address,
                            "amount": a / (10 ** token_decimals)
                        }
                        for r, a in zip(recipients, amounts)
                    ]
                }
                self.save_transaction_record(debug_data)
                self.notify_telegram_sync("✅ Debug run completed successfully")
                return debug_data
            
            # Get user confirmation
            if not self.ui.display_confirmation_prompt(30):
                self.notify_telegram_sync("❌ Airdrop cancelled by user")
                return {"status": "cancelled", "error": "user_cancelled"}
            
            # Execute transaction
            self.logger.debug("Creating transaction...")
            self.notify_telegram_sync("🔄 Creating transaction...")
            tx_id = self.builder.create_multi_output_tx(outputs, active_address)
            
            # Generate explorer link
            explorer_base = self.config['explorer_url'].rstrip('/').replace('/api/v1', '')
            explorer_link = f"{explorer_base}/transactions/{tx_id}"
            
            # Log success
            success_msg = (
                f"✅ Token flight successful!\n"
                f"Transaction: {explorer_link}\n\n"
                f"Distribution:\n"
                f"- {token_name}: {total_amount_actual:,.{token_decimals}f}"
            )
            
            self.notify_telegram_sync(success_msg)
            self.logger.info(f"Transaction created successfully: {tx_id}")
            self.ui.display_success(tx_id, explorer_link)
            
            # Save transaction record
            tx_data = {
                "status": "completed",
                "tx_id": tx_id,
                "explorer_url": explorer_link,
                "token_name": token_name,
                "recipients": len(recipients),
                "total_amount": total_amount_actual,
                "total_erg": total_erg_needed,
                "signing_method": "node" if use_node else "mnemonic",
                "active_address": active_address,
                "timestamp": datetime.now().isoformat()
            }
            self.save_transaction_record(tx_data)
            
            return tx_data
            
        except Exception as e:
            error_msg = f"Airdrop execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui.display_error(f"Mission failed: {str(e)}")
            self.notify_telegram_sync(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": str(e),
                "signing_method": "node" if 'use_node' in locals() else "unknown",
                "active_address": active_address if 'active_address' in locals() else None
            }