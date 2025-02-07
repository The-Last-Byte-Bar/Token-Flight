import logging
from demurrage_service import DemurrageService
from base_scheduler import BaseScheduler
from dotenv import load_dotenv
import os

class DemurrageScheduler(BaseScheduler):
    def __init__(self, debug: bool = False):
        super().__init__(debug)
        self.service = DemurrageService(debug=debug)
        self.logger.info(f"Demurrage Scheduler initialized with debug: {debug}")

    def run_job(self):
        self.logger.info("Starting demurrage job execution")
        try:
            self.logger.info("Fetching blocks since last outgoing transaction")
            block_heights = self.service.collector.get_blocks_since_last_outgoing()
            
            if not block_heights:
                self.logger.info("No new blocks found since last outgoing transaction")
                return
                
            self.logger.info(f"Processing blocks: {block_heights}")
            
            if self.debug:
                self.logger.info("Debug mode - simulating distribution")
                wallet_balance = self.service.get_wallet_balance()
                self.logger.info(f"Current wallet balance: {wallet_balance} ERG")
                
                miners_data = self.service.collector.fetch_miners_data(block_heights)
                recipient_count = len(miners_data.get('miners', []))
                self.logger.info(f"Found {recipient_count} potential recipients")
                
                if recipient_count > 0:
                    distribution_amount = self.service.calculate_distribution_amount(recipient_count)
                    self.logger.info(f"Calculated distribution amount: {distribution_amount} ERG")
                else:
                    self.logger.info("No eligible recipients found")
                return
            
            # Execute actual distribution
            self.logger.info("Executing distribution")
            tx_id = self.service.execute_distribution(block_heights)
            if tx_id:
                self.logger.info(f"Distribution completed successfully. TX: {tx_id}")
            else:
                self.logger.warning("Distribution did not complete - no transaction ID returned")
                
        except ValueError as e:
            self.logger.error(f"Validation error in demurrage job: {e}")
        except Exception as e:
            self.logger.error(f"Error in demurrage job: {e}", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    load_dotenv('/app/.env.demurrage')
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    scheduler = DemurrageScheduler(debug=debug_mode)
    
    # Get cron expression from env or use default (Tuesdays at 13:00 UTC)
    cron_expr = os.getenv('DEMURRAGE_CRON', '0 13 * * 2')
    scheduler.start(cron_expr) 