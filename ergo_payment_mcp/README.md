# Ergo Payment MCP Server

A Model Context Protocol (MCP) server for executing payments and distributions on the Ergo blockchain.

## Features

- **Single Payments**: Send ERG or tokens to individual recipients
- **Bonus Payments**: Distribute bonuses based on configuration files
- **Demurrage Payments**: Execute demurrage payment distributions
- **Bulk Payments**: Send payments to multiple recipients at once
- **Blockchain Analysis**: Tools for examining addresses, transactions, and the network
- **Wallet Management**: Tools for wallet configuration and management

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/ergonaut-airdrop.git
   cd ergonaut-airdrop
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables (see `.env.sample` for examples):
   ```
   cp sample.env .env
   # Edit .env with your wallet details and configuration
   ```

## Usage

### Running the MCP Server

Run the server directly:

```bash
python -m ergo_payment_mcp.run
```

Or using the MCP CLI:

```bash
# Development mode with inspector
mcp dev ergo_payment_mcp/run.py

# Install in Claude Desktop
mcp install ergo_payment_mcp/run.py --name "Ergo Payment Server"
```

### Environment Variables

Required environment variables:

- `NODE_URL`: URL of your Ergo node
- `NETWORK_TYPE`: Network type (`mainnet` or `testnet`)
- `EXPLORER_URL`: URL of the Ergo explorer
- `WALLET_MNEMONIC`: Your wallet mnemonic (15 words)
- `WALLET_ADDRESS`: Your wallet address for receiving/sending

Optional environment variables:

- `MNEMONIC_PASSWORD`: Password for your mnemonic (if applicable)
- `LOG_LEVEL`: Logging level (default: INFO)

## MCP Resources

The server exposes the following resources:

- `config://wallet`: Current wallet configuration (non-sensitive)
- `config://bonus`: Bonus payment configuration
- `config://{config_name}`: Any configuration file by name
- `balance://wallet`: Current wallet balance
- `payments://templates`: Available payment templates
- `payments://bonus/schema`: Schema for bonus payment configuration
- `payments://demurrage/schema`: Schema for demurrage payment configuration
- `payments://sample/bonus`: Sample bonus payment configuration
- `payments://sample/demurrage`: Sample demurrage payment configuration
- `payments://history`: Payment history

## MCP Tools

The server provides the following tools:

### Payment Tools

- `send_payment`: Send a payment to a single recipient
- `send_bonus_payment`: Send bonus payments based on configuration
- `send_demurrage_payment`: Execute demurrage payment distribution
- `send_bulk_payments`: Send payments to multiple recipients
- `check_address_validity`: Check if an Ergo address is valid
- `create_config_file`: Create a new configuration file

### Blockchain Tools

- `get_address_info`: Get information about an Ergo address
- `get_transaction_info`: Get information about a transaction
- `get_network_status`: Get current Ergo network status
- `search_token`: Search for tokens on the Ergo blockchain

### Wallet Tools

- `estimate_transaction_fee`: Estimate transaction fee for a payment
- `create_wallet_config`: Create wallet configuration for payment operations
- `create_transaction_manifest`: Create a transaction manifest for bulk payments
- `generate_wallet_backup_instructions`: Generate wallet backup instructions

## MCP Prompts

The server offers the following interaction prompts:

- `single_payment_prompt`: Prompt for sending a single payment
- `bonus_payment_prompt`: Prompt for sending bonus payments
- `demurrage_payment_prompt`: Prompt for executing demurrage payments
- `bulk_payment_prompt`: Prompt for sending bulk payments
- `create_config_prompt`: Prompt for creating a payment configuration
- `wallet_setup_prompt`: Prompt for setting up wallet configuration

## Configuration Files

### Bonus Payment Configuration

Sample format:

```json
{
  "token_id": "0cd8c9f416e5b1ca9f986a7f10a84191dfb85941619e49e53c0dc30ebf83324b",
  "decimal_places": 0,
  "recipients": [
    {
      "address": "9fLf54PVmRiy7DTNEsNTK2hWwTaB9rrJkgHYgjy8tJeSkQJPx6F",
      "amount": 10
    },
    {
      "address": "9gYxoYyDDo8r8yvWE8QTQCxHqVvcuL4me7nU8NbUXnwLrGgL3bK",
      "amount": 15
    }
  ]
}
```

### Demurrage Payment Configuration

Sample format:

```json
{
  "collector_address": "9fE5o7913CKKe6wvNgM11vULjTuKiopPcvCaj7t2zcJWXM2gcLu",
  "blocks_per_distribution": 10,
  "distribution_percentage": 90,
  "recipient_addresses": [
    "9fLf54PVmRiy7DTNEsNTK2hWwTaB9rrJkgHYgjy8tJeSkQJPx6F",
    "9gYxoYyDDo8r8yvWE8QTQCxHqVvcuL4me7nU8NbUXnwLrGgL3bK"
  ]
}
```

## Security Considerations

- **Wallet Mnemonics**: Always store your wallet mnemonic securely as environment variables or in a secure storage.
- **Approval Process**: Always verify transaction details before confirming payments.
- **Authentication**: This MCP server doesn't provide authentication by default. Use it in a secure environment.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 