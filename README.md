# Token Flight AIRDROP Tool

A Python-based tool for performing token airdrops on the Ergo blockchain. Supports both ERG and token distributions with flexible configuration options.

## Features

- Support for both ERG and token distributions
- Multiple distribution methods:
  - Equal distribution (total amount)
  - Fixed per-recipient amount
  - Variable amounts per recipient
- Miner rewards distribution based on hashrate
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

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ergo-token-airdrop.git
cd ergo-token-airdrop
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file with your configuration:
```env
NODE_URL=http://your.node:9053
NETWORK_TYPE=mainnet
EXPLORER_URL=https://api.ergoplatform.com/api/v1
NODE_API_KEY=your_node_api_key        # Required for node signing
WALLET_ADDRESS=your_wallet_address    # Required for node signing
WALLET_MNEMONIC=your_mnemonic_phrase  # Required for mnemonic signing
```

2. Create a distribution configuration file (e.g., `config.json`):

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

## Acknowledgments

- Ergo Platform team
- ErgoAppKit developers
- Community contributors

## Support

For support:
- Open an issue on GitHub
- Join our Discord server
- Check the documentation
