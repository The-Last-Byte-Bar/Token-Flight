#!/usr/bin/env python3
import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

try:
    from src.telegram_notifier import send_admin_test_summary
except ImportError as e:
    print(f"Error importing notification module: {e}")
    print("Ensure PYTHONPATH includes the project root or run from the project root.")
    sys.exit(1)

# Setup basic logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('send_test_summary')

def main():
    parser = argparse.ArgumentParser(description="Send a test summary notification to the admin Telegram chat.")
    parser.add_argument('message', type=str, help='The summary message to send.')
    args = parser.parse_args()
    
    logger.info("Attempting to send admin test summary...")
    result = send_admin_test_summary(args.message)
    
    if result.get('success'):
        logger.info("Admin test summary sent successfully.")
        print("Admin test summary sent.")
    else:
        logger.error(f"Failed to send admin test summary: {result.get('error')}")
        print(f"Error sending admin test summary: {result.get('error')}")
        # Optionally exit with error code if notification fails
        # sys.exit(1)

if __name__ == "__main__":
    main() 