import os
from dotenv import load_dotenv
from ergo_python_appkit.appkit import ErgoAppKit, ErgoValueT
from org.ergoplatform.appkit import Address, ErgoValue
import logging
import datetime
import sys
from java.lang import Long
import hashlib
from nft_register_helper import create_nft_registers

# Constants
ERG_TO_NANOERG = 1e9
MIN_BOX_VALUE = int(0.005 * ERG_TO_NANOERG)  # 0.005 ERG for NFT box
FEE = int(0.001 * ERG_TO_NANOERG)  # 0.001 ERG fee

def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'logs/nft_minting_{timestamp}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger = setup_logging()

# Required environment variables check
required_vars = [
    'NODE_URL', 'NODE_API_KEY', 'NETWORK', 'EXPLORER_URL', 'WALLET_ADDRESS',
    'NFT_NAME', 'NFT_DESCRIPTION', 'NFT_DECIMALS',
    'NFT_EDITION', 'NFT_EVENT', 'NFT_DATE', 'NFT_CREATOR', 'NFT_PROJECT',
    'NFT_COLLECTION_NAME', 'NFT_COLLECTION_FAMILY', 'IPFS_HASH', 'IPFS_FILENAME'
]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Configuration
node_url = os.getenv('NODE_URL')
node_api_key = os.getenv('NODE_API_KEY')
network_type = os.getenv('NETWORK')
explorer_url = os.getenv('EXPLORER_URL')
sender_address = os.getenv('WALLET_ADDRESS')

# NFT metadata
nft_name = os.getenv('NFT_NAME')
nft_description = os.getenv('NFT_DESCRIPTION')
nft_decimals = int(os.getenv('NFT_DECIMALS', '0'))
nft_edition = os.getenv('NFT_EDITION')
nft_event = os.getenv('NFT_EVENT')
nft_date = os.getenv('NFT_DATE')
nft_creator = os.getenv('NFT_CREATOR')
nft_project = os.getenv('NFT_PROJECT')
nft_collection_name = os.getenv('NFT_COLLECTION_NAME')
nft_collection_family = os.getenv('NFT_COLLECTION_FAMILY')
ipfs_hash = os.getenv('IPFS_HASH')
ipfs_filename = os.getenv('IPFS_FILENAME')

def calculate_image_hash(filepath: str) -> bytes:
    """Calculate SHA256 hash of image file"""
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).digest()

def log_config():
    """Log configuration settings"""
    logger.info("Starting NFT minting process with configuration:")
    logger.info(f"Network Type: {network_type}")
    logger.info(f"Explorer URL: {explorer_url}")
    logger.info(f"Sender Address: {sender_address}")
    logger.info(f"NFT Name: {nft_name}")
    logger.info(f"NFT Description: {nft_description}")
    logger.info(f"NFT Edition: {nft_edition}")
    logger.info(f"Collection Name: {nft_collection_name}")
    logger.info(f"Collection Family: {nft_collection_family}")
    logger.info(f"IPFS URL: ipfs://{ipfs_hash}/{ipfs_filename}")
    logger.info(f"Minimum Box Value: {MIN_BOX_VALUE/ERG_TO_NANOERG:.9f} ERG")

def create_detailed_description():
    """Create a detailed description combining multiple metadata fields"""
    return (f"{nft_description}\n\n"
            f"Edition: {nft_edition}\n"
            f"Event: {nft_event}\n"
            f"Date: {nft_date}\n"
            f"Creator: {nft_creator}\n"
            f"Project: {nft_project}\n"
            f"Collection: {nft_collection_name}\n"
            f"Family: {nft_collection_family}")

def mint_nft():
    """Main function to mint NFT"""
    try:
        # Log configuration
        log_config()
        
        # Initialize ErgoAppKit
        logger.info("Initializing ErgoAppKit...")
        ergo = ErgoAppKit(
            node_url,
            network_type,
            explorer_url,
            node_api_key
        )
        logger.info("ErgoAppKit initialized successfully")

        # Calculate total ERG needed
        total_erg_needed = MIN_BOX_VALUE + FEE
        logger.info(f"Total ERG needed: {total_erg_needed/ERG_TO_NANOERG:.9f} ERG")

        # Get unspent boxes
        unspent_boxes = ergo.boxesToSpend(sender_address, total_erg_needed)
        token_id = unspent_boxes[0].getId().toString()
        logger.info(f"Token ID will be: {token_id}")

        # Calculate image hash from local file
        image_hash = calculate_image_hash('asset.svg')
        logger.info("Calculated image hash successfully")
        
        # Construct IPFS URL
        ipfs_url = f"ipfs://{ipfs_hash}/{ipfs_filename}"
        logger.info(f"Using IPFS URL: {ipfs_url}")

        # Create detailed description
        detailed_description = create_detailed_description()

        # Create registers using helper function
        logger.info("Creating NFT registers...")
        registers = create_nft_registers(
            ergo=ergo,
            name=nft_name,
            description=detailed_description,
            decimals=nft_decimals,
            nft_type=1,
            image_hash=image_hash,
            ipfs_url=ipfs_url
        )
        logger.info("NFT registers created successfully")

        # Create NFT output box
        nft_output_box = ergo.buildOutBox(
            value=MIN_BOX_VALUE,
            tokens={token_id: 1},
            registers=registers,
            contract=ergo.contractFromAddress(sender_address)
        )

        # Build and sign transaction
        logger.info("Building unsigned transaction...")
        unsigned_tx = ergo.buildUnsignedTransaction(
            inputs=unspent_boxes,
            outputs=[nft_output_box],
            fee=FEE,
            sendChangeTo=Address.create(sender_address).getErgoAddress()
        )
        
        logger.info("Signing transaction with node wallet...")
        signed_tx = ergo.signTransactionWithNode(unsigned_tx)
        logger.info("Submitting transaction to network...")
        tx_id = ergo.sendTransaction(signed_tx)
        
        logger.info("NFT minted successfully!")
        logger.info(f"Transaction ID: {tx_id}")
        logger.info(f"Token ID: {token_id}")
        
        # Log explorer links
        explorer_base = explorer_url.replace('/api/v1', '')
        logger.info(f"Transaction explorer link: {explorer_base}/transactions/{tx_id}")
        logger.info(f"Token explorer link: {explorer_base}/tokens/{token_id}")
        
        return tx_id, token_id

    except Exception as e:
        logger.error(f"Error minting NFT: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        mint_nft()
    except Exception as e:
        logger.error("NFT minting process failed", exc_info=True)
        sys.exit(1)