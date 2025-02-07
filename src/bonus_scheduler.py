import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bonus_service import BonusService

class BonusScheduler:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.scheduler = BlockingScheduler()
        self.logger = logging.getLogger(__name__)

    def run_bonus_job(self):
        try:
            service = BonusService(self.config_file)
            service.execute_distribution()
        except Exception as e:
            self.logger.error(f"Error in bonus job: {e}", exc_info=True)

    def start(self, cron_expression: str = "* * * * *"):  # Default: every minute
        self.scheduler.add_job(
            self.run_bonus_job,
            CronTrigger.from_crontab(cron_expression),
            name='bonus_job',
            max_instances=1
        )
        
        try:
            self.logger.info(f"Starting scheduler with cron: {cron_expression}")
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()

if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv

    if len(sys.argv) != 2:
        print("Usage: python scheduler.py <config_file>")
        sys.exit(1)

    load_dotenv('/app/.env.bonus')
    scheduler = BonusScheduler(sys.argv[1])
    
    # Get cron expression from env or use default
    cron_expr = os.getenv('BONUS_CRON', '* * * * *')
    scheduler.start(cron_expr)