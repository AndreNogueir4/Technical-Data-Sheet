import logging
import asyncio
from .repository import LogRepository


class MongoDBHandler(logging.Handler):
    """ Handler que envia logs para o MongoDB """
    def __init__(self, reference=None):
        super().__init__()
        self.reference = reference
        self.repo = LogRepository()

    def emit(self, record):
        message = self.format(record)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.repo.insert_log(record.levelname, message, self.reference))
        except RuntimeError:
            asyncio.run(self.repo.insert_log(record.levelname, message, self.reference))