import os
import json
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from src.nft_service import NFTService

def main():
    # Load environment variables
    load_dotenv()
    
    # Load recipient addresses from JSON file
    with open(project_root / 'nft_recipients.json') as f:
        data = json.load(f)
        recipient_addresses = data['recipient_addresses']
    
    print(f"Loaded {len(recipient_addresses)} recipient addresses")
    
    # Initialize NFT service with the wallet containing NFTs
    nft_service = NFTService(
        wallet_address=os.getenv('WALLET_ADDRESS')  # Using the standard wallet address
    )
    
    try:
        # Execute NFT airdrop
        # Set debug=True to test without executing actual transaction
        result = nft_service.execute_nft_airdrop(
            recipient_addresses=recipient_addresses,
            collection_name="rosen watcher tcg",  # Name of your NFT collection
            debug=False  # Set to False for actual execution
        )
        
        print("\nAirdrop Result:")
        print(f"Status: {result.status}")
        if result.tx_id:
            print(f"Transaction ID: {result.tx_id}")
            print(f"Explorer URL: {result.explorer_url}")
        if result.error:
            print(f"Error: {result.error}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 