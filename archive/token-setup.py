import json
import time
import logging
import asyncio
import signal
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, Constants, InputBox
import binascii

# Constants
ERG_TO_NANOERG = 1e9
NANOERG_PER_RECIPIENT = int(0.001 * ERG_TO_NANOERG)
FEE = int(0.001 * ERG_TO_NANOERG)
MIN_BOX_VALUE = int(0.001 * ERG_TO_NANOERG)  # Minimum ERG required per box
CHECK_INTERVAL = 60  # seconds

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            'ergo_distribution.log', maxBytes=10*1024*1024, backupCount=5
        )
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    node_url: str
    explorer_url: str
    api_key: str
    network_type: str
    node_address: str
    minter_address: str
    recipient_wallets: List[str]
    token_name: str
    token_description: str
    token_total_amount: int
    token_decimals: int
    tokens_per_round: int
    blocks_between_dispense: int

def load_config(file_path: str) -> Config:
    with open(file_path, 'r') as config_file:
        config_data = json.load(config_file)
    
    return Config(
        node_url=config_data['node']['nodeApi']['apiUrl'],
        explorer_url=config_data['node']['explorer_url'],
        api_key=config_data['node']['nodeApi']['apiKey'],
        network_type=config_data['node']['networkType'],
        node_address=config_data['node']['nodeAddress'],
        minter_address=config_data['parameters']['minterAddr'],
        recipient_wallets=config_data['parameters']['recipientWallets'],
        token_name=config_data['token']['name'],
        token_description=config_data['token']['description'],
        token_total_amount=config_data['token']['totalAmount'],
        token_decimals=config_data['token']['decimals'],
        tokens_per_round=config_data['distribution']['tokensPerRound'],
        blocks_between_dispense=config_data['distribution']['blocksBetweenDispense']
    )

def validate_config(config: Config) -> None:
    if not all([config.node_url, config.explorer_url, config.api_key, config.network_type,
                config.node_address, config.minter_address, config.recipient_wallets,
                config.token_name, config.token_description, config.token_total_amount,
                config.token_decimals, config.tokens_per_round, config.blocks_between_dispense]):
        raise ValueError("All configuration fields must be filled")
    
    if not isinstance(config.recipient_wallets, list) or len(config.recipient_wallets) == 0:
        raise ValueError("recipient_wallets must be a non-empty list")
    
    if config.token_total_amount <= 0 or config.tokens_per_round <= 0:
        raise ValueError("Token amounts must be positive")
    
    if config.blocks_between_dispense <= 0:
        raise ValueError("blocks_between_dispense must be positive")

