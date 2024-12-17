from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from decimal import Decimal

@dataclass
class RecipientAmount:
    """Individual recipient with their distribution amount"""
    address: str
    amount: float

@dataclass
class TokenConfig:
    """Configuration for a token to be distributed"""
    def __init__(self, token_name: str, token_id: Optional[str] = None, decimals: int = 0,
                 total_amount: Optional[float] = None, amount_per_recipient: Optional[float] = None,
                 min_amount: float = 0.001, recipients: Optional[List[RecipientAmount]] = None):
        self.token_name = token_name
        self.token_id = token_id
        self.decimals = decimals
        self.total_amount = total_amount
        self.amount_per_recipient = amount_per_recipient
        self.min_amount = min_amount
        self.recipients = recipients

    def validate(self) -> bool:
        """Validate token configuration"""
        # Case 1: Variable distribution per recipient
        if self.recipients is not None:
            if self.total_amount is not None or self.amount_per_recipient is not None:
                raise ValueError("Cannot specify total_amount or amount_per_recipient when using per-recipient amounts")
            if not self.recipients:
                raise ValueError("Recipients list cannot be empty when using per-recipient amounts")
            total = sum(r.amount for r in self.recipients)
            if total <= 0:
                raise ValueError("Total of recipient amounts must be greater than 0")
            return True

        # Case 2: Standard distribution (existing logic)
        if self.total_amount is None and self.amount_per_recipient is None:
            raise ValueError("Either total_amount, amount_per_recipient, or recipients must be specified")
        if self.total_amount is not None and self.amount_per_recipient is not None:
            raise ValueError("Cannot specify both total_amount and amount_per_recipient")
        if self.total_amount is not None and self.total_amount <= 0:
            raise ValueError("Total amount must be greater than 0")
        if self.amount_per_recipient is not None and self.amount_per_recipient <= 0:
            raise ValueError("Amount per recipient must be greater than 0")
        return True

    def get_total_amount(self) -> float:
        """Calculate total amount for distribution"""
        if self.recipients is not None:
            return sum(r.amount for r in self.recipients)
        if self.total_amount is not None:
            return self.total_amount
        if self.amount_per_recipient is not None:
            return self.amount_per_recipient  # Note: This needs to be multiplied by recipient count later
        return 0.0
        
@dataclass
class WalletConfig:
    """Configuration for wallet access"""
    node_url: str
    network_type: str
    explorer_url: str
    node_api_key: Optional[str] = None
    node_wallet_address: Optional[str] = None
    wallet_mnemonic: Optional[str] = None
    mnemonic_password: Optional[str] = None

    def validate(self) -> bool:
        if not self.node_url or not self.network_type or not self.explorer_url:
            raise ValueError("Missing required network configuration")
        if not (self.node_api_key and self.node_wallet_address) and not self.wallet_mnemonic:
            raise ValueError(
                "Either node credentials (API key + wallet address) or mnemonic must be provided"
            )
        return True

@dataclass
class AirdropRecipient:
    """Recipient information for airdrop"""
    address: str
    amount: float = 0
    hashrate: float = 0.0

@dataclass
class AirdropConfig:
    """Main configuration for airdrop execution"""
    wallet_config: WalletConfig
    tokens: List[TokenConfig]
    min_hashrate: float = 0
    debug: bool = False
    headless: bool = False
    recipients_file: Optional[str] = None
    recipient_addresses: Optional[List[str]] = None

    def validate(self) -> bool:
        self.wallet_config.validate()
        for token in self.tokens:
            token.validate()
        if not self.tokens:
            raise ValueError("At least one token configuration must be provided")
        return True

@dataclass
class TransactionResult:
    """Result of airdrop transaction"""
    status: str  # 'completed', 'failed', 'debug', 'cancelled'
    tx_id: Optional[str] = None
    explorer_url: Optional[str] = None
    error: Optional[str] = None
    recipients_count: int = 0
    distributions: List[Dict[str, Union[str, float, int]]] = None