from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, OutBox
import logging
from typing import List, Dict, Union, Optional, Tuple
from dataclasses import dataclass
import json
from decimal import Decimal
import requests

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum box value
FEE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG fee

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
                 node_api_key: str = None):
        self.node_url = node_url.rstrip('/')
        self.network_type = network_type
        self.explorer_url = explorer_url
        self.node_api_key = node_api_key
        self.logger = logging.getLogger(__name__)
        
        # Initialize ErgoAppKit
        self.ergo = ErgoAppKit(
            node_url,
            network_type,
            explorer_url,
            node_api_key
        )

    def check_wallet_status(self) -> bool:
        """Check if the wallet is unlocked"""
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
            # Calculate required amounts
            required_erg, required_tokens = self.calculate_required_amounts(outputs)
            
            # Select input boxes
            selection = self.select_boxes(sender_address, required_erg, required_tokens)
            
            # Create output boxes
            output_boxes = []
            for out in outputs:
                if out.tokens:
                    tokens = {token['tokenId']: int(token['amount']) for token in out.tokens}
                else:
                    tokens = None
                    
                box = self.ergo.buildOutBox(
                    value=int(out.erg_value * ERG_TO_NANOERG),
                    tokens=tokens,
                    registers=None,
                    contract=self.ergo.contractFromAddress(out.address)
                )
                output_boxes.append(box)

            # Build unsigned transaction
            self.logger.info("Building unsigned transaction...")
            unsigned_tx = self.ergo.buildUnsignedTransaction(
                inputs=selection.boxes,
                outputs=output_boxes,
                fee=FEE,
                sendChangeTo=Address.create(sender_address).getErgoAddress()
            )
            
            # Sign and submit transaction
            self.logger.info("Signing transaction with node wallet...")
            try:
                signed_tx = self.ergo.signTransactionWithNode(unsigned_tx)
            except Exception as e:
                error_msg = str(e)
                if ("Tree root should be real" in error_msg or 
                    "UnprovenSchnorr" in error_msg):
                    # Check wallet status
                    if not self.check_wallet_status():
                        raise WalletLockedException(
                            "\nWallet appears to be locked. Please ensure:\n"
                            "1. Your node wallet is initialized\n"
                            "2. The wallet is unlocked using:\n"
                            "   curl -X POST \"http://localhost:9053/wallet/unlock\" -H \"api_key: your_api_key\" -H \"Content-Type: application/json\" -d \"{\\\"pass\\\":\\\"your_wallet_password\\\"}\"\n"
                            "3. Your node API key is correct in the .env file\n"
                            "4. The node is fully synced\n"
                        )
                raise
            
            self.logger.info("Submitting transaction to network...")
            tx_id = self.ergo.sendTransaction(signed_tx)
            
            self.logger.info(f"Transaction submitted successfully: {tx_id}")
            return tx_id

        except WalletLockedException as e:
            self.logger.error(f"Wallet locked: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Transaction creation failed: {e}", exc_info=True)
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