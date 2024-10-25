# Token Vesting and Distribution System

This project is a token vesting and distribution system built on the Ergo blockchain. It allows you to mint a custom token, set up a vesting schedule, and automate the distribution of tokens to a list of recipient wallets over a specified number of blocks.

## Features

- Customizable token parameters (name, description, total supply, decimals)
- Configurable vesting schedule (tokens per round, blocks between each distribution)
- Secure token storage in a proxy contract
- Automated token distribution to multiple recipient wallets
- Detailed logging for tracking and auditing

## Prerequisites

- Python 3.x
- ergo-python-appkit
- Access to an Ergo node (testnet or mainnet)

## Configuration

The system is configured using a JSON file. Here's an example configuration (`testnet.json`):

```json
{
  "node": {
    "nodeApi": {
      "apiUrl": "http://37.27.198.175:9052/",
      "apiKey": "hellodev"
    },
    "explorer_url": "https://api-testnet.ergoplatform.com/",
    "networkType": "TESTNET",
    "nodeAddress": "3WyZiupQXRBQKrUz7UwKTQTc6kxz1FkzM7zUazKDTQo1xbpJdmoe"
  },
  "parameters": {
    "minterAddr": "3WyZiupQXRBQKrUz7UwKTQTc6kxz1FkzM7zUazKDTQo1xbpJdmoe",
    "recipientWallets": [
      "3WyZiupQXRBQKrUz7UwKTQTc6kxz1FkzM7zUazKDTQo1xbpJdmoe",
      "3WzG7rdHxK8inns4Jjj36VPZrBjZ3vvFCNGQXGqN6XGfXJkGSXvr",
      ...
    ]
  },
  "token": {
    "name": "MyToken",
    "description": "My custom token",
    "totalAmount": 500000000000,
    "decimals": 5
  },
  "distribution": {
    "tokensPerRound": 1000000000,
    "blocksBetweenDispense": 1
  }
}
```

## Usage

1. Clone the repository and navigate to the project directory.

2. Install the required dependencies:
   ```
   pip install ergo-python-appkit
   ```

3. Configure the system by modifying the JSON configuration file.

4. Run the `minting_setup.py` script with the path to your configuration file:
   ```
   python minting_setup.py testnet.json
   ```

   This will create the proxy contract, mint the tokens, and save the necessary information for the distribution bot.

5. Run the distribution bot script:
   ```
   python distribution_bot.py
   ```

   The bot will continuously monitor the blockchain and distribute tokens to the recipient wallets according to the configured schedule.

## Logging

Detailed logs are generated for each step of the process and saved in the `logs` directory. The logs include information about the configuration, minting process, token distribution, and any errors encountered.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
