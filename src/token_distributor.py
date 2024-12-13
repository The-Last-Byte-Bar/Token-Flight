from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from decimal import Decimal, ROUND_DOWN
import logging

@dataclass
class DistributionConfig:
    """Configuration for token distribution"""
    token_name: str
    total_amount: Optional[float] = None  # Total amount to distribute
    amount_per_recipient: Optional[float] = None  # Amount per recipient
    min_amount: float = 0.001  # Minimum amount per recipient
    decimals: int = 0  # Token decimals
    
    def validate(self) -> bool:
        """Validate distribution configuration"""
        if self.total_amount is None and self.amount_per_recipient is None:
            raise ValueError("Either total_amount or amount_per_recipient must be specified")
        if self.total_amount is not None and self.amount_per_recipient is not None:
            raise ValueError("Cannot specify both total_amount and amount_per_recipient")
        if self.total_amount is not None and self.total_amount <= 0:
            raise ValueError("Total amount must be greater than 0")
        if self.amount_per_recipient is not None and self.amount_per_recipient <= 0:
            raise ValueError("Amount per recipient must be greater than 0")
        return True

class TokenDistributor:
    """Handles token distribution calculations and validation"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def _adjust_for_decimals(self, amount: float, decimals: int) -> int:
        """Convert float amount to integer with proper decimal places"""
        decimal_amount = Decimal(str(amount))
        factor = Decimal(10) ** decimals
        return int(decimal_amount * factor)

    def _calculate_equal_distribution(self, total_amount: float, recipient_count: int, 
                                   decimals: int, min_amount: float) -> List[int]:
        """Calculate equal distribution amounts for all recipients"""
        if recipient_count <= 0:
            raise ValueError("Recipient count must be greater than 0")
            
        # Convert to Decimal for precise division
        total_decimal = Decimal(str(total_amount))
        min_decimal = Decimal(str(min_amount))
        
        # Calculate amount per recipient
        amount_per_recipient = total_decimal / Decimal(recipient_count)
        
        if amount_per_recipient < min_decimal:
            raise ValueError(
                f"Amount per recipient ({amount_per_recipient}) would be less than "
                f"minimum allowed ({min_decimal})"
            )
            
        # Convert to smallest unit considering decimals
        factor = Decimal(10) ** decimals
        base_amount = int((amount_per_recipient * factor).quantize(
            Decimal('1.'), rounding=ROUND_DOWN
        ))
        
        # Handle remaining dust
        total_base_units = self._adjust_for_decimals(total_amount, decimals)
        distributed_amount = base_amount * recipient_count
        remaining = total_base_units - distributed_amount
        
        # Distribute amounts with remaining dust to first recipients
        amounts = [base_amount] * recipient_count
        for i in range(int(remaining)):
            amounts[i] += 1
            
        return amounts

    def calculate_distribution(self, config: DistributionConfig, 
                             recipient_count: int) -> List[int]:
        """
        Calculate distribution amounts for all recipients
        
        Args:
            config: Distribution configuration
            recipient_count: Number of recipients
            
        Returns:
            List of amounts in smallest token units (adjusted for decimals)
        """
        try:
            config.validate()
            
            if config.total_amount is not None:
                # Equal distribution of total amount
                return self._calculate_equal_distribution(
                    total_amount=config.total_amount,
                    recipient_count=recipient_count,
                    decimals=config.decimals,
                    min_amount=config.min_amount
                )
            else:
                # Fixed amount per recipient
                amount = self._adjust_for_decimals(
                    config.amount_per_recipient,
                    config.decimals
                )
                return [amount] * recipient_count
                
        except Exception as e:
            self.logger.error(f"Distribution calculation failed: {str(e)}")
            raise
            
    def validate_distribution(self, amounts: List[int], total_available: int) -> bool:
        """
        Validate distribution amounts against available balance
        
        Args:
            amounts: List of distribution amounts
            total_available: Total available balance
            
        Returns:
            bool: True if distribution is valid
            
        Raises:
            ValueError: If any validation fails
        """
        if not amounts:
            raise ValueError("No distribution amounts provided")
            
        # Check for zero or negative amounts
        invalid_amounts = [(i, amt) for i, amt in enumerate(amounts) if amt <= 0]
        if invalid_amounts:
            error_msg = "\n".join(f"Recipient {i}: {amt}" for i, amt in invalid_amounts)
            raise ValueError(
                f"Found {len(invalid_amounts)} invalid amounts (must be > 0):\n{error_msg}"
            )

    def preview_distribution(self, config: DistributionConfig, 
                           recipient_count: int) -> Dict[str, Union[int, float, List[float]]]:
        """
        Generate distribution preview
        
        Args:
            config: Distribution configuration
            recipient_count: Number of recipients
            
        Returns:
            Dict containing distribution summary
        """
        amounts = self.calculate_distribution(config, recipient_count)
        
        # Convert amounts back to token units for display
        factor = 10 ** config.decimals
        token_amounts = [amount / factor for amount in amounts]
        
        unique_amounts = len(set(amounts))
        
        return {
            "recipient_count": recipient_count,
            "total_amount": sum(token_amounts),
            "min_amount": min(token_amounts),
            "max_amount": max(token_amounts),
            "unique_amounts": unique_amounts,
            "amounts": token_amounts
        }