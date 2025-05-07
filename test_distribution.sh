#!/bin/bash

# test_distribution.sh - A wrapper script that enforces dry run mode
# 
# Usage:
#   ./test_distribution.sh --service bonus --config-file your_config.json
#   ./test_distribution.sh --service demurrage --run-once
#
# This script will always add the --dry-run flag to ensure that no actual 
# transactions are submitted during testing.

# Ensure we're in the project root directory
cd "$(dirname "$0")" || exit 1

# Set dry run in environment variable too as a fallback
export DRY_RUN=true

# Construct the command string for logging/notification
COMMAND_ARGS=("$@") # Store original arguments
COMMAND_TO_RUN="./run_distribution.sh ${COMMAND_ARGS[@]} --dry-run"

echo "🧪 Running in TEST mode (--dry-run enforced)"
echo "📦 Command: $COMMAND_TO_RUN"
echo "-------------------------------------------"

# Run with all passed arguments plus --dry-run and capture output
echo "⚙️ Executing distribution script..."
output=$(./run_distribution.sh "$@" --dry-run 2>&1)
exit_code=$?

# Print the captured output to the console for visibility
echo "------------------- Captured Output -------------------"
echo "$output"
echo "-------------------------------------------------------"


# Determine result and construct summary message
if [ $exit_code -eq 0 ]; then
  RESULT_ICON="✅"
  RESULT_TEXT="SUCCESS"
  echo "$RESULT_ICON Test completed successfully"
else
  RESULT_ICON="❌"
  RESULT_TEXT="FAILED"
  echo "$RESULT_ICON Test failed with exit code: $exit_code"
fi

# Prepare summary message for Telegram
HOSTNAME=$(hostname)
SUMMARY_MSG="<b>Distribution Test Summary ($HOSTNAME)</b>

Result: $RESULT_ICON $RESULT_TEXT (Exit Code: $exit_code)
Command: <code>$COMMAND_TO_RUN</code>"

# If successful dry run, extract, format, and add details
if [ $exit_code -eq 0 ]; then
  # Use awk to extract and format details into aligned columns
  # Header: Token (Left-aligned, 20 chars), Amount/Miner (Right-aligned, 18 chars, 6 decimals), Total (Right-aligned, 18 chars, 6 decimals)
  details=$(printf '%s' "$output" | awk '
  /^Details:/ { 
      flag=1; 
      printf "%s\n", "------------------------------------------------------------";
      printf "%-20s %18s %18s\n", "Token", "Amount/Miner", "Total"; 
      printf "%s\n", "------------------------------------------------------------";
      next 
  }
  flag && NF > 0 { # Process lines only after "Details:" and ignore empty lines
    # Split the line based on ":" and "("
    split($0, parts, /[:(]/)
    token_name = parts[1]
    gsub(/^[ \t]+|[ \t]+$/, "", token_name); # Trim whitespace

    # Extract amount_per from the second part
    amount_per_part = parts[2]
    sub(/ each to .*$/, "", amount_per_part)
    gsub(/^[ \t]+|[ \t]+$/, "", amount_per_part);
    amount_per = amount_per_part

    # Extract total_distributed from the FOURTH part (was parts[3])
    total_dist_part = parts[4]
    # Remove trailing ")" and surrounding spaces first
    sub(/[ \t]*\)[ \t]*$/, "", total_dist_part) 
    # Trim remaining whitespace
    gsub(/^[ \t]+|[ \t]+$/, "", total_dist_part);
    total_dist = total_dist_part

    # Format and print using printf for alignment and decimal places
    printf "% -20s %18.6f %18.6f\n", token_name, amount_per, total_dist
  }
  ')
  
  # Limit details length to avoid Telegram message limits (e.g., ~3500 chars)
  max_detail_len=3500
  if [ ${#details} -gt $max_detail_len ]; then
      details=$(echo -e "$details" | head -c $max_detail_len) # Use echo -e to handle newlines if present
      details+="\n... (output truncated)"
  fi
  
  # Check if details were actually extracted
  if [ -n "$details" ]; then
      # Add horizontal rule before details
      SUMMARY_MSG+="\n\n<b>Dry Run Details:</b>\n<pre><code>${details}</code></pre>"
  else
      SUMMARY_MSG+="\n\n(Dry run successful, but details could not be automatically extracted from output.)"
  fi
elif [ -n "$output" ]; then # If failed, add last few lines of output as context
    error_context=$(printf '%s' "$output" | tail -n 10)
    SUMMARY_MSG+="\n\n<b>Output Context (Last 10 Lines):</b>\n<pre><code>${error_context}</code></pre>"
fi

# Send summary notification using the helper script
chmod +x send_test_summary.py

echo "-------------------------------------------"
echo "📢 Sending Admin Test Summary Notification..."

# --- DEBUG: Echo the exact message being sent ---
echo "------- Telegram Message Start -------"
echo -e "$SUMMARY_MSG" # Use echo -e to interpret backslashes/newlines if any
echo "------- Telegram Message End ---------"
# --- End Debug ---

# Run the Python script to send the notification
# Use python3 explicitly if needed
python3 send_test_summary.py "$SUMMARY_MSG"
NOTIFICATION_EXIT_CODE=$?

if [ $NOTIFICATION_EXIT_CODE -ne 0 ]; then
    echo "⚠️ Warning: Failed to send admin test summary notification."
fi

exit $exit_code # Exit with the original exit code of the distribution script 