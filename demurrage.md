# Demurrage Distribution System

This document outlines the demurrage distribution system, which distributes ERG tokens to miners based on their participation percentage across specified blocks.

## Overview

The demurrage distribution system calculates rewards for Ergo miners based on their participation in mining the blockchain. Additionally, it includes a 1% pool fee that goes to a specified pool address.

## Components

The system consists of three main scripts:

1. `demurrage_distribution.py` - Core calculation logic, can be used standalone
2. `demurrage_service.py` - Service layer for executing distributions
3. `demurrage_scheduler.py` - Scheduler for running distributions on a schedule or once

## Configuration

Configuration is done through environment variables, loaded from a `.env.demurrage` file by default:

```
WALLET_ADDRESS=your_wallet_address_here
WALLET_MNEMONIC=your_wallet_mnemonic_here
NODE_URL=http://your_node_url
EXPLORER_URL=https://api.ergoplatform.com
NETWORK_TYPE=MAINNET
POOL_FEE_PERCENTAGE=0.01
POOL_FEE_ADDRESS=9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt
SAFETY_MARGIN=0.003
```

## How It Works

1. The system identifies blocks since the last outgoing transaction from your wallet
2. It fetches miner participation data for those blocks from an API
3. It calculates the available balance after accounting for transaction fees and minimum box values
4. It allocates 1% of the available amount as a pool fee
5. The remaining 99% is distributed proportionally to miners based on their participation
6. Both the pool fee recipient and miners are added to the distribution list
7. The distribution is executed as a transaction with outputs to all recipients

## Fee Structure

- **Transaction Fee**: 0.001 ERG per transaction
- **Minimum Box Value**: 0.001 ERG per recipient (including miners and pool)
- **Pool Fee**: 1% of available amount after accounting for transaction costs
- **Safety Margin**: Small buffer (default 0.003 ERG) to prevent issues with rounding/calculations

## Running the System

### Standalone Distribution Calculation

To calculate a distribution and save it to a JSON file without executing:

```bash
python src/demurrage_distribution.py --output-dir=distributions
```

This will:
1. Calculate blocks since last transaction
2. Fetch miner data for those blocks
3. Calculate distribution amounts including the pool fee
4. Print detailed summary to console
5. Save distribution JSON to the specified output directory

### Distribution Execution

To actually execute a distribution (calculate and send transaction):

```bash
# First do a dry run to check the distribution
python src/demurrage_scheduler.py --run-once --dry-run --verbose

# If the output looks good, execute the actual transaction
python src/demurrage_scheduler.py --run-once --verbose
```

The `--run-once` flag tells the scheduler to run immediately and exit instead of running on a schedule.

### Scheduled Distribution

To run the distribution on a regular schedule:

```bash
python src/demurrage_scheduler.py --verbose
```

By default, this will run at midnight every day. You can customize the schedule with the `--schedule` argument.

## Distribution Example

Here's an example of what a distribution might look like:

```
=== DISTRIBUTION SUMMARY ===
Total blocks processed: 12
Total miners found: 34
Wallet balance: 1.25000000 ERG
Total fees required (TX + Min Boxes for 35 recipients): 0.03600000 ERG
Safety Margin: 0.00300000 ERG
Initial available amount (before pool fee): 1.21100000 ERG
Pool Fee (1%): 0.01211000 ERG
Amount distributed to miners: 1.19889000 ERG

Distribution breakdown:
Token: ERG
Address: 9i1Xzz5Axx... Amount: 0.00523542 ERG
Address: 9goLzR6gx4... Amount: 0.03245346 ERG
...
Address: 9iAFh6SzzS... Amount: 0.01211000 ERG (Pool Fee)

Total calculated distribution (Miners + Pool Fee): 1.21100000 ERG
Sum of amounts in generated list: 1.21100000 ERG
```

## File Output

The generated distribution JSON file will be saved to the specified output directory (default: `distributions/`) and will have a format similar to:

```json
{
  "distributions": [
    {
      "token_name": "ERG",
      "recipients": [
        {
          "address": "9i1Xzz5AxxRJUyt4asK7SsjrnoLgDnXupe2r4cvCPUrUZXEgrWm",
          "amount": 0.00523542
        },
        ...
        {
          "address": "9iAFh6SzzSbowjsJPaRQwJfx4Ts4EzXt78UVGLgGaYTdab8SiEt",
          "amount": 0.01211000
        }
      ]
    }
  ]
}
```

The pool fee recipient will be included as one of the recipients in this list.

## Command Line Arguments

### `demurrage_distribution.py`

- `--env-file` - Path to .env file (default: .env.demurrage)
- `--verbose` - Enable verbose logging
- `--output-dir` - Directory to save distribution files (default: distributions)
- `--min-block-height` - Override automatic block height detection with a specified value

### `demurrage_scheduler.py`

- `--run-once` - Run once and exit instead of scheduling
- `--dry-run` - Run in dry-run mode to preview distribution without executing
- `--verbose` - Enable verbose logging
- `--env-file` - Path to environment file (default: .env.demurrage)
- `--output-dir` - Directory to save distribution files (default: distributions)
- `--schedule` - Cron-style schedule (default: "0 0 * * *" - daily at midnight) 