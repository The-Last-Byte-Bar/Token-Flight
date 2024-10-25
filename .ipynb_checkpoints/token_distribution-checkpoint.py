# token_distribution.py
import logging
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address
from typing import List, Tuple
from distribution_patterns import DistributionCalculator, DistributionParams

logger = logging.getLogger(__name__)

class TokenDistributor:
    def __init__(self, 
                 appKit: ErgoAppKit,
                 distribution_info: dict,
                 node_address: str):
        self.appKit = appKit
        self.node_address = node_address
        
        # Initialize distribution calculator
        params = DistributionParams(
            start_height=distribution_info['unlock_height'],
            end_height=distribution_info['end_height'],
            total_tokens=distribution_info['total_tokens'],
            tokens_per_round=distribution_info['tokens_per_round'],
            recipients_count=len(distribution_info['recipient_wallets'])
        )
        
        self.calculator = DistributionCalculator(
            params,
            distribution_info['distribution_type']
        )
        
        # Store other necessary info
        self.token_id = distribution_info['token_id']
        self.recipient_wallets = distribution_info['recipient_wallets']
        self.proxy_address = distribution_info['proxy_contract_address']
        self.blocks_between_dispense = distribution_info['blocks_between_dispense']
    
    async def check_distribution_needed(self, current_height: int) -> Tuple[bool, int]:
        """Check if distribution is needed and calculate tokens for this round"""
        if current_height >= self.calculator.params.end_height:
            logger.info("Distribution period has ended")
            return False, 0
            
        if current_height < self.calculator.params.start_height:
            logger.info("Distribution period hasn't started yet")
            return False, 0
            
        if current_height % self.blocks_between_dispense != 0:
            return False, 0
            
        tokens_this_round = self.calculator.calculate_tokens_for_height(current_height)
        if tokens_this_round <= 0:
            return False, 0
            
        return True, tokens_this_round
    
    def build_distribution_tx(self, 
                            tokens_to_distribute: int,
                            proxy_box,
                            current_height: int) -> dict:
        """Build transaction for token distribution"""
        tokens_per_recipient = tokens_to_distribute // len(self.recipient_wallets)
        
        # Prepare outputs for each recipient
        outputs = []
        for recipient in self.recipient_wallets:
            output_box = self.appKit.buildOutBox(
                value=MIN_BOX_VALUE,
                tokens={self.token_id: tokens_per_recipient},
                registers={},
                contract=self.appKit.contractFromAddress(recipient)
            )
            outputs.append(output_box)
        
        # Build the transaction
        unsigned_tx = self.appKit.buildUnsignedTransaction(
            inputs=[proxy_box],
            outputs=outputs,
            fee=FEE,
            sendChangeTo=Address.create(self.proxy_address).getErgoAddress()
        )
        
        return unsigned_tx
    
    def get_distribution_progress(self, current_height: int) -> dict:
        """Get current distribution progress information"""
        progress = (current_height - self.calculator.params.start_height) / \
                  (self.calculator.params.end_height - self.calculator.params.start_height)
        
        return {
            "progress_percentage": min(100, max(0, progress * 100)),
            "current_height": current_height,
            "blocks_remaining": max(0, self.calculator.params.end_height - current_height),
            "distribution_type": self.calculator.params.distribution_type,
            "tokens_next_round": self.calculator.calculate_tokens_for_height(current_height)
        }