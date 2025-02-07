import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from abc import ABC, abstractmethod

class BaseScheduler(ABC):
    def __init__(self, debug: bool = False):
        self.scheduler = BlockingScheduler()
        self.logger = logging.getLogger(__name__)
        self.debug = debug

    @abstractmethod
    def run_job(self):
        """Abstract method that should be implemented by child classes to run the scheduled job"""
        pass

    def start(self, cron_expression: str):
        """Start the scheduler with the given cron expression"""
        self.scheduler.add_job(
            self.run_job,
            CronTrigger.from_crontab(cron_expression),
            name=f'{self.__class__.__name__}_job',
            max_instances=1
        )
        
        try:
            self.logger.info(f"Starting scheduler with cron: {cron_expression}")
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown() 