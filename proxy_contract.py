# proxy_contract.py
import binascii
from ergo_python_appkit.appkit import ErgoAppKit
from org.ergoplatform.appkit import Address
from fee_calculator import calculate_total_fees

def create_proxy_contract(appKit: ErgoAppKit, recipients: list[str], unlock_height: int, 
                         node_address: str, end_height: int) -> bytes:
    """Create proxy contract with end time logic"""
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() 
                           for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') 
                               for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' 
                                   for tree in recipient_ergo_trees_hex)
    
    node_tree = Address.create(node_address).getErgoAddress().script().bytes()
    node_tree_hex = binascii.hexlify(bytes(node_tree)).decode('utf-8')
    
    contract_script = f"""
    {{
        // Collection of valid recipient addresses
        val recipientTrees = Coll({recipient_trees_str})
        
        // Heights for unlocking conditions
        val unlockHeight = {unlock_height}L
        val endHeight = {end_height}L
        val nodeTree = fromBase16("{node_tree_hex}")
        
        sigmaProp({{
            if (HEIGHT >= endHeight) {{
                // After end height, node can collect remaining funds
                OUTPUTS(0).propositionBytes == nodeTree
            }} else {{
                val validRecipients = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                    recipientTrees.exists({{(tree: Coll[Byte]) => 
                        out.propositionBytes == tree
                    }})
                }})
                
                val heightOk = HEIGHT >= unlockHeight
                
                // Check token distribution and collect any additional tokens
                val validTokenDistribution = {{
                    val distributionOutputs = OUTPUTS.slice(0, recipientTrees.size)
                    val totalTokens = SELF.tokens.fold(0L, {{(acc: Long, token: (Coll[Byte], Long)) => acc + token._2}})
                    
                    // Ensure all recipients get equal share of all tokens
                    distributionOutputs.forall({{(out: Box) =>
                        out.tokens.size >= 1 && 
                        out.tokens.fold(0L, {{(acc: Long, token: (Coll[Byte], Long)) => 
                            acc + token._2
                        }}) == totalTokens / recipientTrees.size
                    }})
                }}
                
                val spentByNode = OUTPUTS(0).propositionBytes == nodeTree
                
                (validRecipients && heightOk && validTokenDistribution) || spentByNode
            }}
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)