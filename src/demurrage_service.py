import time
import logging
from typing import List, Dict, Optional, Tuple
import requests
from dataclasses import dataclass
from .demurrage_distribution import BlockHeightCollector
from .base_airdrop import BaseAirdrop
from .models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from .config import AppConfig
import os
from decimal import Decimal, ROUND_DOWN

# Define ERG to nanoERG conversion constant
ERG_TO_NANOERG = int(1e9)

# Remove hardcoded constants - moved to ServiceSpecificConfig
# MIN_BOX_VALUE = int(os.getenv('MIN_BOX_VALUE', 0.001 * ERG_TO_NANOERG))
# TX_FEE = int(os.getenv('TX_FEE', 0.001 * ERG_TO_NANOERG))
# WALLET_BUFFER = int(os.getenv('WALLET_BUFFER', 0.001 * ERG_TO_NANOERG))

# Default pool fee settings moved to ServiceSpecificConfig in config.py
# DEFAULT_POOL_FEE_PERCENTAGE = '0.01'
# DEFAULT_POOL_FEE_ADDRESS = "9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt"

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class DemurrageService:
    # Modify constructor to accept config instead of just debug flag
    def __init__(self, config: AppConfig):
        # Store the whole config object
        self.config = config
        self.api_url = config.apis.ergo_api_base
        self.logger = logging.getLogger(__name__)
        self.debug = config.debug or config.dry_run # Either debug or dry_run flags will trigger simulation
        
        # Create a models.WalletConfig from our AppConfig
        self.wallet_config = WalletConfig(
            node_url=config.node.url,
            network_type=config.node.network_type,
            explorer_url=config.node.explorer_url,
            wallet_mnemonic=config.wallet.mnemonic,
            mnemonic_password=config.wallet.mnemonic_password,
            node_wallet_address=config.wallet.address
        )
        
        # Initialize collector with the config object
        self.collector = BlockHeightCollector(config=config)

    def get_wallet_balance(self) -> Decimal:
        """Returns the confirmed wallet balance as a Decimal in ERG."""
        try:
            self.logger.debug(f"Fetching balance for {self.wallet_config.node_wallet_address}")
            response = requests.get(
                f"{self.api_url}/addresses/{self.wallet_config.node_wallet_address}/balance/confirmed"
            )
            response.raise_for_status()
            nano_ergs = response.json().get('nanoErgs', 0)
            # Return as Decimal for precision
            return (Decimal(nano_ergs) / Decimal(ERG_TO_NANOERG)).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting wallet balance from API: {e}")
            return Decimal(0) # Return Decimal zero on error
        except Exception as e:
            self.logger.error(f"Unexpected error getting wallet balance: {e}", exc_info=True)
            return Decimal(0)

    def calculate_transaction_costs(self, recipient_count: int) -> Tuple[Decimal, Decimal]:
        """Calculate transaction costs (as Decimal in ERG).
        
        Returns:
            Tuple[Decimal, Decimal]: (total_costs_erg, min_box_total_erg)
        """
        if recipient_count < 0:
             raise ValueError("Recipient count cannot be negative")
             
        # Get values from config
        min_box_value = self.config.service.min_box_value_nanoerg
        tx_fee = self.config.service.tx_fee_nanoerg
        wallet_buffer = self.config.service.wallet_buffer_nanoerg
             
        # Calculate minimum box values needed for all recipients in nanoERG
        min_box_total_nano = Decimal(min_box_value) * Decimal(recipient_count)
        
        # Total costs in nanoERG include:
        # 1. Minimum box values for all recipients
        # 2. Transaction fee
        # 3. Wallet buffer for future transactions
        # 4. Change box minimum value (assuming one is always needed)
        total_costs_nano = min_box_total_nano + Decimal(tx_fee) + Decimal(wallet_buffer) + Decimal(min_box_value)
        
        # Convert to ERG (Decimal)
        total_costs_erg = (total_costs_nano / Decimal(ERG_TO_NANOERG)).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
        min_box_total_erg = (min_box_total_nano / Decimal(ERG_TO_NANOERG)).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
        
        return total_costs_erg, min_box_total_erg

    def calculate_distribution_amount(self, recipient_count: int) -> Decimal:
        """Calculates the amount available for distribution (as Decimal in ERG)."""
        wallet_balance_erg = self.get_wallet_balance()
        self.logger.info(f"Current wallet balance: {wallet_balance_erg:.8f} ERG")
        
        if recipient_count <= 0:
             self.logger.warning("Recipient count is zero or negative. Cannot calculate distribution amount.")
             return Decimal(0)
             
        total_costs_erg, min_box_total_erg = self.calculate_transaction_costs(recipient_count)
        
        # Get values from config for logging
        min_box_value = self.config.service.min_box_value_nanoerg
        tx_fee = self.config.service.tx_fee_nanoerg
        wallet_buffer = self.config.service.wallet_buffer_nanoerg
        
        self.logger.info(f"Transaction costs breakdown:")
        self.logger.info(f"- Minimum box value per recipient: {Decimal(min_box_value)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Total minimum box values ({recipient_count} recipients): {min_box_total_erg:.8f} ERG")
        self.logger.info(f"- Transaction fee: {Decimal(tx_fee)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Wallet buffer: {Decimal(wallet_buffer)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Change box min value: {Decimal(min_box_value)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Total estimated costs: {total_costs_erg:.8f} ERG")
        
        # This is the amount available for actual distribution (excluding min box values)
        # It's the total balance minus all fees/buffers.
        available_for_distribution = (wallet_balance_erg - total_costs_erg).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
        
        if available_for_distribution <= 0:
            # Raise ValueError here for clarity, let caller handle
            raise ValueError(
                f"Insufficient balance for distribution after accounting for costs.\n"
                f"Required (Costs): {total_costs_erg:.8f} ERG\n"
                f"Available (Balance): {wallet_balance_erg:.8f} ERG"
            )
        
        self.logger.info(f"Calculated available amount for distribution pool (before fee split): {available_for_distribution:.8f} ERG")
        return available_for_distribution

    def execute_distribution(self, block_heights: List[int]) -> Optional[str]:
        if not block_heights:
            self.logger.info("No block heights provided for distribution. Skipping.")
            return None
            
        try:
            self.logger.info(f"Starting distribution execution for {len(block_heights)} blocks.")
            miners_data = self.collector.fetch_miners_data(block_heights)
            miners = miners_data.get('miners', [])
            miner_count = len(miners)

            if not miner_count:
                self.logger.info("No eligible miner recipients found in fetched data for these blocks.")
                # Decide if pool fee should still be paid. Requires checking balance vs pool fee cost.
                # For now, exiting if no miners found.
                # TODO: Add logic to pay only pool fee if desired and balance permits.
                return None

            self.logger.info(f"Found {miner_count} eligible miner recipients")
            
            # Pool fee configuration from config
            pool_fee_percentage_str = self.config.service.pool_fee_percentage
            pool_fee_address = self.config.service.pool_fee_address
            
            self.logger.debug(f"Pool Fee Config from settings: Percentage='{pool_fee_percentage_str}', Address='{pool_fee_address}'")
            
            try:
                 pool_fee_percentage_dec = Decimal(pool_fee_percentage_str)
                 if not (0 <= pool_fee_percentage_dec <= 1):
                      raise ValueError("Pool fee percentage must be between 0 and 1")
            except ValueError as e:
                 self.logger.error(f"Invalid pool fee percentage '{pool_fee_percentage_str}': {e}. Using default from config.", exc_info=True)
                 # Re-fetch from ServiceSpecificConfig default
                 pool_fee_percentage_dec = Decimal(self.config.service.pool_fee_percentage)
                 
            if not pool_fee_address:
                 self.logger.warning("Pool fee address not configured. Pool fee cannot be distributed.")
                 # Proceed without pool fee
                 pool_fee_percentage_dec = Decimal(0) # Set percentage to 0 if no address

            # Calculate costs and available amount considering potential pool fee recipient
            # If pool fee address is valid and percentage > 0, include them in recipient count
            has_pool_fee_recipient = pool_fee_address and pool_fee_percentage_dec > 0
            total_recipients = miner_count + (1 if has_pool_fee_recipient else 0)
            
            if total_recipients == 0:
                 self.logger.info("No miner recipients and no valid pool fee recipient. Nothing to distribute.")
                 return None
            
            try:
                 # Calculate the total pot available for distribution among miners + pool fee
                 initial_available_amount_dec = self.calculate_distribution_amount(total_recipients)
            except ValueError as e:
                 # This happens if balance isn't enough even for fees/buffer
                 self.logger.error(f"Cannot execute distribution: {e}")
                 return None

            # Calculate pool fee amount from the available pot
            pool_fee_amount_dec = (initial_available_amount_dec * pool_fee_percentage_dec).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
            # Miner amount is the remainder
            miner_distribution_amount_dec = (initial_available_amount_dec - pool_fee_amount_dec).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
            
            # Log the planned split
            self.logger.info(f"Pool Fee Split ({pool_fee_percentage_dec*100:.2f}% to {pool_fee_address[:10]}... if applicable):")
            self.logger.info(f"- Total available pot: {initial_available_amount_dec:.8f} ERG")
            self.logger.info(f"- Calculated Pool Fee amount: {pool_fee_amount_dec:.8f} ERG")
            self.logger.info(f"- Calculated Miner distribution amount: {miner_distribution_amount_dec:.8f} ERG")

            # Sanity check: Ensure amounts are not negative (should be handled by calculate_distribution_amount check)
            if miner_distribution_amount_dec < 0 or pool_fee_amount_dec < 0:
                 self.logger.error("Internal calculation error resulted in negative distribution amounts. Aborting.")
                 # This case should ideally not be reachable if checks above are correct
                 return None
                 
            # Ensure we only pass a positive pool fee amount if the address is valid
            final_pool_fee_amount = pool_fee_amount_dec if has_pool_fee_recipient else Decimal(0)
            final_pool_fee_address = pool_fee_address if has_pool_fee_recipient else ""

            self.logger.debug(f"Values passed to generate_distribution: miner_amount={miner_distribution_amount_dec:.8f}, pool_amount={final_pool_fee_amount:.8f}, pool_address='{final_pool_fee_address}'")

            # Generate distribution object using Decimal amounts
            distribution = self.collector.generate_distribution(
                miners_data, 
                miner_distribution_amount_dec, 
                "ERG", 
                final_pool_fee_amount, 
                final_pool_fee_address
            )

            self.logger.debug(f"Raw distribution dict returned: {distribution}")

            # Check if the generated distribution actually has recipients
            dist_list = distribution.get('distributions', [])
            if not dist_list or not dist_list[0].get('recipients'):
                self.logger.info("Generated distribution list is empty after calculation. Nothing to send.")
                return None

            # Convert recipients to RecipientAmount objects for the airdrop tool
            recipients_for_airdrop: List[RecipientAmount] = []
            calculated_total_erg = Decimal(0)
            for r in dist_list[0]['recipients']:
                address = r.get('address')
                amount_float = r.get('amount') # generate_distribution now returns float
                if not address or amount_float is None:
                     self.logger.warning(f"Skipping invalid recipient entry in generated distribution: {r}")
                     continue
                     
                # Log if we encounter the pool fee address during processing
                if address == pool_fee_address:
                     self.logger.debug(f"Processing pool fee recipient entry: Address={address}, Amount={amount_float}")
                     
                try:
                    # Convert float amount back to Decimal for summation and logging
                    amount_dec = Decimal(str(amount_float)).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
                    if amount_dec <= 0:
                         self.logger.warning(f"Skipping recipient {address[:10]}... with zero or negative amount: {amount_dec:.8f}")
                         continue
                         
                    recipients_for_airdrop.append(RecipientAmount(
                        address=address,
                        # Pass the float amount required by RecipientAmount/Airdrop
                        amount=amount_float 
                    ))
                    calculated_total_erg += amount_dec
                except Exception as e:
                     self.logger.error(f"Error processing recipient {r}: {e}", exc_info=True)
                     continue # Skip problematic recipient
            
            if not recipients_for_airdrop:
                 self.logger.error("No valid recipients found after processing the generated distribution list.")
                 return None
                 
            # Log distribution statistics
            min_amount = min(r.amount for r in recipients_for_airdrop)
            max_amount = max(r.amount for r in recipients_for_airdrop)
            self.logger.info(f"Final Distribution Summary:")
            self.logger.info(f"- Total recipients to send to: {len(recipients_for_airdrop)}")
            # Log the sum calculated from the final recipient list
            self.logger.info(f"- Total amount in transaction outputs: {calculated_total_erg:.8f} ERG") 
            self.logger.info(f"- Min amount per recipient: {min_amount:.8f} ERG")
            self.logger.info(f"- Max amount per recipient: {max_amount:.8f} ERG")
            # Compare sum with initial pot - should be very close
            if abs(calculated_total_erg - initial_available_amount_dec) > Decimal('0.000001'):
                 self.logger.warning(f"Final summed amount ({calculated_total_erg:.8f}) differs slightly from initial available pot ({initial_available_amount_dec:.8f}) potentially due to rounding or skipped recipients.")
            
            # Configure airdrop
            token_config = TokenConfig(
                token_name="ERG", # Assuming ERG distribution
                recipients=recipients_for_airdrop
            )
            
            airdrop_config = AirdropConfig(
                wallet_config=self.wallet_config,
                tokens=[token_config],
                headless=True,
                debug=self.debug # Pass debug flag to airdrop
            )
            
            if self.debug:
                # This is now the dry run mode (triggered by either debug or dry_run in config)
                dry_run_label = "DEBUG MODE" if self.config.debug else "DRY RUN MODE"
                self.logger.info(f"--- {dry_run_label}: SIMULATING TRANSACTION ---")
                self.logger.info(f"Would send to {len(recipients_for_airdrop)} recipients.")
                self.logger.info(f"Total ERG in outputs: {calculated_total_erg:.8f} ERG")
                # Log the calculated pool fee details explicitly during dry run
                self.logger.info(f"Calculated Pool Fee Amount: {final_pool_fee_amount:.8f} ERG")
                self.logger.info(f"Pool Fee Address: {final_pool_fee_address}")
                self.logger.info("Distribution simulation completed successfully")
                
                # Return structured distribution information for potential notification
                return {
                    "status": "dry_run",
                    "recipients_count": len(recipients_for_airdrop),
                    "total_amount": float(calculated_total_erg),
                    "distribution": distribution,
                    "message": f"Dry run completed successfully. Would send {calculated_total_erg} ERG to {len(recipients_for_airdrop)} recipients."
                }
            
            # Execute actual airdrop
            self.logger.info("Executing airdrop transaction...")
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute() # Assumes BaseAirdrop.execute() exists and returns object with status and tx_id
            
            if result and result.status == "completed" and result.tx_id:
                 self.logger.info(f"Airdrop transaction successful. TX ID: {result.tx_id}")
                 # Return structured info for notification
                 return {
                     "status": "completed",
                     "tx_id": result.tx_id,
                     "explorer_url": f"{self.config.node.explorer_url}/transactions/{result.tx_id}",
                     "recipients_count": len(recipients_for_airdrop),
                     "total_amount": float(calculated_total_erg),
                     "message": f"Sent {calculated_total_erg} ERG to {len(recipients_for_airdrop)} recipients. TX: {result.tx_id}"
                 }
            else:
                 error_msg = f"Airdrop transaction failed or did not return TX ID. Result: {result}"
                 self.logger.error(error_msg)
                 # Return structured error for notification
                 return {
                     "status": "failed",
                     "error": error_msg,
                     "message": "Transaction failed. See logs for details."
                 }
            
        except ValueError as ve:
            # Catch specific ValueErrors raised during calculations (e.g., insufficient balance)
            error_msg = f"Distribution pre-check failed: {ve}"
            self.logger.error(error_msg)
            return {
                "status": "failed",
                "error": str(ve),
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error during distribution execution: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "message": error_msg
            }