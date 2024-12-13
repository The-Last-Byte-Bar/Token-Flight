from typing import Optional, Union, List
from dataclasses import dataclass
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import (
    Address, ErgoValue, OutBox, SignedTransaction, 
    UnsignedTransaction, Mnemonic, SecretString
)

class TransactionSigner:
    """Handles transaction signing using either node or mnemonic."""
    
    def __init__(self, ergo: ErgoAppKit):
        self.ergo = ergo
        self._mnemonic = None
        self._mnemonic_password = None
        self._prover = None
    
    def configure_mnemonic(self, mnemonic: str, password: Optional[str] = None) -> None:
        """Configure mnemonic and optional password for signing."""
        self._mnemonic = mnemonic
        self._mnemonic_password = password or ""
        
        # Create secrets and prover
        mnemonic_secret = SecretString.create(self._mnemonic)
        password_secret = SecretString.create(self._mnemonic_password)
        
        # Get blockchain context and create prover
        ergo_client = RestApiErgoClient.create(
            self.ergo.nodeUrl,
            self.ergo.networkType,
            "",  # No API key needed for mnemonic
            self.ergo.explorerUrl
        )
        
        def create_context(ctx):
            mnemonic = Mnemonic.create(mnemonic_secret, password_secret)
            prover_builder = ctx.newProverBuilder()
            prover_builder.withMnemonic(mnemonic, False)
            prover_builder.withEip3Secret(0)
            return prover_builder.build()
        
        self._prover = ergo_client.execute(create_context)
    
    def sign_transaction(self, unsigned_tx: UnsignedTransaction, use_node: bool = True) -> SignedTransaction:
        """
        Sign transaction using either node wallet or mnemonic.
        
        Args:
            unsigned_tx: The unsigned transaction to sign
            use_node: If True, use node wallet. If False, use mnemonic
            
        Returns:
            SignedTransaction: The signed transaction
            
        Raises:
            ValueError: If mnemonic signing is requested but no mnemonic configured
        """
        if use_node:
            return self.ergo.signTransactionWithNode(unsigned_tx)
        else:
            if not self._mnemonic or not self._prover:
                raise ValueError("Mnemonic not configured for signing")
            return self._prover.sign(unsigned_tx)