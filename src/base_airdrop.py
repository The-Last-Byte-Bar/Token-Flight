from typing import List, Dict, Optional, Union, Tuple
import logging
from decimal import Decimal
import pandas as pd
import requests

from models import (
    AirdropConfig, TokenConfig, WalletConfig, AirdropRecipient,
    TransactionResult
)
from multi_output_builder import MultiOutputBuilder, OutputBox
from recipient_manager import RecipientManager
from ui.base_ui import BaseUI

ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)

from multi_output_builder import (
    ERG_TO_NANOERG,
    MIN_BOX_VALUE,
    FEE,
    PROTOCOL_FEE,
    PROTOCOL_FEE_ADDRESS
)

class BaseAirdrop:
    """Base class for airdrop operations"""
    
    def __init__(self, config: AirdropConfig, ui: Optional[BaseUI] = None):
        self.config = config
        self.ui = ui
        self.logger = logging.getLogger(__name__)
        
        # Initialize builder
        self.builder = MultiOutputBuilder(
            node_url=config.wallet_config.node_url,
            network_type=config.wallet_config.network_type,
            explorer_url=config.wallet_config.explorer_url
        )
        
        # Configure wallet
        self._configure_wallet()
        
    def _configure_wallet(self):
        """Configure wallet based on available credentials"""
        try:
            if self.config.wallet_config.wallet_mnemonic:
                self.logger.info("Configuring wallet with mnemonic...")
                self.builder.wallet_manager.configure_mnemonic(
                    mnemonic=self.config.wallet_config.wallet_mnemonic,
                    password=self.config.wallet_config.mnemonic_password
                )
            elif (self.config.wallet_config.node_api_key and 
                  self.config.wallet_config.node_wallet_address):
                self.logger.info("Configuring wallet with node...")
                # Reinitialize builder with API key
                self.builder = MultiOutputBuilder(
                    node_url=self.config.wallet_config.node_url,
                    network_type=self.config.wallet_config.network_type,
                    explorer_url=self.config.wallet_config.explorer_url,
                    node_api_key=self.config.wallet_config.node_api_key
                )
                self.builder.wallet_manager.configure_node_address(
                    self.config.wallet_config.node_wallet_address
                )
            else:
                raise ValueError("No valid wallet configuration provided")
                
            # Get active wallet address
            _, self.wallet_address = self.builder.wallet_manager.get_signing_config()
            self.logger.info(f"Wallet configured with address: {self.wallet_address}")
            
        except Exception as e:
            self.logger.error(f"Failed to configure wallet: {str(e)}")
            raise

    def _get_token_data(self, token_name: str) -> Tuple[Optional[str], int]:
        """Get token ID and decimals"""
        if token_name.upper() in ['ERG', 'ERGO']:
            return None, 9
            
        df = pd.read_csv('https://raw.githubusercontent.com/marctheshark3/Mining-Reward-Tokens/main/supported-tokens.csv')
        token_row = df[df['Token Name'] == token_name]
        if token_row.empty:
            raise ValueError(f"Token {token_name} not found in supported tokens list.")
        
        return token_row['Token ID'].values[0], int(token_row['Token decimals'].values[0])

    def _prepare_amounts(self, total_amount: Optional[float], 
                        amount_per_recipient: Optional[float],
                        recipient_count: int, decimals: int) -> List[int]:
        """Calculate distribution amounts"""
        if amount_per_recipient is not None:
            amount_in_smallest = int(amount_per_recipient * (10 ** decimals))
            return [amount_in_smallest] * recipient_count
        else:
            total_in_smallest = int(total_amount * (10 ** decimals))
            base_amount = total_in_smallest // recipient_count
            remainder = total_in_smallest % recipient_count
            
            amounts = [base_amount] * recipient_count
            for i in range(remainder):
                amounts[i] += 1
                
            return amounts

    def prepare_outputs(self, recipients: List[AirdropRecipient], 
                       token_configs: List[TokenConfig]) -> List[OutputBox]:
        """Prepare output boxes for transaction with support for variable amounts"""
        outputs = {}  # Use dictionary to prevent duplicate addresses
        self.logger.debug(f"Starting prepare_outputs with {len(recipients)} recipients")
        
        def add_or_update_output(address: str, erg_value: float, tokens: List[Dict] = None) -> None:
            """Helper to add or update output box"""
            self.logger.debug(f"Processing output for address {address}")
            self.logger.debug(f"  ERG value: {erg_value}")
            if tokens:
                self.logger.debug(f"  Tokens: {tokens}")
            
            if address in outputs:
                self.logger.debug(f"  Updating existing output for {address}")
                outputs[address].erg_value += erg_value
                if tokens:
                    if outputs[address].tokens is None:
                        outputs[address].tokens = []
                    outputs[address].tokens.extend(tokens)
            else:
                self.logger.debug(f"  Creating new output for {address}")
                outputs[address] = OutputBox(
                    address=address,
                    erg_value=erg_value,
                    tokens=tokens
                )
    
        # First pass: Handle variable distribution
        for token in token_configs:
            if token.recipients is not None:
                self.logger.debug(f"Processing variable distribution for {token.token_name}")
                token_id, decimals = self._get_token_data(token.token_name)
                
                for recipient_amount in token.recipients:
                    address = recipient_amount.address
                    amount = recipient_amount.amount
                    
                    self.logger.debug(f"Variable distribution: {token.token_name} -> {address}: {amount}")
                    
                    # Handle ERG or token amount
                    if token_id is None:  # ERG
                        # Add both minimum box value AND the distributed ERG amount
                        total_erg = (MIN_BOX_VALUE/ERG_TO_NANOERG) + amount
                        add_or_update_output(
                            address=address,
                            erg_value=total_erg
                        )
                    else:
                        # Convert token amount to smallest unit
                        amount_in_smallest = int(amount * (10 ** decimals))
                        add_or_update_output(
                            address=address,
                            erg_value=MIN_BOX_VALUE/ERG_TO_NANOERG,
                            tokens=[{
                                'tokenId': token_id,
                                'amount': amount_in_smallest
                            }]
                        )
    
        # Second pass: Handle standard distribution
        standard_tokens = [t for t in token_configs if t.recipients is None]
        if standard_tokens:
            self.logger.debug(f"Processing standard distribution for {len(standard_tokens)} tokens")
            for recipient in recipients:
                address = recipient.address
                if address not in outputs:  # Only process if not already included
                    self.logger.debug(f"Standard distribution for new address: {address}")
                    tokens = []
                    erg_value = MIN_BOX_VALUE/ERG_TO_NANOERG
                    
                    for token in standard_tokens:
                        self.logger.debug(f"Processing standard token: {token.token_name}")
                        token_id, decimals = self._get_token_data(token.token_name)
                        amounts = self._prepare_amounts(
                            token.total_amount,
                            token.amount_per_recipient,
                            len(recipients),
                            decimals
                        )
                        
                        if token_id is None:  # ERG
                            erg_value += amounts[0]/ERG_TO_NANOERG
                        else:
                            tokens.append({
                                'tokenId': token_id,
                                'amount': amounts[0]
                            })
                    
                    add_or_update_output(
                        address=address,
                        erg_value=erg_value,
                        tokens=tokens if tokens else None
                    )
        
        # Log final summary
        final_outputs = list(outputs.values())
        total_erg = sum(out.erg_value for out in final_outputs)
        self.logger.debug(f"Final output summary:")
        self.logger.debug(f"  Total outputs: {len(final_outputs)}")
        self.logger.debug(f"  Total ERG needed: {total_erg}")
        for out in final_outputs:
            self.logger.debug(f"  Output: {out.address} -> ERG: {out.erg_value}, Tokens: {out.tokens}")
        
        return final_outputs
    
    def get_recipients(self) -> List[AirdropRecipient]:
        """Get recipients based on configuration, including those with specific amounts"""
        recipients = []
        
        # Collect all addresses from token configs with specific recipients
        for token in self.config.tokens:
            if token.recipients is not None:
                for recipient in token.recipients:
                    if not any(r.address == recipient.address for r in recipients):
                        recipients.append(AirdropRecipient(
                            address=recipient.address,
                            amount=recipient.amount
                        ))
        
        # If we have any standard distribution tokens, add their recipients
        if any(token.recipients is None for token in self.config.tokens):
            if self.config.recipients_file:
                recipients.extend(RecipientManager.from_csv(self.config.recipients_file))
            elif self.config.recipient_addresses:
                recipients.extend(RecipientManager.from_list(self.config.recipient_addresses))
            else:
                recipients.extend(RecipientManager.from_miners(self.config.min_hashrate))
        
        return recipients

    def validate_balances(self, outputs: List[OutputBox]) -> None:
        """Validate wallet has sufficient balances with detailed logging"""
        try:
            boxes = self.builder.ergo.getUnspentBoxes(self.wallet_address)
            if not boxes:
                raise ValueError("No unspent boxes found")
            
            # Calculate available balances
            erg_balance = sum(box.getValue() for box in boxes) / ERG_TO_NANOERG
            token_balances = {}
            
            self.logger.debug(f"Found {len(boxes)} unspent boxes")
            self.logger.debug(f"Total ERG balance: {erg_balance}")
            
            # Debug log each box
            for box in boxes:
                box_erg = box.getValue() / ERG_TO_NANOERG
                self.logger.debug(f"Box ERG: {box_erg}")
                if box.getTokens():
                    for token in box.getTokens():
                        token_id = token.getId().toString()
                        amount = token.getValue()
                        token_balances[token_id] = token_balances.get(token_id, 0) + amount
                        self.logger.debug(f"  Token {token_id}: {amount}")
    
            # Calculate and log required amounts
            tx_fee = FEE / ERG_TO_NANOERG
            protocol_fee = PROTOCOL_FEE / ERG_TO_NANOERG
            min_box_total = len(outputs) * (MIN_BOX_VALUE / ERG_TO_NANOERG)
            output_erg = sum(out.erg_value for out in outputs)
            
            self.logger.debug("Required ERG breakdown:")
            self.logger.debug(f"  Transaction fee: {tx_fee}")
            self.logger.debug(f"  Protocol fee: {protocol_fee}")
            self.logger.debug(f"  Minimum box total: {min_box_total}")
            self.logger.debug(f"  Output ERG: {output_erg}")
            
            total_required_erg = output_erg + tx_fee + protocol_fee
            self.logger.debug(f"Total required ERG: {total_required_erg}")
            
            # Calculate required tokens
            required_tokens = {}
            for out in outputs:
                if out.tokens:
                    for token in out.tokens:
                        token_id = token['tokenId']
                        amount = token['amount']
                        required_tokens[token_id] = required_tokens.get(token_id, 0) + amount
                        self.logger.debug(f"Required token {token_id}: {amount}")
            
            # Validate ERG balance
            if erg_balance < total_required_erg:
                self.logger.error(f"ERG Requirements:")
                self.logger.error(f"  Available: {erg_balance}")
                self.logger.error(f"  Required: {total_required_erg}")
                self.logger.error(f"  Deficit: {total_required_erg - erg_balance}")
                raise ValueError(
                    f"Insufficient ERG balance. Required: {total_required_erg:.4f}, "
                    f"Available: {erg_balance:.4f}"
                )
            
            # Validate token balances
            for token_id, required_amount in required_tokens.items():
                available = token_balances.get(token_id, 0)
                if available < required_amount:
                    raise ValueError(
                        f"Insufficient token balance for {token_id}. "
                        f"Required: {required_amount}, Available: {available}"
                    )
    
        except Exception as e:
            self.logger.error(f"Balance validation failed: {str(e)}")
            raise

    def execute(self) -> TransactionResult:
        """Execute airdrop transaction"""
        try:
            if self.ui:
                self.ui.display_welcome()
                self.ui.display_assumptions()
            
            # Get recipients
            recipients = self.get_recipients()
            self.logger.info(f"Processing airdrop for {len(recipients)} recipients")
            
            # Prepare outputs
            outputs = self.prepare_outputs(recipients, self.config.tokens)
            
            # Validate balances
            self.validate_balances(outputs)
            
            if self.config.debug:
                self.logger.info("Debug mode - no transaction will be created")
                return TransactionResult(
                    status="debug",
                    recipients_count=len(recipients),
                    distributions=[
                        {
                            "token_name": token.token_name,
                            "total_amount": token.get_total_amount()
                        }
                        for token in self.config.tokens
                    ]
                )
            
            # Get user confirmation if UI is available and not in headless mode
            if self.ui and not self.config.headless:
                if not self.ui.display_confirmation_prompt():
                    return TransactionResult(status="cancelled")
            
            # Execute transaction
            self.logger.info("Creating transaction...")
            tx_id = self.builder.create_multi_output_tx(outputs, self.wallet_address)
            
            # Generate explorer URL
            explorer_base = self.config.wallet_config.explorer_url.rstrip('/')
            explorer_base = explorer_base.replace('/api/v1', '')
            explorer_url = f"{explorer_base}/transactions/{tx_id}"
            
            if self.ui:
                self.ui.display_success(tx_id, explorer_url)
            
            # Calculate distributions for result
            distributions = []
            for token in self.config.tokens:
                if token.recipients is not None:
                    # For variable distribution, sum up individual amounts
                    total = sum(r.amount for r in token.recipients)
                else:
                    # For fixed distribution, calculate based on available fields
                    total = token.get_total_amount()
                
                distributions.append({
                    "token_name": token.token_name,
                    "total_amount": total
                })
            
            return TransactionResult(
                status="completed",
                tx_id=tx_id,
                explorer_url=explorer_url,
                recipients_count=len(recipients),
                distributions=distributions
            )
            
        except Exception as e:
            self.logger.error(f"Airdrop execution failed: {str(e)}")
            if self.ui:
                self.ui.display_error(str(e))
            return TransactionResult(
                status="failed",
                error=str(e)
            )