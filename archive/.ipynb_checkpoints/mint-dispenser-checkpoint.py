from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, Constants
import time

# Initialize ErgoAppKit
node_url = "http://37.27.198.175:9053/"
explorer_url = "https://api.ergoplatform.com/"
appKit = ErgoAppKit(node_url, "mainnet", explorer_url, 'hashcream')

# Define addresses
minter_address = "9ebLdLKX7k6gAyruUPeqrT1jqKtscvFiW11EFmX5tcAvmwfZSsH"
proxy_address = "9eg7v2nkypUZbdyvSKSD9kg8FNwrEdTrfC2xdXWXmEpDAFEtYEn"  # Replace with your actual proxy address

# # List of recipient wallets
recipient_wallets = ['9fj3mV8aF27jZBBH5HBdecVcD5hoUcqqcMmo1j8aUbCA1rceGLE',
                     '9hAcdWpFAv7biCSeUcCvXWYRfEepm1ubdsfg5PC48k9S7ymiU3W',
                    '9eg7v2nkypUZbdyvSKSD9kg8FNwrEdTrfC2xdXWXmEpDAFEtYEn']

# recipient_wallets = [
#     '9hDJ91Rx5TZf4njCG6AAcsf4GEWyQxrh5ioZ95mXQk8QtCNv8Js',
#     '9feNRbYuVz2nQy1V8t2z5saYnWKwmGJ2nYgcMdXBjqYXqHMeWnv',
#     '9gwFTap8YaQEzsMAXdt4pa1BjAsR9gcijMMuxTRrAf4vgMhSnXY',
#     '9hYeUWUG2dAM6sZb9vr5qgF1gACEGQPLN9cbXjxERmJS89Tbadc',
#     '9fYvQMsMN3NNaw33cAFnRdyHy1DpxtxfADvGqUV3ocLptw4HpcP',
#     '9fuHCh7cvbWxMXdhNpjxAFVGCtP4W3yP6v7vVLPFYB4PR3NpyAL',
#     '9ggrhWJVjTHHUrK8qJThWi1yBscmETnT3nxTwVDfQQPCASaZmxt',
#     '9fyDqkVk3iDXPNcquyLBehEtiZiqdKb27PnugemJEpGYbTJM7tN',
#     '9enXTiL3i9CKWKCcE3fby2hSaeoWEWV28evc1j1SK9yKRDy9cVN',
#     '9eoPRhRmJQ71TPSkk2eUmMXYpxUVvZvFQo5uB9qjPBM4e3hC82J',
#     '9i8wsL9HYe4wRtuxXtnvki31uGJd6avKoQ79BXbz2sHWNZSKz8K',
#     '9fjQi1JrgFZ9QBKGbE7EYDwUwAvGUk95Wa92kV2D4EnggNcnMzN',
#     '9fvDaBsLKmzP67Cp2i2bmhM1359HhJCrej8y5EGoUcmXDrBqxbW',
#     '9fHLdYBz5fPdDfMkGMfAsuj6EfXCpmM4GkamT23xeT3hzdHbNJx',
#     '9gNEKbpPSNfgWkhxsMF4Z9L7uNiXFfsEX4XTVF5XK4kwpQBRsEQ',
#     '9fLytFFzTYALknc2AZ2dRKeg8sLZwe4LX5qAB3FwDysMEeRTHkV',
#     ]


import binascii

def create_proxy_contract(recipients, unlock_height):
    # Convert recipient addresses to a format usable in the contract
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    
    # Create a string representation of the recipient trees
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    # Create the proxy contract
    contract_script = f"""
    {{
        val recipientTrees = Coll({recipient_trees_str})
        val unlockHeight = {unlock_height}L
        
        sigmaProp({{
            val recipientOutput = OUTPUTS(0)
            val validRecipient = recipientTrees.exists({{(tree: Coll[Byte]) => 
                recipientOutput.propositionBytes == tree
            }})
            val heightOk = HEIGHT >= unlockHeight
            val singleTokenTransfer = recipientOutput.tokens.size == 1 && recipientOutput.tokens(0)._2 == 1L
            
            validRecipient && heightOk && singleTokenTransfer
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)


def mint_tokens_to_proxy(token_name, token_description, token_amount, proxy_contract, decimals=0):
    unspent_boxes = appKit.boxesToSpend(minter_address, int(1e7) + int(1e6))
    
    token_id = unspent_boxes[0].getId().toString()
    
    mint_output = appKit.mintToken(
        value=int(1e6*2*3),  # 0.01 ERG
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

def dispense_token(token_id, recipient_address, proxy_contract):
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    unspent_boxes = appKit.boxesToSpend(proxy_address, int(1e6), {token_id: 1})
    
    if not unspent_boxes:
        raise ValueError(f"No unspent boxes found with token {token_id}")
    
    output = appKit.buildOutBox(
        value=int(1e6),  # 0.001 ERG
        tokens={token_id: 1},
        registers=None,
        contract=appKit.contractFromAddress(recipient_address)
    )
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[output],
        fee=int(1e6),
        sendChangeTo=Address.fromErgoTree(proxy_contract, appKit._networkType).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    print(f"Token dispensed to {recipient_address}. Transaction ID: {tx_id}")

def main():
    current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    unlock_height = current_height + 1  # Unlock after 10 blocks
    
    # Create the proxy contract
    proxy_contract = create_proxy_contract(recipient_wallets, unlock_height)
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    print(f"Proxy contract address: {proxy_address}")
    
    # Mint tokens to proxy contract
    token_name = "ProxyToken"
    token_description = "Test Token for proxy dispensing for sigs mining pool"
    total_tokens = len(recipient_wallets) * 2 
    token_id = mint_tokens_to_proxy(token_name, token_description, total_tokens, proxy_contract)
    
    print(f"Tokens minted. Token ID: {token_id}")
    
    # Set up dispensing parameters
    blocks_between_dispense = 2  # Dispense every 2 blocks
    last_dispense_height = current_height
    current_recipient_index = 0
    
    while True:
        current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        
        if current_height >= last_dispense_height + blocks_between_dispense and current_height >= unlock_height:
            try:
                recipient = recipient_wallets[current_recipient_index]
                dispense_token(token_id, recipient, proxy_contract)
                last_dispense_height = current_height
                current_recipient_index = (current_recipient_index + 1) % len(recipient_wallets)
                print(f"Dispensed token to {recipient} at block height {current_height}")
            except Exception as e:
                print(f"Error dispensing token: {str(e)}")
        
        time.sleep(60)  # Wait for 1 minute before checking again

if __name__ == "__main__":
    main()