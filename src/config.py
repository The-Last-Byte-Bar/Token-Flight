import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Define default paths relative to this config file's location (src/)
DEFAULT_ENV_PATH = Path(__file__).parent.parent / '.env'
BONUS_ENV_PATH = Path(__file__).parent.parent / '.env.bonus'
DEMURRAGE_ENV_PATH = Path(__file__).parent.parent / '.env.demurrage'

@dataclass
class NodeConfig:
    url: str
    explorer_url: str
    network_type: str = 'mainnet' # Or 'testnet'

@dataclass
class WalletConfig:
    mnemonic: str
    address: Optional[str] = None # Can be derived or specified
    mnemonic_password: str = ''

@dataclass
class TelegramConfig:
    # For regular service notifications
    bot_token: Optional[str] = None
    admin_chat_id: Optional[str] = None
    # For separate admin/test summary notifications
    admin_bot_token: Optional[str] = None
    admin_summary_chat_id: Optional[str] = None

@dataclass
class ApiSettings:
    sigscore_url: str = 'https://api.ergominers.com/sigscore/miners?pageSize=5000'
    miners_participation_url: str = 'https://api.ergominers.com/sigscore/miners/average-participation'
    miners_bonus_url: str = 'https://api.ergominers.com/sigscore/miners/bonus'
    ergo_api_base: str = 'https://api.ergoplatform.com/api/v1'
    # Add other relevant API base URLs here

@dataclass
class ServiceSpecificConfig:
    # Example: Demurrage specific settings
    min_box_value_nanoerg: int = int(0.001 * 1e9)
    tx_fee_nanoerg: int = int(0.001 * 1e9)
    wallet_buffer_nanoerg: int = int(0.001 * 1e9)
    pool_fee_percentage: str = '0.01'
    pool_fee_address: str = "9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt"
    min_confirmations: int = 720 # Added for BlockHeightCollector
    # Add bonus specific settings if needed

@dataclass
class AppConfig:
    node: NodeConfig
    wallet: WalletConfig
    apis: ApiSettings
    telegram: TelegramConfig
    service: ServiceSpecificConfig # Holds service-specific overrides/values
    dry_run: bool = False
    debug: bool = False
    # Add general app settings like log level etc. if needed

    # Secrets - consider loading these differently if more security needed
    mining_wave_api_key: Optional[str] = None


# Keep track if we already loaded
_loaded_config: Optional[AppConfig] = None

