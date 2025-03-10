"""
Token Flight - A comprehensive token airdrop and distribution tool for the Ergo blockchain
"""

__version__ = "0.5.0"

from .base_airdrop import BaseAirdrop
from .models import AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from .nft_airdrop import NFTAirdrop
from .bonus_service import BonusService
from .demurrage_service import DemurrageService
from .mrp_service import MRPService

__all__ = [
    "BaseAirdrop",
    "AirdropConfig",
    "TokenConfig",
    "WalletConfig",
    "RecipientAmount",
    "NFTAirdrop",
    "BonusService",
    "DemurrageService",
    "MRPService",
]
