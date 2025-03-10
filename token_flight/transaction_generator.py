def generate_unsigned_transaction(sender, recipients, fee, nonce, timestamp, extra_data=None):
    """
    Generates the transaction skeleton before applying the signature.
    
    Parameters:
        sender (str): The sender's address.
        recipients (list): List of dictionaries with recipient addresses and token amounts.
        fee (str): The transaction fee.
        nonce (int): Unique nonce for the transaction.
        timestamp (str): ISO formatted timestamp.
        extra_data (dict, optional): Any auxiliary data.
    
    Returns:
        dict: The unsigned transaction.
    """
    transaction = {
        "sender": sender,
        "recipients": recipients,
        "fee": fee,
        "nonce": nonce,
        "timestamp": timestamp,
        "data": extra_data or {}
    }
    return transaction


def generate_fleet_transaction_data(sender, recipients, fee, nonce, timestamp, extra_data=None):
    """
    Generates transaction data in a FleetSDK-compatible format.
    
    This method first calls generate_unsigned_transaction to get the standard transaction 
    structure and then converts it to the format required by FleetSDK.
    
    Parameters:
        sender (str): The sender's address.
        recipients (list): List of dictionaries with recipient addresses, token amounts, and optional tokens.
        fee (str): The transaction fee.
        nonce (int): Unique nonce for the transaction.
        timestamp (str): ISO formatted timestamp.
        extra_data (dict, optional): Any auxiliary data.
    
    Returns:
        dict: FleetSDK compatible transaction data.
    """
    # First generate the regular unsigned transaction
    tx = generate_unsigned_transaction(sender, recipients, fee, nonce, timestamp, extra_data)
    
    # Convert to FleetSDK format
    fleet_format = {
        "outputs": [
            {
                "address": recipient["address"],
                "amount": recipient["amount"],
                "tokens": recipient.get("tokens", [])
            }
            for recipient in tx["recipients"]
        ],
        "fee": tx["fee"],
        "additionalData": tx["data"]
    }
    
    return fleet_format


# Example usage of the above functions:
if __name__ == "__main__":
    sender_address = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
    recipient_list = [
        {"address": "0x1234567890abcdef1234567890abcdef12345678", "amount": 100},
        {"address": "0xfedcba0987654321fedcba0987654321fedcba09", "amount": 200, "tokens": ["token1", "token2"]}
    ]
    fee = "0.001"
    nonce = 1
    timestamp = "2023-10-01T10:00:00Z"
    
    # Generate the unsigned transaction
    unsigned_tx = generate_unsigned_transaction(sender_address, recipient_list, fee, nonce, timestamp)
    print("Unsigned Transaction:", unsigned_tx)
    
    # Generate the FleetSDK-compatible transaction data
    fleet_tx = generate_fleet_transaction_data(sender_address, recipient_list, fee, nonce, timestamp)
    print("FleetSDK Compatible Transaction Data:", fleet_tx) 