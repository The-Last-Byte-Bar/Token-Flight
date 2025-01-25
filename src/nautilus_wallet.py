from typing import Optional, Dict, Tuple, List, Any
import logging
import json
import time
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from models import WalletConfig
from ergo_python_appkit.appkit import ErgoAppKit

class NautilusNotFoundError(Exception):
    """Raised when Nautilus extension cannot be found"""
    pass

class NautilusWalletManager:
    """
    Manages wallet operations using Nautilus dApp Connector (EIP-12) via Selenium
    """
    
    NAUTILUS_EXTENSION_ID = "fghancdmplgpgcknceohigfkjcgpkdec"
    CHROME_EXTENSION_PATHS = [
        # Linux paths
        "~/.config/google-chrome/Default/Extensions",
        "~/.config/chromium/Default/Extensions",
        # Add more paths as needed
    ]
    
    def __init__(self, ergo_appkit: ErgoAppKit, wallet_config: WalletConfig, **kwargs):
        self.ergo = ergo_appkit
        self.wallet_config = wallet_config
        self._wallet_address = None
        self.logger = logging.getLogger(__name__)
        self.driver = None
        self.extension_path = self.find_nautilus_extension()
        self.setup_driver()
        
    def find_nautilus_extension(self) -> str:
        """Find Nautilus extension directory"""
        for base_path in self.CHROME_EXTENSION_PATHS:
            path = os.path.expanduser(base_path)
            if not os.path.exists(path):
                continue
                
            extension_path = os.path.join(path, self.NAUTILUS_EXTENSION_ID)
            if os.path.exists(extension_path):
                # Get the latest version directory
                versions = os.listdir(extension_path)
                if versions:
                    latest_version = sorted(versions)[-1]
                    full_path = os.path.join(extension_path, latest_version)
                    self.logger.info(f"Found Nautilus extension at: {full_path}")
                    return full_path
        
        raise NautilusNotFoundError(
            "Could not find Nautilus extension. Please make sure it's installed in Chrome/Chromium."
            "\nExpected locations:"
            "\n - ~/.config/google-chrome/Default/Extensions/fghancdmplgpgcknceohigfkjcgpkdec/*"
            "\n - ~/.config/chromium/Default/Extensions/fghancdmplgpgcknceohigfkjcgpkdec/*"
        )
        
    def setup_driver(self):
        """Set up Chrome driver with Nautilus extension"""
        try:
            chrome_options = Options()
            
            # Add Nautilus extension
            chrome_options.add_argument(f'--load-extension={self.extension_path}')
            
            # Additional options for automation
            if self.wallet_config.headless:
                chrome_options.add_argument('--headless=new')
            
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Enable debug logging if needed
            if self.wallet_config.debug:
                chrome_options.add_argument('--enable-logging')
                chrome_options.add_argument('--v=1')
            
            # Initialize driver
            service = Service('chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set reasonable timeout
            self.driver.set_script_timeout(30)
            
            # Navigate to a blank page and wait for extension
            self.driver.get('chrome://extensions')
            time.sleep(2)  # Give extension time to initialize
            self.driver.get('about:blank')
            
            # Wait for ergoConnector to be available
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script(
                        "return window.ergoConnector !== undefined"
                    )
                )
            except TimeoutException:
                raise NautilusNotFoundError(
                    "Nautilus extension did not initialize properly. "
                    "Please check if it's enabled in Chrome/Chromium."
                )
            
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {str(e)}")
            raise

    def check_nautilus_available(self) -> bool:
        """Check if Nautilus wallet is available"""
        try:
            result = self.driver.execute_script("""
                if (!window.ergoConnector || !window.ergoConnector.nautilus) {
                    return false;
                }
                return true;
            """)
            
            available = bool(result)
            if available:
                self.logger.info("Nautilus wallet is available")
            else:
                self.logger.warning("Nautilus wallet is not available")
            return available
            
        except Exception as e:
            self.logger.error(f"Error checking Nautilus availability: {str(e)}")
            return False

    async def initialize(self) -> bool:
        """Initialize connection with Nautilus wallet"""
        try:
            if not self.check_nautilus_available():
                raise ValueError("Nautilus wallet is not available")
                
            # Request connection
            connected = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                window.ergoConnector.nautilus.connect()
                    .then(result => callback(result))
                    .catch(error => {
                        console.error('Connection error:', error);
                        callback(false);
                    });
            """)
            
            if not connected:
                self.logger.warning("Failed to connect to Nautilus wallet")
                return False
                
            # Get wallet context and address
            address = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                window.ergo.get_change_address()
                    .then(address => callback(address))
                    .catch(error => {
                        console.error('Address error:', error);
                        callback(null);
                    });
            """)
            
            if not address:
                raise ValueError("Failed to get wallet address")
                
            self._wallet_address = address
            self.logger.info(f"Connected to Nautilus wallet with address: {self._wallet_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Nautilus wallet: {str(e)}")
            raise

    async def get_balance(self) -> Tuple[float, Dict[str, int]]:
        """Get wallet ERG and token balances"""
        try:
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                Promise.all([
                    window.ergo.get_balance(),
                    window.ergo.get_balance('all')
                ])
                .then(([ergBalance, tokenBalances]) => {
                    callback({ erg: ergBalance, tokens: tokenBalances });
                })
                .catch(error => {
                    console.error('Balance error:', error);
                    callback(null);
                });
            """)
            
            if not result:
                raise ValueError("Failed to get balances")
                
            erg_balance = float(result['erg'])
            token_balances = {
                t['tokenId']: int(t['amount'])
                for t in result['tokens']
            }
            
            return erg_balance, token_balances
            
        except Exception as e:
            self.logger.error(f"Error getting balances: {str(e)}")
            raise

    async def sign_transaction(self, unsigned_tx: dict) -> dict:
        """Sign transaction using Nautilus wallet"""
        try:
            # Convert Python dict to JSON string for proper JS handling
            tx_json = json.dumps(unsigned_tx)
            
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                const unsignedTx = JSON.parse(arguments[0]);
                
                window.ergo.sign_tx(unsignedTx)
                    .then(signedTx => callback(JSON.stringify(signedTx)))
                    .catch(error => {
                        console.error('Signing error:', error);
                        callback(null);
                    });
            """, tx_json)
            
            if not result:
                raise ValueError("Failed to sign transaction")
                
            return json.loads(result)
            
        except Exception as e:
            self.logger.error(f"Error signing transaction: {str(e)}")
            raise

    async def submit_tx(self, signed_tx: dict) -> str:
        """Submit signed transaction to the network"""
        try:
            # Convert Python dict to JSON string for proper JS handling
            tx_json = json.dumps(signed_tx)
            
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                const signedTx = JSON.parse(arguments[0]);
                
                window.ergo.submit_tx(signedTx)
                    .then(txId => callback(txId))
                    .catch(error => {
                        console.error('Submit error:', error);
                        callback(null);
                    });
            """, tx_json)
            
            if not result:
                raise ValueError("Failed to submit transaction")
                
            return str(result)
            
        except Exception as e:
            self.logger.error(f"Error submitting transaction: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from Nautilus wallet"""
        try:
            result = self.driver.execute_async_script("""
                const callback = arguments[arguments.length - 1];
                window.ergoConnector.nautilus.disconnect()
                    .then(() => callback(true))
                    .catch(error => {
                        console.error('Disconnect error:', error);
                        callback(false);
                    });
            """)
            
            if result:
                self._wallet_address = None
                self.logger.info("Disconnected from Nautilus wallet")
            else:
                self.logger.warning("Failed to disconnect from Nautilus wallet")
                
        except Exception as e:
            self.logger.error(f"Error disconnecting from wallet: {str(e)}")
            raise

    def cleanup(self):
        """Clean up resources"""
        try:
            if self._wallet_address:
                # Try to disconnect gracefully
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(self.disconnect())
                
            if self.driver:
                self.driver.quit()
                self.logger.info("Chrome driver cleaned up")
                
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {str(e)}")