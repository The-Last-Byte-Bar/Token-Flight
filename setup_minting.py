# setup_minting.py
import asyncio
import logging
import sys
import json
from datetime import datetime
from ergo_python_appkit.appkit import ErgoAppKit
from config import load_config, validate_config, TokenConfig
from proxy_contract import create_proxy_contract, calculate_total_fees
from token_minting import mint_tokens_to_proxy, calculate_end_height
from org.ergoplatform.appkit import Address

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def setup_token_distribution(appKit: ErgoAppKit, config, token_config: TokenConfig, 
                                 unlock_height: int, end_height: int):
    """Setup distribution for a single token"""
    logger.info(f"Starting setup for token: {token_config.name}")
    try:
        # Create proxy contract
        logger.debug(f"Creating proxy contract for {token_config.name}...")
        proxy_contract = create_proxy_contract(
            appKit,
            config.recipient_wallets,
            unlock_height,
            config.node.node_address,
            end_height
        )
        
        # Get proxy contract address
        proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
        logger.info(f"Created proxy contract address for {token_config.name}: {proxy_address}")
        
        # Mint tokens and fund contract
        logger.debug(f"Starting token minting for {token_config.name}...")
        token_id = mint_tokens_to_proxy(appKit, config, token_config, proxy_contract, end_height)
        logger.info(f"Successfully minted token: {token_config.name} (ID: {token_id})")
        
        return (token_config.name.lower().replace("test", "_token"), {
            "token_id": token_id,
            "distribution_type": token_config.distribution.type,
            "tokens_per_round": token_config.distribution.tokensPerRound,
            "decimals": token_config.decimals,
            "total_amount": token_config.totalAmount
        })
        
    except Exception as e:
        logger.error(f"Error setting up token {token_config.name}: {str(e)}", exc_info=True)
        raise

async def main():
    if len(sys.argv) < 3:
        print("Usage: python setup_minting.py <config_file> <output_file>")
        sys.exit(1)

    try:
        logger.info("Starting token setup process...")
        
        # Load configuration
        config_path = sys.argv[1]
        output_file = sys.argv[2]
        logger.debug(f"Loading config from {config_path}")
        config = load_config(config_path)
        validate_config(config)
        logger.info("Configuration loaded and validated successfully")
        
        # Initialize ErgoAppKit
        logger.debug("Initializing ErgoAppKit...")
        appKit = ErgoAppKit(
            config.node.api_url,
            config.node.network_type,
            config.node.explorer_url,
            config.node.api_key
        )
        logger.info("ErgoAppKit initialized successfully")
        
        # Calculate common parameters
        logger.debug("Getting current block height...")
        current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        unlock_height = current_height + 1
        end_height = current_height + config.distribution.maxDuration
        
        # Log distribution parameters
        estimated_hours = config.distribution.maxDuration * 2 / 60
        logger.info(f"""
Distribution Parameters:
----------------------
Current Height: {current_height}
Unlock Height: {unlock_height}
End Height: {end_height}
Total Blocks: {config.distribution.maxDuration}
Estimated Duration: {estimated_hours:.2f} hours
Total Tokens to Create: {len(config.tokens)}
Recipients: {len(config.recipient_wallets)}
Node Address: {config.node.node_address}
Network Type: {config.node.network_type}
""")
        
        # Setup each token distribution
        logger.info("Starting token distribution setup...")
        tasks = []
        proxy_address = None  # Will store the first proxy address
        
        for token_config in config.tokens:
            logger.info(f"Creating setup task for {token_config.name}")
            task = asyncio.create_task(
                setup_token_distribution(
                    appKit, 
                    config, 
                    token_config, 
                    unlock_height, 
                    end_height
                )
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        logger.info("Waiting for all token setup tasks to complete...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and check for errors
        tokens_dict = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with error: {str(result)}")
                raise result
            elif isinstance(result, tuple):
                key, value = result
                tokens_dict[key] = value
                if proxy_address is None:
                    proxy_address = value.get("proxy_address")
        
        logger.info(f"Successfully set up {len(tokens_dict)} tokens")
        
        # Save distribution information
        logger.debug("Preparing output data...")
        output_data = {
            "proxy_contract_address": proxy_address,
            "tokens": tokens_dict,
            "recipient_wallets": config.recipient_wallets,
            "blocks_between_dispense": config.distribution.defaultBlocksBetweenDispense,
            "unlock_height": unlock_height,
            "node_address": config.node.node_address
        }
        
        logger.debug(f"Saving output to {output_file}")
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Distribution information saved to {output_file}")
        logger.info("Setup completed successfully!")
        
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        logger.info("Starting script execution...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)