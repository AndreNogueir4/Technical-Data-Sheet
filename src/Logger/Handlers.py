import logging
import asyncio
from src.Logger.Repository import LogRepository


class MongoDBHandler(logging.Handler):
    def __init__(self, reference: str | None = None):
        super().__init__()
        self.reference = reference
        self.repo = LogRepository()

    def emit(self, record: logging.LogRecord):
        message = self.format(record)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.repo.insert_log(record.levelname, message, self.reference))
        except RuntimeError:
            asyncio.run(self.repo.insert_log(record.levelname, message, self.reference))
