import logging
from bonus_service import BonusService
from base_scheduler import BaseScheduler
import argparse

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

    def run_once(self):
        """Execute the job once and exit"""
        self.run_job()

if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description='Bonus distribution service')
    parser.add_argument('config_file', help='Path to the configuration file')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit (no scheduling)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--env-file', default='/app/.env.bonus', help='Path to environment file')
    args = parser.parse_args()

    load_dotenv(args.env_file)
    scheduler = BonusScheduler(args.config_file, debug=args.debug or os.getenv('DEBUG', 'false').lower() == 'true')
    
    if args.run_once:
        scheduler.run_once()
    else:
        # Get cron expression from env or use default
        cron_expr = os.getenv('BONUS_CRON', '* * * * *')
        scheduler.start(cron_expr)