def create_proxy_contract(appKit: ErgoAppKit, recipients: List[str], unlock_height: int, node_address: str) -> bytes:
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    node_tree = Address.create(node_address).getErgoAddress().script().bytes()
    node_tree_hex = binascii.hexlify(bytes(node_tree)).decode('utf-8')
    
    contract_script = f"""
    {{
        val recipientTrees = Coll({recipient_trees_str})
        val unlockHeight = {unlock_height}L
        val nodeTree = fromBase16("{node_tree_hex}")
        
        sigmaProp({{
            val validRecipients = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                recipientTrees.exists({{(tree: Coll[Byte]) => 
                    out.propositionBytes == tree
                }})
            }})
            val heightOk = HEIGHT >= unlockHeight
            val validTokenDistribution = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                out.tokens.size == 1 && out.tokens(0)._2 > 0L
            }})
            
            val spentByNode = OUTPUTS(0).propositionBytes == nodeTree
            
            (validRecipients && heightOk && validTokenDistribution) || spentByNode
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)

def mint_tokens_to_proxy(appKit: ErgoAppKit, config: Config, proxy_contract: bytes) -> str:
    erg_amount = NANOERG_PER_RECIPIENT * (len(config.recipient_wallets) + 1)
    unspent_boxes = appKit.boxesToSpend(config.minter_address, erg_amount + FEE)
    
    token_id = unspent_boxes[0].getId().toString()
    
    mint_output = appKit.mintToken(
        value=erg_amount,
        tokenId=token_id,
        tokenName=config.token_name,
        tokenDesc=config.token_description,
        mintAmount=config.token_total_amount,
        decimals=config.token_decimals,
        contract=appKit.contractFromTree(proxy_contract)
    )
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[mint_output],
        fee=FEE,
        sendChangeTo=Address.create(config.minter_address).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    tx_id = appKit.sendTransaction(signed_tx)
    logger.info(f"Minting transaction sent. Transaction ID: {tx_id}")
    logger.info(f"Minted {config.token_total_amount} tokens with {erg_amount/ERG_TO_NANOERG:.9f} ERG locked in proxy contract")
    return token_id

def get_unspent_boxes(appKit: ErgoAppKit, address: str) -> List[InputBox]:
    return appKit.getUnspentBoxes(address)

def dispense_tokens(appKit: ErgoAppKit, token_id: str, recipient_addresses: List[str], tokens_per_round: int, proxy_contract: bytes) -> None:
    total_erg_needed = (NANOERG_PER_RECIPIENT + MIN_BOX_VALUE) * len(recipient_addresses) + FEE
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    
    all_unspent_boxes = get_unspent_boxes(appKit, proxy_address)
    
    # Calculate total available ERG and tokens
    total_available_erg = sum(box.getValue() for box in all_unspent_boxes)
    total_available_tokens = sum(token.getValue() for box in all_unspent_boxes for token in box.getTokens() if token.getId().toString() == token_id)
    
    logger.info(f"Total available ERG: {total_available_erg/ERG_TO_NANOERG:.9f}")
    logger.info(f"Total available tokens: {total_available_tokens}")
    
    if total_available_erg < total_erg_needed:
        raise ValueError(f"Not enough ERG in proxy contract. Available: {total_available_erg/ERG_TO_NANOERG:.9f}, Needed: {total_erg_needed/ERG_TO_NANOERG:.9f}")
    
    if total_available_tokens < tokens_per_round:
        raise ValueError(f"Not enough tokens in proxy contract. Available: {total_available_tokens}, Needed: {tokens_per_round}")
    
    # Select input boxes
    input_boxes = []
    current_erg = 0
    current_tokens = 0
    for box in all_unspent_boxes:
        input_boxes.append(box)
        current_erg += box.getValue()
        current_tokens += sum(token.getValue() for token in box.getTokens() if token.getId().toString() == token_id)
        if current_erg >= total_erg_needed and current_tokens >= tokens_per_round:
            break
    
    if current_erg < total_erg_needed or current_tokens < tokens_per_round:
        raise ValueError(f"Unable to select enough input boxes. ERG: {current_erg/ERG_TO_NANOERG:.9f}, Tokens: {current_tokens}")
    
    outputs = []
    tokens_per_recipient = tokens_per_round // len(recipient_addresses)
    
    for recipient in recipient_addresses:
        output = appKit.buildOutBox(
            value=NANOERG_PER_RECIPIENT + MIN_BOX_VALUE,
            tokens={token_id: tokens_per_recipient},
            registers=None,
            contract=appKit.contractFromAddress(recipient)
        )
        outputs.append(output)
    
    # Calculate change
    change_value = current_erg - total_erg_needed
    change_tokens = current_tokens - tokens_per_round
    
    if change_value > 0 or change_tokens > 0:
        change_output = appKit.buildOutBox(
            value=max(change_value, MIN_BOX_VALUE),
            tokens={token_id: change_tokens} if change_tokens > 0 else None,
            registers=None,
            contract=appKit.contractFromTree(proxy_contract)
        )
        outputs.append(change_output)
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=input_boxes,
        outputs=outputs,
        fee=FEE,
        sendChangeTo=Address.fromErgoTree(proxy_contract, appKit._networkType).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    logger.info(f"Tokens dispensed to {len(recipient_addresses)} recipients. Transaction ID: {tx_id}")
    logger.info(f"Distributed {tokens_per_round} tokens with {total_erg_needed/ERG_TO_NANOERG:.9f} ERG")

class ErgoTokenDistributor:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        validate_config(self.config)
        self.appKit = ErgoAppKit(self.config.node_url, self.config.network_type, self.config.explorer_url, self.config.api_key)
        self.proxy_contract = None
        self.token_id = None
        self.last_dispense_height = 0
        self.running = False

    async def initialize(self) -> None:
        current_height = self.appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        unlock_height = current_height + 1
        
        self.proxy_contract = create_proxy_contract(
            self.appKit,
            self.config.recipient_wallets,
            unlock_height,
            self.config.node_address
        )
        proxy_address = Address.fromErgoTree(self.proxy_contract, self.appKit._networkType).toString()
        logger.info(f"Proxy contract address: {proxy_address}")
        
        self.token_id = mint_tokens_to_proxy(
            self.appKit,
            self.config,
            self.proxy_contract
        )
        
        logger.info(f"Tokens minted. Token ID: {self.token_id}")
        
        self.last_dispense_height = current_height
        
        total_rounds = self.config.token_total_amount // self.config.tokens_per_round
        total_erg_needed = total_rounds * len(self.config.recipient_wallets) * 0.001
        logger.info(f"Total number of distribution rounds: {total_rounds}")
        logger.info(f"Total ERG needed for all rounds: {total_erg_needed:.3f} ERG")

    async def run(self) -> None:
        self.running = True
        while self.running:
            try:
                current_height = self.appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
                
                if current_height >= self.last_dispense_height + self.config.blocks_between_dispense:
                    logger.info(f"Attempting to dispense tokens at block height {current_height}")
                    dispense_tokens(
                        self.appKit,
                        self.token_id,
                        self.config.recipient_wallets,
                        self.config.tokens_per_round,
                        self.proxy_contract
                    )
                    self.last_dispense_height = current_height
                    logger.info(f"Successfully dispensed tokens at block height {current_height}")
            except Exception as e:
                logger.error(f"Error dispensing tokens: {str(e)}")
                logger.exception("Full stack trace:")
                await asyncio.sleep(CHECK_INTERVAL)  # Wait before retrying
            
            await asyncio.sleep(CHECK_INTERVAL)

    def stop(self) -> None:
        self.running = False
        logger.info("Stopping token distribution")

async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    distributor = ErgoTokenDistributor(config_path)

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, stopping distribution...")
        distributor.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await distributor.initialize()
        await distributor.run()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())