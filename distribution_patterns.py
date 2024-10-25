# distribution_patterns.py
import math
from typing import Callable, Dict
from dataclasses import dataclass

@dataclass
class DistributionParams:
    start_height: int
    end_height: int
    total_tokens: int
    tokens_per_round: int
    recipients_count: int

def calculate_progress(current_height: int, start_height: int, end_height: int) -> float:
    """Calculate progress as a value between 0 and 1"""
    if current_height <= start_height:
        return 0.0
    if current_height >= end_height:
        return 1.0
    return (current_height - start_height) / (end_height - start_height)

def linear_distribution(progress: float) -> float:
    """Linear distribution pattern"""
    return progress

def quadratic_distribution(progress: float) -> float:
    """Quadratic (accelerating) distribution pattern"""
    return progress ** 2

def inverse_quadratic_distribution(progress: float) -> float:
    """Inverse quadratic (decelerating) distribution pattern"""
    return 1 - (1 - progress) ** 2

def sine_distribution(progress: float) -> float:
    """Sinusoidal distribution pattern"""
    return (math.sin(progress * math.pi - math.pi/2) + 1) / 2

def gaussian_distribution(progress: float) -> float:
    """Gaussian (bell curve) distribution pattern"""
    # Center the peak at progress = 0.5
    x = (progress - 0.5) * 6  # Scale to make the curve fit in [0,1]
    return math.exp(-(x**2) / 2)

def logarithmic_distribution(progress: float) -> float:
    """Logarithmic distribution pattern"""
    if progress <= 0:
        return 0
    return math.log(1 + 9 * progress) / math.log(10)  # log base 10 of (1 + 9x)

# Map of distribution types to their functions
DISTRIBUTION_PATTERNS: Dict[str, Callable[[float], float]] = {
    'linear': linear_distribution,
    'quadratic': quadratic_distribution,
    'inverse_quadratic': inverse_quadratic_distribution,
    'sine': sine_distribution,
    'gaussian': gaussian_distribution,
    'logarithmic': logarithmic_distribution
}

class DistributionCalculator:
    def __init__(self, params: DistributionParams, distribution_type: str):
        if distribution_type not in DISTRIBUTION_PATTERNS:
            raise ValueError(f"Unsupported distribution type: {distribution_type}")
        
        self.params = params
        self.distribution_func = DISTRIBUTION_PATTERNS[distribution_type]
        self.total_blocks = params.end_height - params.start_height
        
    def calculate_tokens_for_height(self, current_height: int) -> int:
        """Calculate tokens to distribute at current height"""
        progress = calculate_progress(
            current_height, 
            self.params.start_height, 
            self.params.end_height
        )
        
        # Get the distribution value for current progress
        distribution_value = self.distribution_func(progress)
        
        # Calculate tokens for this round
        tokens_this_round = int(self.params.tokens_per_round * distribution_value)
        
        # Ensure even distribution among recipients
        tokens_per_recipient = tokens_this_round // self.params.recipients_count
        return tokens_per_recipient * self.params.recipients_count
    
    def estimate_total_distribution(self, sample_points: int = 1000) -> float:
        """
        Estimate total tokens that will be distributed over the entire period
        Used for validation and adjustment
        """
        total = 0
        for i in range(sample_points):
            progress = i / (sample_points - 1)
            height = self.params.start_height + int(progress * self.total_blocks)
            total += self.calculate_tokens_for_height(height)
        
        # Average and scale to total blocks
        avg_per_point = total / sample_points
        return avg_per_point * self.total_blocks
    
    def adjust_tokens_per_round(self) -> int:
        """
        Adjust tokens_per_round to ensure total distribution matches target
        """
        estimated_total = self.estimate_total_distribution()
        adjustment_factor = self.params.total_tokens / estimated_total
        return int(self.params.tokens_per_round * adjustment_factor)