# test_distributions.py
import json
import matplotlib.pyplot as plt
from distribution_patterns import DistributionCalculator, DistributionParams
from datetime import datetime, timedelta
import numpy as np

def test_distribution_patterns(config_path: str):
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Setup parameters
    current_time = datetime.now()
    block_time = 120  # 2 minutes per block
    total_blocks = config['distribution']['maxBlockDuration']
    start_height = 0
    end_height = total_blocks
    
    # Create plot
    plt.figure(figsize=(15, 10))
    
    # Calculate time points
    time_points = [current_time + timedelta(seconds=i*block_time) for i in range(total_blocks)]
    x_axis = range(total_blocks)
    
    # Test each distribution
    for dist in config['distribution']['distributions']:
        # Initialize distribution calculator
        params = DistributionParams(
            start_height=start_height,
            end_height=end_height,
            total_tokens=dist['totalAmount'],
            tokens_per_round=config['distribution']['tokensPerRound'],
            recipients_count=len(config['parameters']['recipientWallets'])
        )
        
        calculator = DistributionCalculator(params, dist['type'])
        
        # Calculate distribution over time
        y_values = []
        cumulative_tokens = 0
        for height in x_axis:
            tokens = calculator.calculate_tokens_for_height(height)
            cumulative_tokens += tokens
            y_values.append(cumulative_tokens / dist['totalAmount'] * 100)  # Convert to percentage
        
        # Plot distribution
        plt.plot(x_axis, y_values, label=f"{dist['name']} ({dist['type']})")
    
    # Customize plot
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xlabel('Blocks (2 min each)')
    plt.ylabel('Tokens Distributed (%)')
    plt.title('Token Distribution Patterns Over 6 Hours')
    
    # Add time markers on second x-axis
    ax2 = plt.gca().twiny()
    hours = [current_time + timedelta(hours=i) for i in range(7)]
    ax2.set_xticks(np.linspace(0, total_blocks, 7))
    ax2.set_xticklabels([h.strftime('%H:%M') for h in hours])
    ax2.set_xlabel('Time')
    
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    
    # Save plot
    plt.savefig('distribution_patterns.png', bbox_inches='tight', dpi=300)
    print("Distribution visualization saved as 'distribution_patterns.png'")
    
    # Print distribution statistics
    print("\nDistribution Statistics:")
    print("=" * 50)
    for dist in config['distribution']['distributions']:
        params = DistributionParams(
            start_height=start_height,
            end_height=end_height,
            total_tokens=dist['totalAmount'],
            tokens_per_round=config['distribution']['tokensPerRound'],
            recipients_count=len(config['parameters']['recipientWallets'])
        )
        calculator = DistributionCalculator(params, dist['type'])
        
        # Calculate key statistics
        total_distributed = 0
        max_single_round = 0
        for height in x_axis:
            tokens = calculator.calculate_tokens_for_height(height)
            total_distributed += tokens
            max_single_round = max(max_single_round, tokens)
        
        print(f"\nPattern: {dist['name']} ({dist['type']})")
        print(f"Total Tokens Distributed: {total_distributed:,}")
        print(f"Max Tokens in Single Round: {max_single_round:,}")
        print(f"Average Tokens per Block: {total_distributed/total_blocks:,.2f}")

if __name__ == "__main__":
    test_distribution_patterns('testnet.json')