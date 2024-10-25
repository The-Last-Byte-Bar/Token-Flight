import json
import time
import logging
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, Constants
import binascii

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(file_path):
    with open(file_path, 'r') as config_file:
        return json.load(config_file)

def create_proxy_contract(recipients, unlock_height, node_address):
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    node_tree = Address.create(node_address).getErgoAddress().script().bytes()
    node_tree_hex = binascii.hexlify(bytes(node_tree)).decode('utf-8')
    
    contract_script = f"""
    {{
        val recipientTrees = Coll({recipient_trees_str})
        val unlockHeight = {unlock_height}L
        val nodeTree = fromBase16("{node_tree_hex}")
        
        sigmaProp({{
            val validRecipients = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                recipientTrees.exists({{(tree: Coll[Byte]) => 
                    out.propositionBytes == tree
                }})
            }})
            val heightOk = HEIGHT >= unlockHeight
            val validTokenDistribution = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                out.tokens.size == 1 && out.tokens(0)._2 > 0L
            }})
            
            val spentByNode = OUTPUTS(0).propositionBytes == nodeTree
            
            (validRecipients && heightOk && validTokenDistribution) || spentByNode
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)

def mint_tokens_to_proxy(token_name, token_description, token_amount, proxy_contract, decimals=0):
    erg_amount = int(1e6) * (len(config['parameters']['recipientWallets']) + 1)
    unspent_boxes = appKit.boxesToSpend(config['parameters']['minterAddr'], erg_amount + int(1e6))
    
    token_id = unspent_boxes[0].getId().toString()
    
    mint_output = appKit.mintToken(
        value=erg_amount,
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
        sendChangeTo=Address.create(config['parameters']['minterAddr']).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    tx_id = appKit.sendTransaction(signed_tx)
    logger.info(f"Minting transaction sent. Transaction ID: {tx_id}")
    logger.info(f"Minted {token_amount} tokens with {erg_amount/1e9:.9f} ERG locked in proxy contract")
    return token_id

def dispense_tokens(token_id, recipient_addresses, tokens_per_round, proxy_contract):
    erg_per_recipient = int(1e6)  # 0.001 ERG
    total_erg_needed = erg_per_recipient * len(recipient_addresses)
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    unspent_boxes = appKit.boxesToSpend(proxy_address, total_erg_needed, {token_id: tokens_per_round})
    
    if not unspent_boxes:
        raise ValueError(f"No unspent boxes found with token {token_id} and sufficient ERG")
    
    outputs = []
    tokens_per_recipient = tokens_per_round // len(recipient_addresses)
    
    for recipient in recipient_addresses:
        output = appKit.buildOutBox(
            value=erg_per_recipient,
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
    logger.info(f"Tokens dispensed to {len(recipient_addresses)} recipients. Transaction ID: {tx_id}")
    logger.info(f"Distributed {tokens_per_round} tokens with {total_erg_needed/1e9:.9f} ERG")

def recover_erg(proxy_contract, node_address):
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    unspent_boxes = appKit.boxesToSpend(proxy_address, 0)
    
    if not unspent_boxes:
        logger.info("No unspent boxes found in the proxy contract")
        return
    
    total_erg = sum(box.getValue() for box in unspent_boxes)
    total_tokens = {}
    
    for box in unspent_boxes:
        for token in box.getTokens():
            token_id = token.getId().toString()
            token_amount = token.getValue()
            if token_id in total_tokens:
                total_tokens[token_id] += token_amount
            else:
                total_tokens[token_id] = token_amount
    
    output = appKit.buildOutBox(
        value=total_erg - int(1e6),  # Subtract fee
        tokens=total_tokens,
        registers=None,
        contract=appKit.contractFromAddress(node_address)
    )
    
    unsigned_tx = appKit.buildUnsignedTransaction(
        inputs=unspent_boxes,
        outputs=[output],
        fee=int(1e6),
        sendChangeTo=Address.create(node_address).getErgoAddress()
    )
    signed_tx = appKit.signTransactionWithNode(unsigned_tx)
    
    tx_id = appKit.sendTransaction(signed_tx)
    logger.info(f"ERG and tokens recovered to node wallet. Transaction ID: {tx_id}")
    logger.info(f"Recovered {total_erg/1e9:.9f} ERG and {total_tokens} tokens")

def main():
    global appKit, config
    
    config = load_config('ergo.json')
    
    node_url = config['node']['nodeApi']['apiUrl']
    explorer_url = config['node']['explorer_url']
    api_key = config['node']['nodeApi']['apiKey']
    
    appKit = ErgoAppKit(node_url, config['node']['networkType'], explorer_url, api_key)
    
    current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    unlock_height = current_height + 1
    
    node_address = config['node']['nodeAddress']  # Add this to your config file
    proxy_contract = create_proxy_contract(config['parameters']['recipientWallets'], unlock_height, node_address)
    proxy_address = Address.fromErgoTree(proxy_contract, appKit._networkType).toString()
    logger.info(f"Proxy contract address: {proxy_address}")
    
    token_id = mint_tokens_to_proxy(
        config['token']['name'],
        config['token']['description'],
        config['token']['totalAmount'],
        proxy_contract,
        config['token']['decimals']
    )
    
    logger.info(f"Tokens minted. Token ID: {token_id}")
    
    last_dispense_height = current_height
    
    total_rounds = config['token']['totalAmount'] // config['distribution']['tokensPerRound']
    total_erg_needed = total_rounds * len(config['parameters']['recipientWallets']) * 0.001
    logger.info(f"Total number of distribution rounds: {total_rounds}")
    logger.info(f"Total ERG needed for all rounds: {total_erg_needed:.3f} ERG")
    
    while True:
        current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        
        if current_height >= last_dispense_height + config['distribution']['blocksBetweenDispense'] and current_height >= unlock_height:
            try:
                dispense_tokens(
                    token_id,
                    config['parameters']['recipientWallets'],
                    config['distribution']['tokensPerRound'],
                    proxy_contract
                )
                last_dispense_height = current_height
                logger.info(f"Dispensed tokens at block height {current_height}")
            except Exception as e:
                logger.error(f"Error dispensing tokens: {str(e)}")
        
        time.sleep(60)  # Wait for 1 minute before checking again
    
    # Uncomment the following line to recover ERG and tokens at the end of distribution
    # recover_erg(proxy_contract, node_address)

if __name__ == "__main__":
    main()