# Transaction Limit Bug Investigation and Fix

## The Issue

When running our blockchain block height collector, we observed inconsistent results:
- Sometimes it found only 4 blocks after height 1509800
- Other times it found 54 blocks after the same height

## Root Cause Investigation

To debug this issue, we:

1. Created a debug script (`debug_tx_lookup.py`) with extensive logging
2. Tested with different heights and parameter combinations
3. Added functionality to limit the transactions processed per page
4. Added search functionality to track specific block heights

Key findings:

1. The API returns transactions in reverse chronological order (newest first)
2. When processing only 50 transactions per page, we found 0 blocks in the key range
3. When processing 100 transactions per page, we found all 54 blocks
4. The 4 blocks originally observed (1509846, 1509996, 1510211, 1510299) are in positions 51-54 in the transaction list

## Problem Diagnosis

In the codebase, we found inconsistent transaction limits used when calling the API:
1. In `get_blocks_since_last_outgoing`, a limit of 100 was used
2. In other API calls, a limit of 50 was used

Since the key blocks appeared at positions 51-54, they were missed when using a limit of 50.

## Solution

We implemented the following fixes:

1. Created a constant `TRANSACTION_PAGE_LIMIT = 100` at the module level
2. Replaced all hardcoded limits with this constant
3. Added a detailed comment explaining why the limit should not be decreased
4. Fixed some related issues, such as pagination calculations

The fix ensures that all code paths use the same transaction limit, guaranteeing consistent results.

## Verification

After implementing the fix, we ran the debug script with the test height of 1509800 and confirmed that it consistently finds all 54 blocks.

## Lessons Learned

1. API pagination limits are critical for data consistency
2. When results are ordered, using different page sizes can lead to missing data
3. Constants should be used for critical configuration values to ensure consistency
4. Good debugging tools are essential for identifying issues with external APIs

## Future Recommendations

1. Consider adding unit tests for this functionality
2. Add monitoring to alert if unusually low numbers of blocks are found
3. Consider implementing retry logic for API failures
4. Review other pagination implementations for similar issues 