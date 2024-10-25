# main.py
import asyncio
import logging
import sys
from ergo_python_appkit.appkit import ErgoAppKit
from config import load_config, validate_config
from proxy_contract import create_proxy_contract
from token_minting import mint_tokens_to_proxy
from utxo_scanner import scan_proxy_utxos
from token_distribution import distribute_tokens

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    config = load_config(config_path)
    validate_config(config)

    appKit = ErgoAppKit(config.node_url, config.network_type, config.explorer_url, config.api_key)

    # Create proxy contract
    current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    unlock_height = current_height + 1
    proxy_contract = create_proxy_contract(appKit, config.recipient_wallets, unlock_height, config.node_address)
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    logger.info(f"Proxy contract address: {proxy_address}")

    # Mint tokens
    token_id = mint_tokens_to_proxy(appKit, config, proxy_contract)
    logger.info(f"Tokens minted. Token ID: {token_id}")

    # Example distribution loop
    while True:
        try:
            utxos = scan_proxy_utxos(appKit, proxy_contract, token_id)
            if utxos:
                distribute_tokens(appKit, utxos, token_id, config.recipient_wallets, config.tokens_per_round, proxy_contract)
            else:
                logger.info("No UTXOs available for distribution")
            await asyncio.sleep(config.blocks_between_dispense * 120)  # Assuming 2 minutes per block
        except Exception as e:
            logger.error(f"Error during distribution: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    asyncio.run(main())