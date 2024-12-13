from ergo_python_appkit.appkit import ErgoAppKit
import logging
import jpype
from java.util.function import Function
from org.ergoplatform.appkit import SecretString, Address
from jpype.types import JBoolean

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@jpype.JImplements(Function)
class AddressDerivenExecutor(object):
    def __init__(self, mnemonic: str):
        self._mnemonic = mnemonic
        self.logger = logging.getLogger(__name__ + ".AddressDerivenExecutor")
        self.logger.setLevel(logging.DEBUG)

    @jpype.JOverride
    def apply(self, ctx):
        try:
            self.logger.debug("Attempting to derive address...")
            
            # Create mnemonic secret and use empty password
            mnemonic_secret = SecretString.create(self._mnemonic)
            empty_password = SecretString.empty()
            
            # Build prover exactly like the example
            prover = ctx.newProverBuilder()\
                .withMnemonic(mnemonic_secret, empty_password, JBoolean(False))\
                .withEip3Secret(0)\
                .build()
            
            # Get address
            address = prover.getAddress()
            addr_str = address.toString()
            self.logger.debug(f"Generated address: {addr_str}")
            return addr_str
            
        except Exception as e:
            self.logger.error(f"Failed to derive address: {str(e)}", exc_info=True)
            raise

def validate_address(mnemonic: str, target_address: str):
    """Validate if the mnemonic generates the target address."""
    try:
        # Initialize ErgoAppKit
        ergo = ErgoAppKit(
            "http://213.239.193.208:9053/",
            "mainnet",
            "https://api.ergoplatform.com/api/v1/",
            ""  # Empty API key
        )

        # Try to derive the address
        logger.info("Attempting to derive address from mnemonic...")
        derived_address = ergo._ergoClient.execute(
            AddressDerivenExecutor(mnemonic)
        )
        
        # Log the result
        logger.info(f"Derived address: {derived_address}")
        logger.info(f"Target address: {target_address}")
        
        # Return the match status and derived address
        return {
            "matches": derived_address == target_address,
            "derived_address": derived_address,
            "target_address": target_address
        }
        
    except Exception as e:
        logger.error(f"Error in address validation: {str(e)}")
        raise

if __name__ == "__main__":
    # Your mnemonic and target address
    mnemonic = "hard upon afraid kitten response solve tonight bless hat reopen style until vacant way fruit"
    target_address = "9fk6yNk2acfkypoYVYeuEjCbxPwJSHeAH3qNUXCUipmjVPr6wGP"
    
    print("\nValidating mnemonic and address...")
    print(f"Target address: {target_address}")
    
    result = validate_address(mnemonic, target_address)
    if result["matches"]:
        print("\nSuccess! Mnemonic derives the correct address")
    else:
        print("\nAddress mismatch!")
        print(f"Derived address: {result['derived_address']}")
        print(f"Target address: {result['target_address']}")