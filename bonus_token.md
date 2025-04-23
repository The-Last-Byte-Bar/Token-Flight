# Bonus Token Distribution System

This document outlines the bonus token distribution system, which allows for the distribution of tokens to specified recipients based on a configuration file.

## Overview

The bonus token distribution system is designed to distribute various types of tokens to a list of recipients. Unlike the demurrage system which calculates distributions based on mining participation, the bonus system uses a predefined configuration file specifying either the total token amount, amount per recipient, or individual recipient amounts.

## Components

The system consists of three main scripts:

1. `bonus_service.py` - Core service for executing token distributions
2. `bonus_scheduler.py` - Scheduler for running distributions on a schedule or once
3. `base_airdrop.py` - Base implementation handling the actual transaction building and submission

## Configuration

### Environment Variables

Configuration is done through environment variables, loaded from a `.env.bonus` file by default:

```
NODE_URL=http://your_node_url
EXPLORER_URL=https://api.ergoplatform.com
NETWORK_TYPE=MAINNET
WALLET_MNEMONIC=your_wallet_mnemonic_here
MNEMONIC_PASSWORD=optional_mnemonic_password
BONUS_CRON=0 13 * * 1  # Runs every Monday at 8am EST (optional, for scheduled runs)
```

### Distribution Configuration File

The distribution configuration is defined in a JSON file with the following structure:

```json
{
  "distributions": [
    {
      "token_name": "TOKENNAME",
      "token_id": "token_id_hash_here",  // Optional, can be auto-detected by name
      "decimals": 0,  // Optional, defaults to 0
      
      // Option 1: Specify total amount (will be divided equally)
      "total_amount": 1000,
      
      // Option 2: Specify amount per recipient
      "amount_per_recipient": 100,
      
      // Option 3: Specify individual recipient amounts
      "recipients": [
        { 
          "address": "recipient_address_1", 
          "amount": 100 
        },
        { 
          "address": "recipient_address_2", 
          "amount": 200 
        }
      ]
    }
  ]
}
```

You must choose one of the three options for each token distribution:
1. **Total amount**: The system will divide the total equally among all recipients
2. **Amount per recipient**: Each recipient will receive this exact amount
3. **Individual recipient amounts**: Specify different amounts for each recipient

## How It Works

1. The system loads the distribution configuration from the specified JSON file
2. For each token distribution in the configuration:
   - It validates the configuration parameters
   - It prepares recipient lists and amounts based on the specified distribution type
3. It authenticates with the node using the wallet mnemonic
4. It builds and submits a transaction with outputs to all recipients
5. It logs the transaction details and returns the transaction ID if successful

## Running the System

### One-time Distribution

To execute a one-time distribution:

```bash
# First, ensure your .env.bonus and config JSON are set up
cp .env.sample .env.bonus
# Edit .env.bonus with your configuration
# Create your distribution config JSON file

# Execute the distribution
python src/bonus_service.py path/to/your/config.json --run-once
```

### Scheduled Distribution

To run the distribution on a schedule:

```bash
# With Docker:
docker-compose -f docker/bonus/docker-compose.bonus.yaml up

# Without Docker:
python src/bonus_scheduler.py path/to/your/config.json
```

By default, this will use the schedule specified in the `BONUS_CRON` environment variable or run every minute if not specified.

## Distribution Examples

### Simple Equal Distribution

This example distributes 1000 tokens equally among all recipients:

```json
{
  "distributions": [
    {
      "token_name": "SIGMANAUTSMININGPOOL",
      "total_amount": 1000
    }
  ]
}
```

The recipients will be determined from another source (typically from a recipient manager or API).

### Fixed Amount Per Recipient

This example gives exactly 100 tokens to each recipient:

```json
{
  "distributions": [
    {
      "token_name": "SIGMANAUTSMININGPOOL",
      "amount_per_recipient": 100
    }
  ]
}
```

### Custom Amount Per Recipient

This example specifies different amounts for each recipient:

```json
{
  "distributions": [
    {
      "token_name": "SIGMANAUTSMININGPOOL",
      "recipients": [
        { "address": "9et33SeVYvt2aSzEXQbGhmYZgh44Chvs3pjCJCJZMCZgNcQVxRW", "amount": 150 },
        { "address": "9iMhhRJwCPSEFQaEq2iPdU5K8DvGzYA2refQYM48EPfAs1K6peg", "amount": 250 },
        { "address": "9fyRcVGKaGmuJk5T1E6hJkqXTGCJ4rhgyWqaNNJgkCC8SDDfr5L", "amount": 375 }
      ]
    }
  ]
}
```

### Multiple Token Distribution

You can distribute multiple tokens in a single transaction:

```json
{
  "distributions": [
    {
      "token_name": "SIGMANAUTSMININGPOOL",
      "total_amount": 1000
    },
    {
      "token_name": "ERDOGE",
      "token_id": "d71693c49a84fbbecd4908c94813b46514b18b67a99952dc1e6e4791556de413",
      "decimals": 2,
      "amount_per_recipient": 100
    }
  ]
}
```

## Command Line Arguments

### `bonus_service.py`

- `config_file` - Path to the distribution configuration file (required)
- `--run-once` - Run once and exit (no scheduling)
- `--debug` - Enable debug mode
- `--env-file` - Path to environment file (default: .env.bonus)

### `bonus_scheduler.py`

- `config_file` - Path to the distribution configuration file (required)
- `--run-once` - Run once and exit (no scheduling)
- `--debug` - Enable debug mode
- `--env-file` - Path to environment file (default: /app/.env.bonus)

## Docker Deployment

The bonus distribution service can be deployed using Docker:

```bash
# Configure your environment
cp .env.sample .env.bonus
# Edit .env.bonus with your configuration

# Create your distribution config
cp test_bonus_config.json your_bonus_config.json
# Edit your_bonus_config.json with your distribution settings

# Start the service
docker-compose -f docker/bonus/docker-compose.bonus.yaml up
```

The Docker configuration will mount your config file and environment variables into the container. 