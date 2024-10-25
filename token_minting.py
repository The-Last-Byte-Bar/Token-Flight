# token_minting.py
import logging
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address
from config import Config, TokenConfig
from fee_calculator import calculate_total_fees, ERG_TO_NANOERG, MIN_BOX_VALUE, BASE_FEE
import math

logger = logging.getLogger(__name__)

def calculate_end_height(appKit: ErgoAppKit, config: Config) -> int:
    """Calculate the end height based on total tokens and distribution rate"""
    current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    return current_height + config.distribution.maxDuration

def mint_tokens_to_proxy(appKit: ErgoAppKit, config: Config, token_config: TokenConfig, 
                        proxy_contract: bytes, end_height: int) -> str:
    """Mint tokens and fund proxy contract with sufficient ERG for all operations"""
    # Get total fees needed
    total_fees = calculate_total_fees(config, end_height)
    logger.info(f"Calculated total fees needed: {total_fees/ERG_TO_NANOERG:.9f} ERG")
    
    # Add minimum box value for the minting box
    total_erg_needed = total_fees + MIN_BOX_VALUE
    
    # Get unspent boxes for transaction
    unspent_boxes = appKit.boxesToSpend(config.minter_address, total_erg_needed + BASE_FEE)
    token_id = unspent_boxes[0].getId().toString()
    
    # Create minting output
    mint_output = appKit.mintToken(
        value=total_erg_needed,
        tokenId=token_id,
        tokenName=token_config.name,
        tokenDesc=token_config.description,
        mintAmount=token_config.totalAmount,  # Updated naming
        decimals=token_config.decimals,
        contract=appKit.contractFromTree(proxy_contract)
    )
        
    # Build and send transaction
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[mint_output],
        fee=BASE_FEE,
        sendChangeTo=Address.create(config.minter_address).getErgoAddress()
    )
    
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    tx_id = appKit.sendTransaction(signed_tx)
    
    logger.info(f"Minting transaction sent. Transaction ID: {tx_id}")
    logger.info(f"Contract funded with {total_erg_needed/ERG_TO_NANOERG:.9f} ERG")
    logger.info(f"Token ID: {token_id}")
    
    return token_id