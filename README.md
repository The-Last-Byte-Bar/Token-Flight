# Token Flight 
## An Ergo Token Distribution Tool

A Python-based tool for performing token airdrops and distributions on the Ergo blockchain. Supports both ERG and token distributions with flexible configuration options.

## Features

- Support for both ERG and token distributions
- Multiple distribution methods:
  - Equal distribution (total amount)
  - Fixed per-recipient amount
  - Variable amounts per recipient
- Specialized Services:
  - NFT Distribution Service
  - Demurrage Service
  - Bonus Distribution Service
  - Miner Reward Program (MRP) Service
- Miner rewards distribution based on hashrate
- Pool and protocol fee support
- Automated block reward reduction
- Block height persistence
- Node wallet and mnemonic-based signing
- Rich CLI interface with space theme
- Comprehensive error handling and logging
- Support for reading recipients from CSV files
- Transaction batching for large airdrops
- Real-time confirmation prompts
- Explorer integration

## Prerequisites

- Python 3.10 or higher
- Java 11 or higher (required for ErgoAppKit)
- Access to an Ergo node (local or remote)
- Either:
  - Node wallet with API access, or
  - Wallet mnemonic phrase

## Installation

### Option 1: Install from PyPI
```bash
pip install token-flight
```

### Option 2: Install from source
```bash
git clone https://github.com/ergonaut-airdrop/token-flight.git
cd token-flight
pip install -e .
```

## Configuration

### For Standard Airdrops
Create a `.env` file with your configuration:
```env
NODE_URL=http://your.node:9053
NETWORK_TYPE=mainnet
EXPLORER_URL=https://api.ergoplatform.com/api/v1
NODE_API_KEY=your_node_api_key        # Required for node signing
WALLET_ADDRESS=your_wallet_address    # Required for node signing
WALLET_MNEMONIC=your_mnemonic_phrase  # Required for mnemonic signing
```

### For MRP Service
Copy `.env.mrp.sample` to `.env.mrp` and configure:
```env
# Node Configuration
NODE_URL=http://localhost:9053/
NODE_API_KEY=your_node_api_key_here
NETWORK_TYPE=MAINNET
EXPLORER_URL=https://api.ergoplatform.com/api/v1
WALLET_ADDRESS=your_wallet_address_here

# Block Processing
STARTING_BLOCK_HEIGHT=1446576

# Token Configuration
RIGHTS_TOKEN_ID=your_token_id_here
EMISSION_TOKEN_NAME=YourToken
BLOCK_REWARD=10000.0

# Fee Configuration
POOL_FEE_PERCENT=1.0
PROTOCOL_FEE_PERCENT=1.0
POOL_ADDRESS=pool_address_here
PROTOCOL_ADDRESS=protocol_address_here

# Emission Reduction
REDUCTION_BLOCKS=500
REDUCTION_PERCENT=10.0

# Output
OUTPUT_FILE=MRP.json
```

2. Configure distribution file (e.g., `config.json`):

```json
{
    "distributions": [
        {
            "token_name": "TokenName",
            "total_amount": 1000000,    // Or use amount_per_recipient
            "decimals": 0               // Optional, defaults to 0
        }
    ]
}
```

For variable amounts per recipient:
```json
{
    "distributions": [
        {
            "token_name": "ERGO",
            "recipients": [
                {"address": "9f...", "amount": 1.5},
                {"address": "9h...", "amount": 2.3}
            ]
        }
    ]
}
```

## Usage

### Basic Usage

```bash
# Start MRP Service
python mrp_service.py

# For standard airdrops
python airdrop.py config.json --use-node  # For node wallet signing
# or
python airdrop.py config.json --use-seed  # For mnemonic signing
```

### Additional Options

```bash
# Filter miners by minimum hashrate
python airdrop.py config.json --use-node --min-hashrate 100000

# Use CSV file for recipients
python airdrop.py config.json --use-node --source recipients.csv

# Debug mode (no transaction submission)
python airdrop.py config.json --use-node --debug

# Headless mode (no prompts)
python airdrop.py config.json --use-node --headless
```

## CSV Format

When using a CSV file for recipients, use the following format:

```csv
address,amount,hashrate
9f...,1.5,100000
9h...,2.3,200000
```

## Emission Reduction

Block rewards automatically reduce based on configuration:
- REDUCTION_BLOCKS: Number of blocks between reductions
- REDUCTION_PERCENT: Percentage to reduce by each cycle

Example with 500 blocks and 10% reduction:
- Height 0-499: 10000
- Height 500-999: 9000
- Height 1000-1499: 8100

## Security Considerations

- Never share your mnemonic phrase or node API key
- Always use the `--debug` flag first to verify distribution
- Keep your node wallet locked when not in use
- Verify recipient addresses carefully
- Monitor your wallet balance
- Back up your wallet before large distributions

## Troubleshooting

Common issues and solutions:

1. "Wallet appears to be locked":
   - Ensure your node wallet is unlocked
   - Verify your API key has proper permissions

2. "Insufficient balance":
   - Check wallet balance includes ERG for box minimums
   - Account for transaction fees
   - Verify token balances

3. "Invalid mnemonic":
   - Double-check mnemonic phrase
   - Ensure no extra spaces or characters

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support:
- Open an issue on GitHub
- Join our Discord server
- Check the documentation

## Specialized Services

### NFT Service
The NFT Service enables automated distribution of NFTs across multiple recipients:
```bash
# Configure NFT service
cp .env.sample .env.nft
# Edit .env.nft with your configuration

# Run NFT distribution
python src/nft_service.py --collection "YourCollection" --recipients recipients.json
```

### Demurrage Service
The Demurrage Service handles block height-based token distribution:
```bash
# Configure Demurrage service
cp .env.sample .env.demurrage
# Edit .env.demurrage with your configuration

# Run Demurrage service
docker-compose -f docker/demurrage/docker-compose.demurrage.yaml up
```

### Bonus Service
The Bonus Service manages additional reward distributions:
```bash
# Configure Bonus service
cp .env.sample .env.bonus
# Edit .env.bonus with your configuration

# Run Bonus service
docker-compose -f docker/bonus/docker-compose.bonus.yaml up
```

### MRP (Miner Reward Program) Service
The MRP Service handles mining reward distributions:
```bash
# Configure MRP service
cp .env.sample .env.mrp
# Edit .env.mrp with your configuration

# Run MRP service
python src/mrp_service.py
```

Each service can be configured independently through their respective environment files and can be run either directly or through Docker containers. Refer to the service-specific documentation in the `docs/` directory for detailed configuration options and usage examples.

## Usage with Fleet SDK

```python
from token_flight import Airdrop, TokenConfig
from fleet_sdk.core import FleetSDK

# Initialize Fleet SDK
fleet = FleetSDK()

# Configure your airdrop
config = TokenConfig(
    token_id="your_token_id",
    total_amount=1000000,
    decimals=0
)

# Create airdrop instance
airdrop = Airdrop(config)

# Add recipients
airdrop.add_recipient("9f...", 100)
airdrop.add_recipient("9h...", 200)

# Get unsigned transaction
unsigned_tx = airdrop.build_transaction()

# Sign with Fleet SDK
signed_tx = fleet.sign_transaction(unsigned_tx)

# Submit transaction
tx_id = fleet.submit_transaction(signed_tx)
print(f"Transaction submitted: {tx_id}")
```