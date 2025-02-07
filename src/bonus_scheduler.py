import logging
from bonus_service import BonusService
from base_scheduler import BaseScheduler

class BonusScheduler(BaseScheduler):
    def __init__(self, config_file: str, debug: bool = False):
        super().__init__(debug)
        self.config_file = config_file

    def run_job(self):
        try:
            service = BonusService(self.config_file)
            service.execute_distribution()
        except Exception as e:
            self.logger.error(f"Error in bonus job: {e}", exc_info=True)

if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv

    if len(sys.argv) != 2:
        print("Usage: python scheduler.py <config_file>")
        sys.exit(1)

    load_dotenv('/app/.env.bonus')
    scheduler = BonusScheduler(sys.argv[1], debug=os.getenv('DEBUG', 'false').lower() == 'true')
    
    # Get cron expression from env or use default
    cron_expr = os.getenv('BONUS_CRON', '* * * * *')
    scheduler.start(cron_expr)