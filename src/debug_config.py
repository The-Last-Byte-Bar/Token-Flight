from dotenv import load_dotenv
import os
import logging
from env_config import EnvironmentConfig
from multi_output_builder import MultiOutputBuilder
from wallet_manager import WalletManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_configuration():
    # Load environment variables
    load_dotenv()
    
    # Print all relevant environment variables
    print("\nEnvironment Variables:")
    env_vars = [
        'NODE_URL', 'NODE_API_KEY', 'NETWORK_TYPE', 
        'EXPLORER_URL', 'WALLET_ADDRESS', 'WALLET_MNEMONIC'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        # Mask sensitive data
        if var in ['NODE_API_KEY', 'WALLET_MNEMONIC'] and value:
            masked_value = value[:4] + '****' + value[-4:] if len(value) > 8 else '****'
            print(f"{var}: {masked_value}")
        else:
            print(f"{var}: {value}")

    print("\nTesting EnvironmentConfig:")
    try:
        config = EnvironmentConfig.load()
        print("\nConfig loaded successfully:")
        for key, value in config.items():
            if key in ['node_api_key', 'wallet_mnemonic'] and value:
                masked_value = value[:4] + '****' + value[-4:] if len(value) > 8 else '****'
                print(f"{key}: {masked_value}")
            else:
                print(f"{key}: {value}")
    except Exception as e:
        print(f"Error loading config: {str(e)}")

    print("\nTesting MultiOutputBuilder:")
    try:
        builder = MultiOutputBuilder(
            node_url=os.getenv('NODE_URL'),
            network_type=os.getenv('NETWORK_TYPE'),
            explorer_url=os.getenv('EXPLORER_URL'),
            node_api_key=os.getenv('NODE_API_KEY'),
            node_wallet_address=os.getenv('WALLET_ADDRESS'),
            wallet_mnemonic=os.getenv('WALLET_MNEMONIC')
        )
        print("MultiOutputBuilder initialized successfully")
        
        # Test wallet configuration
        use_node, active_address = builder.wallet_manager.get_signing_config()
        print(f"\nWallet configuration:")
        print(f"Using node: {use_node}")
        print(f"Active address: {active_address}")
        
    except Exception as e:
        print(f"Error initializing builder: {str(e)}")

if __name__ == "__main__":
    debug_configuration()