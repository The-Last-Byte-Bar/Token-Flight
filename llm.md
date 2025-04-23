# Token Flight Tool Guide for LLMs

## Overview
This guide explains how to use the Token Flight tool for managing Ergo blockchain transactions and airdrops. The tool provides functionality for sending tokens and ERG to multiple addresses efficiently.

## Transaction Analysis

Before sending transactions, always analyze the source address:

1. Check address balance:
```python
balance = get_address_balance(address="SOURCE_ADDRESS")
```

2. Verify transaction history:
```python
history = get_transaction_history(
    address="SOURCE_ADDRESS",
    limit=10  # Adjust as needed
)
```

## Airdrop Process

### 1. Pre-flight Checks

Before initiating an airdrop:

- Verify source wallet has sufficient balance
- Confirm target addresses are valid Ergo addresses
- Calculate total token amount needed
- Ensure enough ERG for transaction fees

### 2. Transaction Structure

Format airdrop transactions as:

```python
airdrop_tx = {
    "sourceAddress": "SOURCE_WALLET_ADDRESS",
    "recipients": [
        {
            "address": "TARGET_ADDRESS_1",
            "value": TOKEN_AMOUNT_1,
            "tokenId": "TOKEN_ID"  # Optional for token transfers
        },
        # Add more recipients as needed
    ]
}
```

### 3. Transaction Validation

Before submitting transactions:

1. Verify total amount doesn't exceed balance
2. Check minimum ERG requirements
3. Validate all recipient addresses
4. Confirm token IDs exist (for token transfers)

### 4. Monitoring Transactions

After sending transactions:

1. Get transaction status:
```python
tx_info = analyze_transaction(tx_id="TRANSACTION_ID")
```

2. Monitor network status:
```python
network_status = get_network_status()
```

## Best Practices

1. **Batching**
   - Group transactions into reasonable batch sizes
   - Consider network congestion
   - Monitor mempool status

2. **Error Handling**
   - Implement retry logic for failed transactions
   - Keep transaction logs
   - Monitor network conditions

3. **Security**
   - Always verify addresses before sending
   - Double-check amounts
   - Keep private keys secure

## Common Operations

### Send ERG
```python
# Single ERG transfer
tx = {
    "sourceAddress": "SOURCE_ADDRESS",
    "recipients": [{
        "address": "TARGET_ADDRESS",
        "value": ERG_AMOUNT
    }]
}
```

### Send Tokens
```python
# Token transfer
tx = {
    "sourceAddress": "SOURCE_ADDRESS",
    "recipients": [{
        "address": "TARGET_ADDRESS",
        "value": TOKEN_AMOUNT,
        "tokenId": "TOKEN_ID"
    }]
}
```

### Batch Operations
```python
# Batch transfer
tx = {
    "sourceAddress": "SOURCE_ADDRESS",
    "recipients": [
        {
            "address": "TARGET_1",
            "value": AMOUNT_1,
            "tokenId": "TOKEN_ID"
        },
        {
            "address": "TARGET_2",
            "value": AMOUNT_2,
            "tokenId": "TOKEN_ID"
        }
        # Add more recipients as needed
    ]
}
```

## Troubleshooting

1. **Transaction Failed**
   - Check network status
   - Verify sufficient ERG for fees
   - Confirm recipient addresses
   - Review transaction structure

2. **Network Issues**
   - Monitor network hashrate
   - Check current difficulty
   - Verify node connection

3. **Balance Issues**
   - Confirm source address balance
   - Check for pending transactions
   - Verify token availability

## Rate Limiting and Network Considerations

1. **Transaction Spacing**
   - Allow time between batches
   - Monitor mempool congestion
   - Adjust batch sizes based on network load

2. **Network Monitoring**
```python
# Check network status
network_info = get_network_status()
mempool_info = get_mempool_info()
```

3. **Performance Optimization**
   - Pre-validate addresses
   - Cache token information
   - Monitor transaction confirmation times

Remember to always test with small amounts first and implement proper error handling for all operations.

## Integrating with Fleet SDK

### 1. Token Flight to Fleet SDK Bridge

The token flight tool generates transaction data that needs to be converted into Fleet SDK compatible format. Here's how to bridge them:

```typescript
import { 
    TransactionBuilder, 
    OutputBuilder,
    ErgoAddress,
    Box,
    TokenAmount
} from '@fleet-sdk/core';

// Interface for token flight output
interface TokenFlightOutput {
    generate_fleet_transaction_data: {
        inputs: Array<{
            boxId: string;
            value: bigint;
            assets?: Array<{
                tokenId: string;
                amount: bigint;
            }>;
        }>;
        outputs: Array<{
            address: string;
            value: bigint;
            assets?: Array<{
                tokenId: string;
                amount: bigint;
            }>;
        }>;
    };
}

// Convert token flight output to Fleet SDK format
function convertToFleetFormat(tokenFlightOutput: TokenFlightOutput) {
    const { inputs, outputs } = tokenFlightOutput.generate_fleet_transaction_data;
    
    // Convert inputs to Fleet SDK Box format
    const fleetInputs = inputs.map(input => ({
        boxId: input.boxId,
        value: input.value.toString(),
        assets: input.assets?.map(asset => ({
            tokenId: asset.tokenId,
            amount: asset.amount.toString()
        })) || []
    }));

    // Convert outputs to Fleet SDK OutputBuilder format
    const fleetOutputs = outputs.map(output => {
        const outputBuilder = new OutputBuilder(
            output.value.toString(),
            ErgoAddress.fromBase58(output.address)
        );

        if (output.assets && output.assets.length > 0) {
            const tokens: TokenAmount[] = output.assets.map(asset => ({
                tokenId: asset.tokenId,
                amount: asset.amount.toString()
            }));
            outputBuilder.addTokens(tokens);
        }

        return outputBuilder;
    });

    return { fleetInputs, fleetOutputs };
}
```

### 2. Using the Bridge

Here's how to use token flight with Fleet SDK:

```typescript
async function processTokenFlightAirdrop(recipientList: any[]) {
    // 1. Generate transaction data using token flight
    const tokenFlightTx = await generate_fleet_transaction_data({
        recipients: recipientList,
        // other token flight options...
    });

    // 2. Convert to Fleet SDK format
    const { fleetInputs, fleetOutputs } = convertToFleetFormat(tokenFlightTx);

    // 3. Create Fleet SDK transaction
    const txBuilder = new TransactionBuilder(fleetInputs)
        .from(fleetInputs)
        .to(fleetOutputs);

    // 4. Build unsigned transaction
    const unsignedTx = txBuilder.build();
    return unsignedTx;
}
```

### 3. Integration Example

Complete example showing how to use both tools together:

```typescript
async function executeAirdrop(config: {
    tokenId: string,
    recipients: Array<{ address: string, amount: bigint }>,
    sourceAddress: string
}) {
    try {
        // 1. Use token flight to generate optimal transaction structure
        const tokenFlightData = await generate_fleet_transaction_data({
            sourceAddress: config.sourceAddress,
            recipients: config.recipients,
            tokenId: config.tokenId
        });

        // 2. Convert and validate with Fleet SDK
        const { fleetInputs, fleetOutputs } = convertToFleetFormat(tokenFlightData);
        
        // 3. Create and build transaction with Fleet SDK
        const txBuilder = new TransactionBuilder(fleetInputs);
        fleetOutputs.forEach(output => txBuilder.to(output));
        
        // 4. Add any Fleet SDK specific optimizations
        txBuilder.configure(builder => {
            builder.feeAmount(1000000n); // Example fee
            builder.sendChangeTo(config.sourceAddress);
        });

        // 5. Build final transaction
        const unsignedTx = txBuilder.build();
        return unsignedTx;
    } catch (error) {
        console.error("Error in airdrop execution:", error);
        throw error;
    }
}
```

### 4. Handling Complex Scenarios

For more complex token distributions:

```typescript
async function handleComplexAirdrop(config: {
    distributions: Array<{
        tokenId: string,
        recipients: Array<{ address: string, amount: bigint }>
    }>,
    sourceAddress: string
}) {
    // 1. Generate separate token flight data for each distribution
    const tokenFlightPromises = config.distributions.map(dist => 
        generate_fleet_transaction_data({
            sourceAddress: config.sourceAddress,
            recipients: dist.recipients,
            tokenId: dist.tokenId
        })
    );

    const tokenFlightResults = await Promise.all(tokenFlightPromises);

    // 2. Merge token flight results
    const mergedInputs = mergeTokenFlightInputs(tokenFlightResults);
    const mergedOutputs = mergeTokenFlightOutputs(tokenFlightResults);

    // 3. Convert to Fleet SDK format
    const { fleetInputs, fleetOutputs } = convertToFleetFormat({
        generate_fleet_transaction_data: {
            inputs: mergedInputs,
            outputs: mergedOutputs
        }
    });

    // 4. Build with Fleet SDK
    const txBuilder = new TransactionBuilder(fleetInputs)
        .from(fleetInputs)
        .to(fleetOutputs);

    return txBuilder.build();
}
```

### 5. Best Practices for Integration

1. **Data Validation**
   - Validate token flight output before conversion
   - Verify Fleet SDK input requirements are met
   - Check for transaction size limits
   - Validate token amounts and ERG values

2. **Error Handling**
   - Handle conversion errors gracefully
   - Implement proper error reporting
   - Add validation checks at each step
   - Monitor transaction status

3. **Performance**
   - Batch similar transactions
   - Optimize input selection
   - Cache common operations
   - Use appropriate Fleet SDK configurations

4. **Security**
   - Validate all addresses
   - Check transaction amounts
   - Verify token IDs
   - Implement proper signing procedures

Remember to test the integration thoroughly with small amounts before processing large airdrops. 