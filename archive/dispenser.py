from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, Constants
import time
import math

# Initialize ErgoAppKit
node_url = "http://37.27.198.175:9053/"
explorer_url = "https://api.ergoplatform.com/"
appKit = ErgoAppKit(node_url, "mainnet", explorer_url, 'hashcream')

# Define addresses
minter_address = "9ebLdLKX7k6gAyruUPeqrT1jqKtscvFiW11EFmX5tcAvmwfZSsH"

# List of recipient wallets
recipient_wallets = [
    '9hDJ91Rx5TZf4njCG6AAcsf4GEWyQxrh5ioZ95mXQk8QtCNv8Js',
    '9feNRbYuVz2nQy1V8t2z5saYnWKwmGJ2nYgcMdXBjqYXqHMeWnv',
    '9gwFTap8YaQEzsMAXdt4pa1BjAsR9gcijMMuxTRrAf4vgMhSnXY',
    '9hYeUWUG2dAM6sZb9vr5qgF1gACEGQPLN9cbXjxERmJS89Tbadc',
    '9fYvQMsMN3NNaw33cAFnRdyHy1DpxtxfADvGqUV3ocLptw4HpcP',
    '9fuHCh7cvbWxMXdhNpjxAFVGCtP4W3yP6v7vVLPFYB4PR3NpyAL',
    '9ggrhWJVjTHHUrK8qJThWi1yBscmETnT3nxTwVDfQQPCASaZmxt',
    '9fyDqkVk3iDXPNcquyLBehEtiZiqdKb27PnugemJEpGYbTJM7tN',
    '9enXTiL3i9CKWKCcE3fby2hSaeoWEWV28evc1j1SK9yKRDy9cVN',
    '9eoPRhRmJQ71TPSkk2eUmMXYpxUVvZvFQo5uB9qjPBM4e3hC82J',
    '9i8wsL9HYe4wRtuxXtnvki31uGJd6avKoQ79BXbz2sHWNZSKz8K',
    '9fjQi1JrgFZ9QBKGbE7EYDwUwAvGUk95Wa92kV2D4EnggNcnMzN',
    '9fvDaBsLKmzP67Cp2i2bmhM1359HhJCrej8y5EGoUcmXDrBqxbW',
    '9fHLdYBz5fPdDfMkGMfAsuj6EfXCpmM4GkamT23xeT3hzdHbNJx',
    '9gNEKbpPSNfgWkhxsMF4Z9L7uNiXFfsEX4XTVF5XK4kwpQBRsEQ',
    '9fLytFFzTYALknc2AZ2dRKeg8sLZwe4LX5qAB3FwDysMEeRTHkV',
    ]

import binascii

def create_distribution_contract(unlock_height, recipient_wallets):
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipient_wallets]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    contract_script = f"""
    {{
        val unlockHeight = {unlock_height}L
        val recipientTrees = Coll({recipient_trees_str})
        
        sigmaProp(HEIGHT >= unlockHeight && {{
            val validOutputs = OUTPUTS.filter({{(output: Box) =>
                output.tokens.size == 1 && output.tokens(0)._1 == SELF.tokens(0)._1
            }})
            validOutputs.forall({{(output: Box) =>
                recipientTrees.exists({{(tree: Coll[Byte]) => 
                    output.propositionBytes == tree
                }})
            }})
        }})
    }}
    """
    return appKit.compileErgoScript(contract_script)