def load_config(service_type: Optional[str] = None) -> AppConfig:
    """
    Loads configuration from environment variables and .env files.
    Prioritizes service-specific .env files, then base .env, then environment variables.
    
    Args:
        service_type: 'bonus' or 'demurrage' to load specific env file.
    """
    global _loaded_config
    if _loaded_config:
        # Optionally add logic here to check if service_type matches the loaded one
        # For now, just return the cached config. Be careful if services need truly distinct settings.
        # logger.debug("Returning cached config.")
        # return _loaded_config
        # Re-loading every time ensures service context is respected if needed
        logger.debug("Re-loading config...")


    # Load base .env file first (if exists) - provides defaults
    loaded_base = load_dotenv(dotenv_path=DEFAULT_ENV_PATH, verbose=True)
    if loaded_base:
        logger.info(f"Loaded base configuration from {DEFAULT_ENV_PATH}")
    else:
        logger.info(f"Base configuration file not found at {DEFAULT_ENV_PATH}, relying on environment variables or service-specific files.")

    # Load service-specific .env file (if specified and exists) - overrides base
    service_env_path = None
    if service_type == 'bonus':
        service_env_path = BONUS_ENV_PATH
    elif service_type == 'demurrage':
        service_env_path = DEMURRAGE_ENV_PATH

    if service_env_path:
        loaded_service = load_dotenv(dotenv_path=service_env_path, override=True, verbose=True)
        if loaded_service:
            logger.info(f"Loaded and applied overrides from {service_env_path}")
        else:
            logger.info(f"Service-specific configuration file not found at {service_env_path}.")

    # Now, read values from environment (which includes loaded .env vars)
    node_config = NodeConfig(
        url=os.getenv('NODE_URL', 'http://localhost:9053'), # Default to common local node
        explorer_url=os.getenv('EXPLORER_URL', 'https://explorer.ergoplatform.com/'),
        network_type=os.getenv('NETWORK_TYPE', 'mainnet'),
    )

    wallet_config = WalletConfig(
        mnemonic=os.getenv('WALLET_MNEMONIC', ''), # Make mandatory?
        address=os.getenv('WALLET_ADDRESS'), # Optional
        mnemonic_password=os.getenv('MNEMONIC_PASSWORD', '')
    )
    if not wallet_config.mnemonic:
        logger.error("WALLET_MNEMONIC environment variable is required but not set.")
        raise ValueError("WALLET_MNEMONIC must be set in your environment or .env file.")


    api_settings = ApiSettings(
        sigscore_url=os.getenv('SIGSCORE_API_URL', ApiSettings.sigscore_url),
        miners_participation_url=os.getenv('MINERS_PARTICIPATION_API_URL', ApiSettings.miners_participation_url),
        miners_bonus_url=os.getenv('MINERS_BONUS_API_URL', ApiSettings.miners_bonus_url),
        ergo_api_base=os.getenv('ERGO_API_BASE', ApiSettings.ergo_api_base),
    )

    telegram_config = TelegramConfig(
        bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
        admin_chat_id=os.getenv('TELEGRAM_ADMIN_CHAT_ID'),
        admin_bot_token=os.getenv('ADMIN_TELEGRAM_BOT_TOKEN'),
        admin_summary_chat_id=os.getenv('ADMIN_TELEGRAM_CHAT_ID') # Note env var name
    )

    # Load service-specific settings - Allow overrides via environment
    service_cfg = ServiceSpecificConfig(
         min_box_value_nanoerg=int(os.getenv('MIN_BOX_VALUE', ServiceSpecificConfig.min_box_value_nanoerg)),
         tx_fee_nanoerg=int(os.getenv('TX_FEE', ServiceSpecificConfig.tx_fee_nanoerg)),
         wallet_buffer_nanoerg=int(os.getenv('WALLET_BUFFER', ServiceSpecificConfig.wallet_buffer_nanoerg)),
         pool_fee_percentage=os.getenv('POOL_FEE_PERCENTAGE', ServiceSpecificConfig.pool_fee_percentage),
         pool_fee_address=os.getenv('POOL_FEE_ADDRESS', ServiceSpecificConfig.pool_fee_address),
         min_confirmations=int(os.getenv('MIN_CONFIRMATIONS', ServiceSpecificConfig.min_confirmations)),
         # Add more service-specific vars here
    )

    app_config = AppConfig(
        node=node_config,
        wallet=wallet_config,
        apis=api_settings,
        telegram=telegram_config,
        service=service_cfg,
        dry_run=os.getenv('DRY_RUN', 'false').lower() == 'true',
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        mining_wave_api_key=os.getenv('MINING_WAVE_API_KEY')
    )
    
    # Validate required fields were loaded
    if not app_config.node.url: raise ValueError("NODE_URL is required.")
    if not app_config.node.explorer_url: raise ValueError("EXPLORER_URL is required.")
    # Add more validations as needed

    _loaded_config = app_config # Cache the loaded config
    logger.info(f"Configuration loaded. Dry Run: {app_config.dry_run}, Debug: {app_config.debug}")
    return app_config

# Example usage (optional, for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        print("--- Loading Default Config ---")
        default_cfg = load_config()
        print(default_cfg)

        print("\n--- Loading Bonus Config ---")
        bonus_cfg = load_config(service_type='bonus')
        print(bonus_cfg)
        
        print("\n--- Loading Demurrage Config ---")
        demurrage_cfg = load_config(service_type='demurrage')
        print(demurrage_cfg)
        
        # Demonstrate accessing values
        print(f"\nNode URL (Demurrage): {demurrage_cfg.node.url}")
        print(f"Dry Run (Demurrage): {demurrage_cfg.dry_run}")
        print(f"Pool Fee Addr (Demurrage): {demurrage_cfg.service.pool_fee_address}")

    except ValueError as e:
        print(f"Error loading config: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 