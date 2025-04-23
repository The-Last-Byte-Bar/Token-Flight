import time
import logging
from typing import List, Dict, Optional, Tuple
import requests
from dataclasses import dataclass
from .demurrage_distribution import BlockHeightCollector
from .base_airdrop import BaseAirdrop
from .models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
import os
from decimal import Decimal, ROUND_DOWN

# Define constants sourcing from environment variables with defaults
ERG_TO_NANOERG = int(1e9)
# Use os.getenv to fetch these, matching demurrage_distribution.py
MIN_BOX_VALUE = int(os.getenv('MIN_BOX_VALUE', 0.001 * ERG_TO_NANOERG))
TX_FEE = int(os.getenv('TX_FEE', 0.001 * ERG_TO_NANOERG))
WALLET_BUFFER = int(os.getenv('WALLET_BUFFER', 0.001 * ERG_TO_NANOERG))

# Use the defaults defined in demurrage_distribution for consistency
DEFAULT_POOL_FEE_PERCENTAGE = '0.01'
DEFAULT_POOL_FEE_ADDRESS = "9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt"

@dataclass
class Block:
    height: int
    confirmation_progress: float
    created: str

class DemurrageService:
    def __init__(self, debug: bool = False):
        # Use environment variable for API base with a default
        self.api_url = os.getenv('ERGO_API_BASE', "https://api.ergoplatform.com/api/v1")
        self.logger = logging.getLogger(__name__)
        self.debug = debug
        
        # Configure wallet with mnemonic
        node_url = os.getenv('NODE_URL')
        network_type = os.getenv('NETWORK_TYPE')
        explorer_url = os.getenv('EXPLORER_URL')
        wallet_mnemonic = os.getenv('WALLET_MNEMONIC')
        wallet_address = os.getenv('WALLET_ADDRESS')
        
        # Validate required env vars
        if not node_url: raise ValueError("NODE_URL environment variable is required")
        if not network_type: raise ValueError("NETWORK_TYPE environment variable is required")
        if not explorer_url: raise ValueError("EXPLORER_URL environment variable is required")
        if not wallet_mnemonic: raise ValueError("WALLET_MNEMONIC environment variable is required")
        if not wallet_address: raise ValueError("WALLET_ADDRESS environment variable is required")
        
        self.wallet_config = WalletConfig(
            node_url=node_url,
            network_type=network_type,
            explorer_url=explorer_url,
            wallet_mnemonic=wallet_mnemonic,
            mnemonic_password=os.getenv('MNEMONIC_PASSWORD', ''),
            node_wallet_address=wallet_address
        )
        
        # Initialize collector with wallet address from the config
        # Removed the hardcoded address '9fE...'
        self.collector = BlockHeightCollector(wallet_address=self.wallet_config.node_wallet_address)
        # The check below is now redundant as BlockHeightCollector raises ValueError if no address is found
        # if not self.collector.wallet_address:
        #     raise ValueError("WALLET_ADDRESS environment variable is required")

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
             
        # Calculate minimum box values needed for all recipients in nanoERG
        min_box_total_nano = Decimal(MIN_BOX_VALUE) * Decimal(recipient_count)
        
        # Total costs in nanoERG include:
        # 1. Minimum box values for all recipients
        # 2. Transaction fee
        # 3. Wallet buffer for future transactions
        # 4. Change box minimum value (assuming one is always needed)
        total_costs_nano = min_box_total_nano + Decimal(TX_FEE) + Decimal(WALLET_BUFFER) + Decimal(MIN_BOX_VALUE)
        
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
        self.logger.info(f"Transaction costs breakdown:")
        self.logger.info(f"- Minimum box value per recipient: {Decimal(MIN_BOX_VALUE)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Total minimum box values ({recipient_count} recipients): {min_box_total_erg:.8f} ERG")
        self.logger.info(f"- Transaction fee: {Decimal(TX_FEE)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Wallet buffer: {Decimal(WALLET_BUFFER)/Decimal(ERG_TO_NANOERG):.8f} ERG")
        self.logger.info(f"- Change box min value: {Decimal(MIN_BOX_VALUE)/Decimal(ERG_TO_NANOERG):.8f} ERG")
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
            
            # Pool fee configuration from environment variables
            pool_fee_percentage_str = os.getenv('POOL_FEE_PERCENTAGE', DEFAULT_POOL_FEE_PERCENTAGE)
            pool_fee_address = os.getenv('POOL_FEE_ADDRESS', DEFAULT_POOL_FEE_ADDRESS)
            
            self.logger.debug(f"Pool Fee Config: Percentage Env='{pool_fee_percentage_str}', Address Env='{pool_fee_address}'")
            
            try:
                 pool_fee_percentage_dec = Decimal(pool_fee_percentage_str)
                 if not (0 <= pool_fee_percentage_dec <= 1):
                      raise ValueError("POOL_FEE_PERCENTAGE must be between 0 and 1")
            except ValueError as e:
                 self.logger.error(f"Invalid POOL_FEE_PERCENTAGE '{pool_fee_percentage_str}': {e}. Using default {DEFAULT_POOL_FEE_PERCENTAGE}.", exc_info=True)
                 pool_fee_percentage_dec = Decimal(DEFAULT_POOL_FEE_PERCENTAGE)
                 
            if not pool_fee_address:
                 self.logger.warning("POOL_FEE_ADDRESS environment variable not set or empty. Pool fee cannot be distributed.")
                 # Proceed without pool fee? Or fail?
                 # For now, assume pool fee is optional if address is missing.
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
                self.logger.info("--- DEBUG MODE: SIMULATING TRANSACTION ---")
                self.logger.info(f"Would send to {len(recipients_for_airdrop)} recipients.")
                self.logger.info(f"Total ERG in outputs: {calculated_total_erg:.8f} ERG")
                # Log the calculated pool fee details explicitly during dry run
                self.logger.info(f"Calculated Pool Fee Amount: {final_pool_fee_amount:.8f} ERG")
                self.logger.info(f"Pool Fee Address: {final_pool_fee_address}")
                # Simulate success in debug mode
                self.logger.info("Distribution simulation completed successfully")
                # Ensure we return the dictionary containing the plan
                return distribution 
            
            # Execute actual airdrop
            self.logger.info("Executing airdrop transaction...")
            airdrop = BaseAirdrop(config=airdrop_config)
            result = airdrop.execute() # Assumes BaseAirdrop.execute() exists and returns object with status and tx_id
            
            if result and result.status == "completed" and result.tx_id:
                 self.logger.info(f"Airdrop transaction successful. TX ID: {result.tx_id}")
                 # On successful non-dry-run, return the tx_id
                 return result.tx_id 
            else:
                 self.logger.error(f"Airdrop transaction failed or did not return TX ID. Result: {result}")
                 return None
            
        except ValueError as ve:
            # Catch specific ValueErrors raised during calculations (e.g., insufficient balance)
            self.logger.error(f"Distribution pre-check failed: {ve}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during distribution execution: {e}", exc_info=True)
            return None