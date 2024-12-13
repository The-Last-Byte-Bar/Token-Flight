# Ergo Token Airdrop Tool

A Python-based tool for airdropping tokens on the Ergo blockchain. Supports both single-token and multi-token airdrops.

## Features

- Single token airdrops
- Multi-token airdrops
- Support for both node wallet and mnemonic signing
- Flexible recipient sources (miners/CSV/JSON/direct address)
- Amount distribution by total amount or per-recipient amount
- Transaction preview with dry-run option
- Telegram notifications (optional)
- Rich console UI with progress indicators

## Prerequisites

- Python 3.8+
- Java 11+ (required for ErgoAppKit)
- Access to an Ergo node (local or remote)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-repo/ergonaut-airdrop.git
cd ergonaut-airdrop
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the root directory with your configuration:

```env
# Required: Node and Network Configuration
NODE_URL=http://your-node:9053
NETWORK_TYPE=MAINNET
EXPLORER_URL=https://api.ergoplatform.com/api/v1

# Option 1: Node Wallet Configuration
NODE_API_KEY=your_node_api_key
NODE_WALLET_ADDRESS=your_wallet_address

# Option 2: Mnemonic Configuration
WALLET_MNEMONIC=your mnemonic phrase
MNEMONIC_PASSWORD=optional mnemonic password

# Optional: Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Usage

### Single Token Airdrop

The basic airdrop supports distributing a single token or ERG to multiple recipients.

```bash
# Airdrop to miners
python src/airdrop.py TOKEN_NAME --total-amount 100 --source miners

# Airdrop to specific address
python src/airdrop.py TOKEN_NAME --amount-per-recipient 10 --address 9hxk8tPN8RsbbeCYChBKJmBjNSEqcNcJW68gHJBBYnmAfDfZW9g

# Dry run to preview transaction
python src/airdrop.py TOKEN_NAME --total-amount 100 --source miners --debug
```

### Multi-Token Airdrop

For distributing multiple tokens in a single transaction, use the multi-token airdrop with a JSON configuration file.

1. Create a distribution config file (e.g., `config.json`):

```json
{
    "distributions": [
        {
            "token_name": "LASTBYTE",
            "total_amount": 100
        },
        {
            "token_name": "ERG",
            "total_amount": 1
        },
        {
            "token_name": "SIGMANAUTS",
            "amount_per_recipient": 10
        }
    ]
}
```

2. Run the multi-token airdrop:

```bash
# Airdrop to miners
python src/multi_token_airdrop.py config.json --source miners

# Airdrop to specific address
python src/multi_token_airdrop.py config.json --source 9hxk8tPN8RsbbeCYChBKJmBjNSEqcNcJW68gHJBBYnmAfDfZW9g

# Dry run to preview transaction
python src/multi_token_airdrop.py config.json --source miners --dry-run
```

## Distribution Configuration

For each token distribution, you can specify either:
- `total_amount`: Total amount to distribute equally among recipients
- `amount_per_recipient`: Fixed amount for each recipient

The tool will automatically:
- Handle token decimals correctly
- Validate all addresses
- Check wallet balances
- Estimate and validate ERG requirements
- Preview the distribution before execution

## Recipient Sources

The tool supports multiple ways to specify recipients:

1. **Miners**: Uses the SigmaUSD mining pool API
```bash
--source miners
```

2. **Direct Address**: Single Ergo address
```bash
--source 9hxk8tPN8RsbbeCYChBKJmBjNSEqcNcJW68gHJBBYnmAfDfZW9g
```

3. **CSV File**: Custom recipient list with optional hashrates
```bash
--source path/to/recipients.csv
```

4. **JSON File**: Custom recipient list with optional metadata
```bash
--source path/to/recipients.json
```

## Security Considerations

1. Never share your mnemonic phrase or node API key
2. Always use `--dry-run` or `--debug` first to preview transactions
3. Keep your wallet backup secure
4. Ensure your node is fully synced before executing transactions

## Troubleshooting

Common issues and solutions:

1. **Wallet Locked Error**: 
   ```
   Ensure your node wallet is unlocked:
   curl -X POST "http://localhost:9053/wallet/unlock" -H "api_key: your_api_key" -H "Content-Type: application/json" -d "{\"pass\":\"your_wallet_password\"}"
   ```

2. **Insufficient ERG**:
   - Each output box requires minimum 0.001 ERG
   - Additional ERG needed for transaction fees
   - Check wallet balance includes network fees

3. **Invalid Token Name**:
   - Ensure token name matches exactly (case-sensitive)
   - Token must be listed in supported tokens list

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.