# Transaction Limit Bug in Block Height Collection

## Issue Description

There's a discrepancy in the number of blocks found by the `get_blocks_since_last_outgoing` method in the `BlockHeightCollector` class:
- Sometimes it finds 4 blocks since height 1509800
- Other times it finds 54 blocks since the same height

## Root Cause

After extensive debugging, we've identified the issue:

1. The API returns transactions in reverse chronological order (newest first)
2. The 4 blocks with heights [1509846, 1509996, 1510211, 1510299] are in transactions #51-54 on the first page
3. When the code only processes 50 transactions per page, these blocks are missed
4. When 100 transactions are processed per page, all 54 blocks are found

This suggests that in some code paths, a limit of 50 transactions per page is being used instead of 100.

## Locations to Check

Looking at the code in `src/demurrage_distribution.py`:

1. The `get_blocks_since_last_outgoing` method uses a limit of 100 transactions:
   ```python
   limit = 100
   ```

2. However, there might be another code path that calls the API with a lower limit (50 transactions).
   Look for API calls like:
   ```python
   params={"offset": offset, "limit": 50}
   ```

## Recommended Fix

Ensure all API calls that fetch transactions for block height collection consistently use the same limit:

1. Review all API calls to `/addresses/{address}/transactions` 
2. Make sure they all use the same limit value (preferably 100)
3. Add comments to explain why this value should not be changed
4. Add tests that verify the correct number of blocks are found

## Example Fix

```python
# In src/demurrage_distribution.py

# Define a consistent limit across the codebase
TRANSACTION_PAGE_LIMIT = 100  # Do not lower this value without checking block collection logic

# Then replace all instances of hardcoded limits
response = requests.get(
    f"{self.api_base}/addresses/{self.wallet_address}/transactions",
    params={
        "offset": current_offset,
        "limit": TRANSACTION_PAGE_LIMIT,  # Use the consistent value
        "concise": True
    }
)
```

## Verification

After making the fix, run the debug script with:
```
./debug_tx_lookup.py --test-height 1509800
```

This should consistently return 54 blocks. 