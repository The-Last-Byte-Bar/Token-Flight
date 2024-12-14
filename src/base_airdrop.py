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
                self.builder.ergo.apiKey = self.config.wallet_config.node_api_key
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

    def get_recipients(self) -> List[AirdropRecipient]:
        """Get recipients based on configuration"""
        if self.config.recipients_file:
            return RecipientManager.from_csv(self.config.recipients_file)
        elif self.config.recipient_addresses:
            return RecipientManager.from_list(self.config.recipient_addresses)
        else:
            return RecipientManager.from_miners(self.config.min_hashrate)

    def prepare_outputs(self, recipients: List[AirdropRecipient], 
                       token_configs: List[TokenConfig]) -> List[OutputBox]:
        """Prepare output boxes for transaction"""
        outputs = []
        for recipient in recipients:
            tokens = []
            erg_value = MIN_BOX_VALUE / ERG_TO_NANOERG
            
            for token in token_configs:
                token_id, decimals = self._get_token_data(token.token_name)
                amounts = self._prepare_amounts(
                    token.total_amount,
                    token.amount_per_recipient,
                    len(recipients),
                    decimals
                )
                
                if token_id is None:  # ERG
                    erg_value += amounts[0] / ERG_TO_NANOERG
                else:
                    tokens.append({
                        'tokenId': token_id,
                        'amount': amounts[0]
                    })
            
            outputs.append(OutputBox(
                address=recipient.address,
                erg_value=erg_value,
                tokens=tokens if tokens else None
            ))
            
        return outputs

    def validate_balances(self, outputs: List[OutputBox]) -> None:
        """Validate wallet has sufficient balances"""
        erg_balance, token_balances = self.builder.get_wallet_balances(self.wallet_address)
        
        # Calculate required amounts
        required_erg = sum(out.erg_value for out in outputs)
        required_tokens = {}
        
        for out in outputs:
            if out.tokens:
                for token in out.tokens:
                    token_id = token['tokenId']
                    amount = token['amount']
                    required_tokens[token_id] = required_tokens.get(token_id, 0) + amount
        
        # Validate ERG balance
        if erg_balance < required_erg:
            raise ValueError(
                f"Insufficient ERG balance. Required: {required_erg:.4f}, "
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
                            "total_amount": token.total_amount or 
                                          (token.amount_per_recipient * len(recipients))
                        }
                        for token in self.config.tokens
                    ]
                )
            
            # Get user confirmation if UI is available
            if self.ui and not self.ui.display_confirmation_prompt():
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
            
            return TransactionResult(
                status="completed",
                tx_id=tx_id,
                explorer_url=explorer_url,
                recipients_count=len(recipients),
                distributions=[
                    {
                        "token_name": token.token_name,
                        "total_amount": token.total_amount or 
                                      (token.amount_per_recipient * len(recipients))
                    }
                    for token in self.config.tokens
                ]
            )
            
        except Exception as e:
            self.logger.error(f"Airdrop execution failed: {str(e)}")
            if self.ui:
                self.ui.display_error(str(e))
            return TransactionResult(
                status="failed",
                error=str(e)
            )