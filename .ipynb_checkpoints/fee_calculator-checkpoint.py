# fee_calculator.py
import math
from config import Config

ERG_TO_NANOERG = 1e9
BASE_FEE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG per transaction
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG minimum per box

def calculate_distribution_fees(config: Config, current_height: int, end_height: int) -> dict:
    """
    Calculate all fees needed for distribution operations
    Returns a dictionary with detailed fee breakdown
    """
    # Calculate number of blocks for distribution period
    total_blocks = end_height - current_height
    
    # Calculate number of transactions needed
    transactions = total_blocks // config.distribution.defaultBlocksBetweenDispense  # Fixed naming
    recipients_count = len(config.recipient_wallets)
    
    # Calculate fees
    tx_fees = transactions * BASE_FEE  # 0.001 ERG per transaction
    min_box_values = transactions * recipients_count * MIN_BOX_VALUE  # 0.001 ERG per recipient box
    
    # Add 10% buffer for safety
    base_total = tx_fees + min_box_values
    buffer = base_total * 0.1
    
    total_ergs = (base_total + buffer) / ERG_TO_NANOERG
    
    return {
        "tx_fees": tx_fees,
        "min_box_values": min_box_values,
        "base_total": base_total,
        "buffer": buffer,
        "total_with_buffer": base_total + buffer,
        "total_ergs": total_ergs,
        "details": {
            "number_of_transactions": transactions,
            "recipients_per_tx": recipients_count,
            "blocks_between_tx": config.distribution.defaultBlocksBetweenDispense,
            "erg_per_tx": BASE_FEE / ERG_TO_NANOERG,
            "erg_per_box": MIN_BOX_VALUE / ERG_TO_NANOERG
        }
    }

def calculate_total_fees(config: Config, end_height: int) -> int:
    """Calculate total fees needed for all distributions until end height"""
    current_height = end_height - (180)  # 6 hours worth of blocks
    fee_details = calculate_distribution_fees(config, current_height, end_height)
    
    # Log detailed breakdown
    details = fee_details["details"]
    print(f"""
Fee Calculation Details:
-----------------------
Number of transactions: {details['number_of_transactions']}
Recipients per transaction: {details['recipients_per_tx']}
Blocks between transactions: {details['blocks_between_tx']}
ERG per transaction: {details['erg_per_tx']}
ERG per recipient box: {details['erg_per_box']}
Total ERG needed: {fee_details['total_ergs']:.4f}
""")
    
    return int(fee_details["total_with_buffer"])