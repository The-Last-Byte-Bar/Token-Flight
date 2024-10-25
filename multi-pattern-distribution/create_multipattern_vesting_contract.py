def create_multipattern_vesting_contract(
    appKit: ErgoAppKit,
    recipients: list[str],
    start_height: int,
    end_height: int,
    token_distribution_patterns: dict[str, str],
    node_address: str
) -> bytes:
    """
    Creates a smart contract that handles vesting of multiple tokens with configurable 
    distribution patterns. Each token can have its own distribution curve (linear, 
    quadratic, exponential, or logarithmic) and will be distributed proportionally 
    to all recipients over the vesting period.
    
    Args:
        appKit: ErgoAppKit instance
        recipients: List of recipient addresses that will receive the vested tokens
        start_height: Block height when vesting begins
        end_height: Block height when vesting ends
        token_distribution_patterns: Dictionary mapping token IDs to their distribution pattern
                                   Supported patterns:
                                   - "linear": Constant rate distribution
                                   - "quadratic": Accelerating distribution
                                   - "exponential": Sharply accelerating distribution
                                   - "logarithmic": Heavy early distribution
        node_address: Address of the contract creator/administrator who can reclaim tokens
    
    Returns:
        bytes: Compiled ErgoScript contract that enforces the vesting schedule
    """
    recipient_ergo_trees = [Address.create(addr).getErgoAddress().script().bytes() for addr in recipients]
    recipient_ergo_trees_hex = [binascii.hexlify(bytes(tree)).decode('utf-8') for tree in recipient_ergo_trees]
    recipient_trees_str = ', '.join(f'fromBase16("{tree}")' for tree in recipient_ergo_trees_hex)
    
    # Convert token IDs and their distribution patterns to contract format
    distribution_patterns = []
    for token_id, pattern in token_distribution_patterns.items():
        distribution_patterns.append(f'(fromBase16("{token_id}"), "{pattern}")')
    distribution_patterns_str = ', '.join(distribution_patterns)
    
    node_tree = Address.create(node_address).getErgoAddress().script().bytes()
    node_tree_hex = binascii.hexlify(bytes(node_tree)).decode('utf-8')
    
    contract_script = f"""
    {{
        val recipientTrees = Coll({recipient_trees_str})
        val startHeight = {start_height}L
        val endHeight = {end_height}L
        val nodeTree = fromBase16("{node_tree_hex}")
        
        // Define distribution patterns for each token
        val distributionPatterns = Coll({distribution_patterns_str})
        
        def calculateLinearVesting(progress: Double): Long = {{
            (progress * 100).toLong
        }}
        
        def calculateQuadraticVesting(progress: Double): Long = {{
            (progress * progress * 100).toLong
        }}
        
        def calculateExponentialVesting(progress: Double): Long = {{
            // e^(progress - 1) normalized to 0-100 range
            val exp = progress * 2.718281828459045 - 1
            ((exp / 1.718281828459045) * 100).toLong
        }}
        
        def calculateLogVesting(progress: Double): Long = {{
            // ln(progress + 1) normalized to 0-100 range
            val ln = log(progress + 1)
            ((ln / 0.6931471805599453) * 100).toLong
        }}
        
        def getVestingPercentage(tokenId: Coll[Byte], currentHeight: Long): Long = {{
            if (currentHeight <= startHeight) return 0L
            if (currentHeight >= endHeight) return 100L
            
            val totalPeriod = endHeight - startHeight
            val progress = (currentHeight - startHeight).toDouble / totalPeriod
            
            // Find the distribution pattern for this token
            val pattern = distributionPatterns.find({{(p) => p._1 == tokenId}}).get._2
            
            pattern match {{
                case "linear" => calculateLinearVesting(progress)
                case "quadratic" => calculateQuadraticVesting(progress)
                case "exponential" => calculateExponentialVesting(progress)
                case "logarithmic" => calculateLogVesting(progress)
                case _ => calculateLinearVesting(progress) // Default to linear if pattern not found
            }}
        }}
        
        sigmaProp({{
            val heightOk = HEIGHT >= startHeight
            
            val validDistribution = {{
                val numRecipients = recipientTrees.size.toLong
                
                SELF.tokens.forall({{(selfToken) =>
                    val tokenId = selfToken._1
                    val totalAmount = selfToken._2
                    
                    val currentVestingPercentage = getVestingPercentage(tokenId, HEIGHT)
                    val distributableAmount = (totalAmount * currentVestingPercentage) / 100L
                    
                    // Find previous state
                    val prevBox = INPUTS.find({{(box: Box) => 
                        box.tokens.exists({{(t) => t._1 == tokenId}})
                    }}).get
                    
                    val prevVestingPercentage = getVestingPercentage(tokenId, CONTEXT.preHeader.height - 1L)
                    val prevDistributableAmount = (totalAmount * prevVestingPercentage) / 100L
                    
                    val newlyVestedAmount = distributableAmount - prevDistributableAmount
                    val sharePerRecipient = newlyVestedAmount / numRecipients
                    
                    OUTPUTS.slice(0, numRecipients.toInt).forall({{(out: Box) =>
                        out.tokens.exists({{(outToken) =>
                            outToken._1 == tokenId &&
                            outToken._2 >= sharePerRecipient
                        }})
                    }})
                }})
            }}
            
            val validRecipients = OUTPUTS.slice(0, recipientTrees.size).forall({{(out: Box) =>
                recipientTrees.exists({{(tree: Coll[Byte]) => 
                    out.propositionBytes == tree
                }})
            }})
            
            val spentByNode = OUTPUTS(0).propositionBytes == nodeTree
            
            (heightOk && validDistribution && validRecipients) || spentByNode
        }})
    }}
    """
    
    return appKit.compileErgoScript(contract_script)