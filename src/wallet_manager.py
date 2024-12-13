from typing import Optional, Tuple
import logging
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import (
    SecretString, Mnemonic, Address, RestApiErgoClient, 
    InputBox, UnsignedTransaction, SignedTransaction
)
from jpype.types import JBoolean
import java.lang

class WalletManager:
    """Manages wallet operations with support for both node and mnemonic signing"""
    
    def __init__(self, ergo_appkit: ErgoAppKit, node_url: str, network_type: str, explorer_url: str):
        self.ergo = ergo_appkit
        self.node_url = node_url
        self.network_type = network_type
        self.explorer_url = explorer_url
        self._mnemonic = None
        self._mnemonic_password = None
        self._wallet_address = None
        self._prover = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
    
    def configure_mnemonic(self, mnemonic: str, password: Optional[str] = None) -> None:
        """Configure mnemonic and derive wallet address."""
        try:
            if not mnemonic:
                raise ValueError("Mnemonic cannot be empty")
            
            self.logger.debug(f"Configuring mnemonic (length: {len(mnemonic)})")
            self._mnemonic = mnemonic
            self._mnemonic_password = password or ""
            
            # Create secrets
            mnemonic_secret = SecretString.create(self._mnemonic)
            password_secret = SecretString.create(self._mnemonic_password)
            
            # Derive address using proper NetworkType enum
            network_type = ErgoAppKit.NetworkType(self.network_type)
            self._wallet_address = Address.createEip3Address(
                0,  # Use first address from derivation path
                network_type,
                mnemonic_secret,
                password_secret,
                java.lang.Boolean(True)  # Use pre-calculated keys
            ).toString()
            
            # Initialize prover
            self._prover = self._create_prover()
            
            self.logger.info(f"Mnemonic configured successfully. Derived address: {self._wallet_address}")
            
        except Exception as e:
            self.logger.error(f"Error configuring mnemonic: {str(e)}", exc_info=True)
            raise
    
    def _create_prover(self):
        """Create a prover from mnemonic for transaction signing"""
        try:
            if not self._mnemonic:
                raise ValueError("Mnemonic not configured")
                
            # Create ergo client
            network_type = ErgoAppKit.NetworkType(self.network_type)
            ergo_client = RestApiErgoClient.create(
                self.node_url,
                network_type,
                "",  # No API key needed for mnemonic signing
                self.explorer_url
            )
            
            # Create prover within context
            def create_context(ctx):
                # Create mnemonic instance
                mnemonic = Mnemonic.create(
                    SecretString.create(self._mnemonic),
                    SecretString.create(self._mnemonic_password)
                )
                
                # Build prover
                prover_builder = ctx.newProverBuilder()
                prover_builder.withMnemonic(mnemonic, java.lang.Boolean(False))  # False = don't use pre-calculated keys
                prover_builder.withEip3Secret(0)
                return prover_builder.build()
            
            return ergo_client.execute(create_context)
            
        except java.lang.Exception as e:
            raise Exception(f"Failed to create prover: {str(e)}")
    
    def configure_node_address(self, address: str) -> None:
        """Configure wallet address for node-based signing."""
        if not address:
            raise ValueError("Wallet address cannot be empty")
        self._wallet_address = address
        self.logger.debug(f"Configured node wallet address: {address}")
    
    def get_signing_config(self) -> Tuple[bool, str]:
        """Get wallet configuration.
        
        Returns:
            Tuple[bool, str]: (use_node, wallet_address)
            use_node is True if using node signing, False if using mnemonic
        """
        self.logger.debug(f"Getting signing config - Wallet address: {self._wallet_address}")
        
        if not self._wallet_address:
            raise ValueError("Wallet address not configured")
            
        use_node = not bool(self._mnemonic)
        return use_node, self._wallet_address

    def validate_addresses(self, specified_address: str) -> None:
        """Validate that the specified address matches the wallet address."""
        if not self._wallet_address:
            raise ValueError("Wallet address not configured")
            
        self.logger.debug(f"Validating addresses - Wallet: {self._wallet_address}, Specified: {specified_address}")
        
        if self._wallet_address != specified_address:
            raise ValueError(
                f"Address mismatch: Specified address '{specified_address}' "
                f"does not match wallet address '{self._wallet_address}'"
            )
    
    def sign_transaction(self, unsigned_tx: UnsignedTransaction) -> SignedTransaction:
        """Sign transaction using configured method (mnemonic or node)."""
        if self._mnemonic and self._prover:
            try:
                self.logger.debug("Signing transaction with mnemonic...")
                return self._prover.sign(unsigned_tx)
            except Exception as e:
                self.logger.error(f"Error signing with mnemonic: {str(e)}", exc_info=True)
                raise
        elif self.ergo.apiKey:
            try:
                self.logger.debug("Signing transaction with node...")
                return self.ergo.signTransactionWithNode(unsigned_tx)
            except Exception as e:
                self.logger.error(f"Error signing with node: {str(e)}", exc_info=True)
                raise
        else:
            raise ValueError("No signing method configured (neither mnemonic nor node)")