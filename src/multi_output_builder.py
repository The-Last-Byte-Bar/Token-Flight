from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, OutBox
import logging
from typing import List, Dict, Union, Optional, Tuple
from dataclasses import dataclass
import json
from decimal import Decimal
import requests
from src.wallet_manager import WalletManager
from src.transaction_signer import TransactionSigner

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value
FEE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG fee per transaction (not per recipient)


# Protocol fee configuration
PROTOCOL_FEE = int(0 * ERG_TO_NANOERG)  # 0 ERG
PROTOCOL_FEE_ADDRESS = "9gPohoQooaGWbZbgTb1JrrqFWiTpM2zBknEwiyDANwmAtAne1Y8"  # Replace with actual protocol fee address

@dataclass
class OutputBox:
    address: str
    erg_value: float
    tokens: Optional[List[Dict[str, Union[str, float]]]] = None

@dataclass
class BoxSelection:
    boxes: List[any]  # ErgoBox objects
    erg_total: int
    token_totals: Dict[str, int]

class WalletLockedException(Exception):
    """Exception raised when wallet is locked."""
    pass

class MultiOutputBuilder:
    def __init__(self, node_url: str = "http://213.239.193.208:9053/", 
                 network_type: str = "mainnet",
                 explorer_url: str = "https://api.ergoplatform.com/api/v1",
                 node_api_key: Optional[str] = None,
                 node_wallet_address: Optional[str] = None,
                 wallet_mnemonic: Optional[str] = None,
                 mnemonic_password: Optional[str] = None):
        """
        Initialize MultiOutputBuilder with wallet configuration.
        """
        self.node_url = node_url.rstrip('/')
        self.network_type = network_type
        self.explorer_url = explorer_url
        self.node_api_key = node_api_key
        self.logger = logging.getLogger(__name__)
        
        # Initialize ErgoAppKit with basic configuration
        self.ergo = ErgoAppKit(
            node_url,
            network_type,
            explorer_url,
            node_api_key if node_api_key else ""
        )
        
        # Initialize wallet manager with appropriate credentials
        self.wallet_manager = WalletManager(
            self.ergo,
            node_url=node_url,
            network_type=network_type,
            explorer_url=explorer_url
        )
        
        # Configure mnemonic if provided
        if wallet_mnemonic:
            self.wallet_manager.configure_mnemonic(wallet_mnemonic, mnemonic_password)
            self.logger.info("Configured mnemonic for signing")
            
        # Configure wallet address
        if node_wallet_address:
            self.wallet_manager.configure_wallet_address(node_wallet_address)
            self.logger.info("Configured wallet address")
            
    def check_wallet_status(self) -> bool:
        """Check if the wallet is unlocked"""
        if not self.node_api_key:
            return True  # Mnemonic-based wallets don't need unlocking
        try:
            headers = {
                'Content-Type': 'application/json',
                'api_key': self.node_api_key
            }
            response = requests.get(f"{self.node_url}/wallet/status", headers=headers)
            if response.status_code == 200:
                return response.json().get('isUnlocked', False)
            return False
        except Exception as e:
            self.logger.error(f"Failed to check wallet status: {e}")
            return False

    def create_multi_output_tx(self, outputs: List[OutputBox], sender_address: str) -> str:
        """
        Create a multi-input to multi-output transaction with optimal box selection.
        """
        try:
            # Validate that sender address matches active wallet
            self.logger.debug(f"Validating sender address: {sender_address}")
            self.wallet_manager.validate_addresses(sender_address)
            use_node, active_address = self.wallet_manager.get_signing_config()
            
            # Calculate required amounts - only add FEE once for the whole transaction
            required_erg = sum(int(out.erg_value * ERG_TO_NANOERG) for out in outputs) + FEE
            required_tokens = {}
            for out in outputs:
                if out.tokens:
                    for token in out.tokens:
                        token_id = token['tokenId']
                        amount = int(token['amount'])
                        required_tokens[token_id] = required_tokens.get(token_id, 0) + amount
            
            self.logger.debug(f"Required ERG: {required_erg/ERG_TO_NANOERG}")
            self.logger.debug(f"Transaction fee: {FEE/ERG_TO_NANOERG}")
            if required_tokens:
                self.logger.debug(f"Required tokens: {required_tokens}")
            
            # Get input boxes
            self.logger.debug(f"Getting input boxes for {active_address}")
            input_boxes = self.ergo.boxesToSpend(
                active_address,
                required_erg,
                required_tokens
            )
            
            if not input_boxes:
                raise ValueError("No input boxes found")
                
            self.logger.debug(f"Found {len(input_boxes)} input boxes")
            
            # Create output boxes
            output_boxes = []

            # Add protocol fee box
            if PROTOCOL_FEE > 0:
                protocol_fee_box = self.ergo.buildOutBox(
                    value=PROTOCOL_FEE,
                    tokens=None,
                    registers=None,
                    contract=self.ergo.contractFromAddress(PROTOCOL_FEE_ADDRESS)
                )
                output_boxes.append(protocol_fee_box)
                self.logger.debug(f"Added protocol fee box: {PROTOCOL_FEE/ERG_TO_NANOERG} ERG")
            else:
                self.logger.debug("Protocol fee is 0, skipping protocol fee box")
            
            for out in outputs:
                # Convert token list to dictionary format for buildOutBox
                token_dict = {}
                if out.tokens:
                    for token in out.tokens:
                        token_dict[token['tokenId']] = int(token['amount'])
                
                self.logger.debug(f"Building output box for {out.address} with {len(token_dict)} tokens")
                self.logger.debug(f"ERG value: {out.erg_value}")
                
                box = self.ergo.buildOutBox(
                    value=int(out.erg_value * ERG_TO_NANOERG),
                    tokens=token_dict if token_dict else None,
                    registers=None,
                    contract=self.ergo.contractFromAddress(out.address)
                )
                output_boxes.append(box)
    
            # Build unsigned transaction
            self.logger.info("Building unsigned transaction...")
            from org.ergoplatform.appkit import Address
            
            self.logger.debug(f"Creating change address from: {active_address}")
            change_address = Address.create(active_address).getErgoAddress()
            
            unsigned_tx = self.ergo.buildUnsignedTransaction(
                inputs=input_boxes,
                outputs=output_boxes,
                fee=FEE,
                sendChangeTo=change_address
            )
            
            # Sign transaction using appropriate method
            self.logger.info(f"Signing transaction using {'node' if use_node else 'mnemonic'}...")
            if use_node:
                # Check wallet status before signing
                if not self.check_wallet_status():
                    raise WalletLockedException(
                        "\nWallet appears to be locked. Please ensure:\n"
                        "1. Your node wallet is initialized\n"
                        "2. The wallet is unlocked using:\n"
                        "   curl -X POST \"http://localhost:9053/wallet/unlock\" -H \"api_key: your_api_key\" -H \"Content-Type: application/json\" -d \"{\\\"pass\\\":\\\"your_wallet_password\\\"}\"\n"
                        "3. Your node API key is correct\n"
                        "4. The node is fully synced\n"
                    )
                signed_tx = self.ergo.signTransactionWithNode(unsigned_tx)
            else:
                signed_tx = self.wallet_manager.sign_transaction(unsigned_tx)
            
            self.logger.info("Submitting transaction to network...")
            tx_id = self.ergo.sendTransaction(signed_tx)
            
            self.logger.info(f"Transaction submitted successfully: {tx_id}")
            return tx_id
    
        except Exception as e:
            self.logger.error(f"Transaction creation failed: {str(e)}", exc_info=True)
            raise
            
    def calculate_required_amounts(self, outputs: List[OutputBox]) -> Tuple[int, Dict[str, int]]:
        """Calculate total ERG and tokens needed for outputs."""
        total_erg = sum(int(out.erg_value * ERG_TO_NANOERG) for out in outputs) + FEE
        token_amounts = {}
        
        for out in outputs:
            if out.tokens:
                for token in out.tokens:
                    token_id = token['tokenId']
                    amount = int(token['amount'])
                    token_amounts[token_id] = token_amounts.get(token_id, 0) + amount
        
        return total_erg, token_amounts

    def select_boxes(self, address: str, required_erg: int, required_tokens: Dict[str, int]) -> BoxSelection:
        """Select optimal set of input boxes to cover required ERG and token amounts."""
        try:
            all_boxes = self.ergo.getUnspentBoxes(address)
            if not all_boxes:
                raise ValueError("No unspent boxes found")

            selected_boxes = []
            current_erg = 0
            current_tokens: Dict[str, int] = {}
            
            # Sort boxes by ERG value (descending) for efficiency
            sorted_boxes = sorted(all_boxes, key=lambda box: box.getValue(), reverse=True)
            
            # Track what we still need
            remaining_erg = required_erg
            remaining_tokens = required_tokens.copy()

            # First pass: select boxes that contain required tokens
            for box in sorted_boxes[:]:
                if not remaining_tokens:  # If we have all tokens, stop
                    break
                    
                box_tokens = {token.getId().toString(): token.getValue() 
                            for token in box.getTokens()}
                
                selected = False
                for token_id, needed_amount in list(remaining_tokens.items()):
                    if token_id in box_tokens:
                        selected = True
                        current_tokens[token_id] = current_tokens.get(token_id, 0) + box_tokens[token_id]
                        if current_tokens[token_id] >= needed_amount:
                            del remaining_tokens[token_id]
                
                if selected:
                    current_erg += box.getValue()
                    selected_boxes.append(box)
                    sorted_boxes.remove(box)
                    remaining_erg = max(0, required_erg - current_erg)

            # Second pass: select additional boxes if we need more ERG
            for box in sorted_boxes:
                if current_erg >= required_erg:
                    break
                
                current_erg += box.getValue()
                selected_boxes.append(box)
                
                # Add any tokens from these boxes to our totals
                for token in box.getTokens():
                    token_id = token.getId().toString()
                    current_tokens[token_id] = current_tokens.get(token_id, 0) + token.getValue()

            # Validate selection
            if current_erg < required_erg:
                raise ValueError(f"Insufficient ERG. Required: {required_erg/ERG_TO_NANOERG:.4f}, "
                               f"Selected: {current_erg/ERG_TO_NANOERG:.4f}")
            
            for token_id, amount in required_tokens.items():
                if current_tokens.get(token_id, 0) < amount:
                    raise ValueError(f"Insufficient tokens. TokenId: {token_id}, "
                                   f"Required: {amount}, Selected: {current_tokens.get(token_id, 0)}")

            return BoxSelection(
                boxes=selected_boxes,
                erg_total=current_erg,
                token_totals=current_tokens
            )

        except Exception as e:
            self.logger.error(f"Box selection failed: {e}")
            raise

    def get_wallet_balances(self, address: str) -> Tuple[float, Dict[str, float]]:
        """Get ERG and token balances for a wallet address."""
        try:
            boxes = self.ergo.getUnspentBoxes(address)
            total_erg = sum(box.getValue() for box in boxes) / ERG_TO_NANOERG
            
            token_balances = {}
            for box in boxes:
                for token in box.getTokens():
                    token_id = token.getId().toString()
                    amount = token.getValue()
                    token_balances[token_id] = token_balances.get(token_id, 0) + amount
            
            return total_erg, token_balances
            
        except Exception as e:
            self.logger.error(f"Failed to get wallet balances: {e}")
            raise

    def estimate_transaction_cost(self, output_count: int) -> float:
        """Calculate minimum ERG needed for transaction."""
        return (output_count * (MIN_BOX_VALUE/ERG_TO_NANOERG)) + (FEE/ERG_TO_NANOERG)