def create_proxy_contract(recipients):
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    contract_script = f"""
    {{
        val recipientTrees = Coll({recipient_trees_str})
        val totalRecipients = {len(recipients)}
        
        sigmaProp({{
            val validOutputs = OUTPUTS.slice(0, totalRecipients)
            val allValidRecipients = validOutputs.forall({{(output: Box) =>
                recipientTrees.exists({{(tree: Coll[Byte]) => 
                    output.propositionBytes == tree
                }})
            }})
            val validTokenTransfer = validOutputs.forall({{(output: Box) =>
                output.tokens.size == 1 && output.tokens(0)._1 == SELF.tokens(0)._1
            }})
            
            allValidRecipients && validTokenTransfer
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)

def mint_tokens_to_proxy(token_name, token_description, token_amount, proxy_contract, decimals=5):
    unspent_boxes = appKit.boxesToSpend(minter_address, int(1e7) + int(1e6))
    
    token_id = unspent_boxes[0].getId().toString()
    
    mint_output = appKit.mintToken(
        value=int(1e7),  # 0.01 ERG
        tokenId=token_id,
        tokenName=token_name,
        tokenDesc=token_description,
        mintAmount=token_amount,
        decimals=decimals,
        contract=appKit.contractFromTree(proxy_contract)
    )
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[mint_output],
        fee=int(1e6),
        sendChangeTo=Address.create(minter_address).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    print(f"Minting transaction sent. Transaction ID: {tx_id}")
    return token_id

def create_distribution_box(token_id, tokens_to_dispense, proxy_contract, distribution_contract):
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    erg_amount_per_box = int(1e6)  # 0.001 ERG per box
    total_erg_needed = erg_amount_per_box * len(recipient_wallets) + int(1e6)  # Additional 0.001 ERG for the change box
    
    unspent_boxes = appKit.boxesToSpend(proxy_address, total_erg_needed, {token_id: tokens_to_dispense})
    
    if not unspent_boxes:
        raise ValueError(f"No unspent boxes found with token {token_id}")
    
    distribution_output = appKit.buildOutBox(
        value=total_erg_needed - int(1e6),  # Subtract fee
        tokens={token_id: tokens_to_dispense},
        registers=None,
        contract=appKit.contractFromTree(distribution_contract)
    )
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[distribution_output],
        fee=int(1e6),
        sendChangeTo=Address.fromErgoTree(proxy_contract, appKit._networkType).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    print(f"Distribution box created. Transaction ID: {tx_id}")

def dispense_tokens(token_id, recipient_addresses, distribution_contract, proxy_contract, tokens_to_dispense):
    distribution_address = Address.fromErgoTree(distribution_contract, appKit._networkType).toString()
    erg_amount_per_box = int(1e6)  # 0.001 ERG per box
    total_erg_needed = erg_amount_per_box * len(recipient_addresses)
    unspent_boxes = appKit.boxesToSpend(distribution_address, total_erg_needed, {token_id: tokens_to_dispense})
    
    if not unspent_boxes:
        raise ValueError(f"No unspent distribution box found with token {token_id}")
    
    tokens_per_recipient = tokens_to_dispense // len(recipient_addresses)
    outputs = []
    
    for recipient in recipient_addresses:
        output = appKit.buildOutBox(
            value=erg_amount_per_box,  # 0.001 ERG
            tokens={token_id: tokens_per_recipient},
            registers=None,
            contract=appKit.contractFromAddress(recipient)
        )
        outputs.append(output)
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=outputs,
        fee=int(1e6),
        sendChangeTo=Address.fromErgoTree(proxy_contract, appKit._networkType).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    print(f"Tokens dispensed to {len(recipient_addresses)} recipients. Transaction ID: {tx_id}")

def main():
    current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    
    # Create the proxy contract
    proxy_contract = create_proxy_contract(recipient_wallets)
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    print(f"Proxy contract address: {proxy_address}")
    
    # Mint tokens to proxy contract
    token_name = "ProxyToken"
    token_description = "Test Token for proxy dispensing for sigs mining pool"
    total_tokens = 5 * 100000  # 5 tokens with 5 decimal places
    tokens_to_dispense_per_round = 100000  # 1 token with 5 decimal places
    token_id = mint_tokens_to_proxy(token_name, token_description, total_tokens, proxy_contract, decimals=5)
    
    print(f"Tokens minted. Token ID: {token_id}")
    
    # Calculate required ERGs
    num_recipients = len(recipient_wallets)
    num_rounds = total_tokens // tokens_to_dispense_per_round
    required_ergs = num_recipients * num_rounds * int(1e6)  # 0.001 ERG per recipient per round
    print(f"Required ERGs for all rounds: {required_ergs / 1e9} ERG")
    print(f"Number of recipients: {num_recipients}")
    print(f"Number of rounds: {num_rounds}")
    time.sleep(60 * 3)
    # Set up dispensing parameters
    blocks_between_dispense = 2  # Dispense every 2 blocks
    last_dispense_height = current_height
    
    for round in range(num_rounds):
        current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        unlock_height = current_height + blocks_between_dispense
        
        # Create distribution contract for this round
        distribution_contract = create_distribution_contract(unlock_height, recipient_wallets)
        
        # Create distribution box for this round
        create_distribution_box(token_id, tokens_to_dispense_per_round, proxy_contract, distribution_contract)
        
        # Wait until unlock height
        while current_height < unlock_height:
            time.sleep(60)  # Wait for 1 minute before checking again
            current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        
        # Dispense tokens
        try:
            dispense_tokens(token_id, recipient_wallets, distribution_contract, proxy_contract, tokens_to_dispense_per_round)
            print(f"Dispensed tokens for round {round + 1} at block height {current_height}")
        except Exception as e:
            print(f"Error dispensing tokens: {str(e)}")
        
        # Wait for the next dispense interval
        time.sleep(60 * blocks_between_dispense)

if __name__ == "__main__":
    main()