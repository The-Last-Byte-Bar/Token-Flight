import json
import logging
import time
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address, ErgoValue, Constants

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
with open('testnet.json', 'r') as config_file:
    config = json.load(config_file)

# Initialize ErgoAppKit
node_url = config['node']['nodeApi']['apiUrl']
api_key = config['node']['nodeApi']['apiKey']
network_type = config['node']['networkType']
appKit = ErgoAppKit(node_url, network_type, config['node']['explorer_url'], api_key)

def dispense_token(token_id, recipient_address, proxy_address, unlock_height):
    logging.info(f"Attempting to dispense token {token_id} to {recipient_address}")
    try:
        current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
        
        if current_height < unlock_height:
            logging.warning(f"Current height {current_height} is less than unlock height {unlock_height}")
            return False
        
        unspent_boxes = appKit.boxesToSpend(proxy_address, int(1e6), {token_id: 1})
        
        if not unspent_boxes:
            logging.warning(f"No unspent boxes found with token {token_id}")
            return False
        
        logging.info(f"Found {len(unspent_boxes)} unspent box(es) with the token")
        
        # Create the output box for the recipient
        recipient_output = appKit.buildOutBox(
            value=int(1e6),  # 0.001 ERG
            tokens={token_id: 1},
            registers=None,
            contract=appKit.contractFromAddress(recipient_address)
        )
        
        logging.info("Built output box for the transaction")
        
        # Create the unsigned transaction
        unsigned_tx = appKit.buildUnsignedTransaction(
            inputs=unspent_boxes,
            outputs=[recipient_output],
            fee=int(1e6),
            sendChangeTo=Address.create(proxy_address).getErgoAddress(),
            preHeader=appKit._ergoClient.getPreHeaders().get(0)
        )
        
        logging.info("Built unsigned transaction")
        
        signed_tx = appKit.signTransactionWithNode(unsigned_tx)
        logging.info("Transaction signed with node")
        
        tx_id = appKit.sendTransaction(signed_tx)
        logging.info(f"Token dispensed to {recipient_address}. Transaction ID: {tx_id}")
        return True
    except Exception as e:
        logging.error(f"Error dispensing token: {str(e)}")
        return False

def main():
    token_id = config['token']['tokenId']
    recipient_wallets = config['parameters']['recipientWallets']
    proxy_address = config['proxy']['address']
    unlock_height = config.get('proxy', {}).get('unlockHeight', 0)
    blocks_between_dispense = config['distribution']['blocksBetweenDispense']
    
    logging.info(f"Token ID: {token_id}")
    logging.info(f"Number of recipient wallets: {len(recipient_wallets)}")
    logging.info(f"Proxy address: {proxy_address}")
    logging.info(f"Unlock height: {unlock_height}")
    logging.info(f"Blocks between dispense: {blocks_between_dispense}")
    
    current_recipient_index = 0
    last_dispense_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
    
    while True:
        try:
            current_height = appKit._ergoClient.execute(lambda ctx: ctx.getHeight())
            logging.info(f"Current block height: {current_height}")
            
            if current_height >= 0: #s last_dispense_height + blocks_between_dispense:
                recipient = recipient_wallets[current_recipient_index]
                logging.info(f"Attempting to dispense token to recipient {current_recipient_index + 1}/{len(recipient_wallets)}: {recipient}")
                
                success = dispense_token(token_id, recipient, proxy_address, unlock_height)
                
                if success:
                    last_dispense_height = current_height
                    current_recipient_index = (current_recipient_index + 1) % len(recipient_wallets)
                    logging.info(f"Successfully dispensed token at block height {current_height}")
                else:
                    logging.warning("Failed to dispense token, will retry in the next cycle")
            else:
                blocks_to_wait = last_dispense_height + blocks_between_dispense - current_height
                logging.info(f"Waiting for {blocks_to_wait} more block(s) before next dispense")
            
            time.sleep(60)  # Wait for 1 minute before checking again
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            time.sleep(60)  # Wait for 1 minute before retrying

if __name__ == "__main__":
    logging.info("Starting Ergo Token Distribution Bot")
    main()
    logging.info("Ergo Token Distribution Bot stopped")