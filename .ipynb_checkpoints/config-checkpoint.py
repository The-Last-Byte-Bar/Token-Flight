# config.py
from dataclasses import dataclass
from typing import List, Dict, Any
import json

@dataclass
class TokenDistribution:
    type: str
    tokensPerRound: int  # Match JSON naming
    blocksBetweenDispense: int  # Match JSON naming

@dataclass
class TokenConfig:
    name: str
    description: str
    totalAmount: int  # Match JSON naming
    decimals: int
    distribution: TokenDistribution

@dataclass
class NodeConfig:
    api_url: str
    api_key: str
    explorer_url: str
    network_type: str
    node_address: str

@dataclass
class DistributionConfig:
    maxDuration: int
    defaultBlocksBetweenDispense: int

@dataclass
class Config:
    node: NodeConfig
    minter_address: str
    recipient_wallets: List[str]
    tokens: List[TokenConfig]
    distribution: DistributionConfig

def load_config(file_path: str) -> Config:
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    return Config(
        node=NodeConfig(
            api_url=data['node']['nodeApi']['apiUrl'],
            api_key=data['node']['nodeApi']['apiKey'],
            explorer_url=data['node']['explorer_url'],
            network_type=data['node']['networkType'],
            node_address=data['node']['nodeAddress']
        ),
        minter_address=data['parameters']['minterAddr'],
        recipient_wallets=data['parameters']['recipientWallets'],
        tokens=[TokenConfig(
            name=token['name'],
            description=token['description'],
            totalAmount=token['totalAmount'],
            decimals=token['decimals'],
            distribution=TokenDistribution(
                type=token['distribution']['type'],
                tokensPerRound=token['distribution']['tokensPerRound'],
                blocksBetweenDispense=token['distribution']['blocksBetweenDispense']
            )
        ) for token in data['tokens']],
        distribution=DistributionConfig(
            maxDuration=data['distribution']['maxDuration'],
            defaultBlocksBetweenDispense=data['distribution']['defaultBlocksBetweenDispense']
        )
    )

def validate_config(config: Config) -> None:
    """Validate configuration values"""
    if not all([
        config.node.api_url,
        config.node.api_key,
        config.node.explorer_url,
        config.node.network_type,
        config.node.node_address,
        config.minter_address,
        config.recipient_wallets
    ]):
        raise ValueError("All required node and parameter fields must be filled")
    
    if not isinstance(config.recipient_wallets, list) or len(config.recipient_wallets) == 0:
        raise ValueError("recipient_wallets must be a non-empty list")
        
    if not config.tokens or len(config.tokens) == 0:
        raise ValueError("At least one token configuration must be provided")
        
    for token in config.tokens:
        if token.totalAmount <= 0:
            raise ValueError(f"Token {token.name} amount must be positive")
        if token.distribution.tokensPerRound <= 0:
            raise ValueError(f"Token {token.name} tokensPerRound must be positive")
        if token.distribution.blocksBetweenDispense <= 0:
            raise ValueError(f"Token {token.name} blocksBetweenDispense must be positive")
        
    if config.distribution.maxDuration <= 0:
        raise ValueError("maxDuration must be positive")
    if config.distribution.defaultBlocksBetweenDispense <= 0:
        raise ValueError("defaultBlocksBetweenDispense must be positive")