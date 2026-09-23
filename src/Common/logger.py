import sys
import asyncio
import logging
import colorlog
from datetime import datetime
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

_LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}
_TEST_LOG_COLORS = {level: 'bold_purple' for level in _LOG_COLORS}


class MongoLogHandler(logging.Handler):
    """Mirrors every record into the `logs` collection — the only log this app keeps.

    Inside the event loop the insert is fired off as a task, so crawling never waits on
    the database. Outside of it (startup, shutdown, the crash handler) there is no loop
    to schedule on, and a dropped record there is exactly the one worth having, so those
    go through a blocking client instead.
    """

    def __init__(self, uri: str, db_name: str, reference: str | None = None):
        super().__init__()
        self._uri = uri
        self._db_name = db_name
        self._reference = reference
        self._collection = AsyncIOMotorClient(uri)[db_name].logs
        self._sync_collection = None
        self._tasks: set[asyncio.Task] = set()

    def emit(self, record: logging.LogRecord) -> None:
        document = self._document(record)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._insert_blocking(document, record)
            return

        task = loop.create_task(self._insert(document, record))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def pending(self) -> tuple[asyncio.Task, ...]:
        """Inserts still in flight, for callers that must not exit before they land."""
        return tuple(self._tasks)

    def _document(self, record: logging.LogRecord) -> dict:
        now = datetime.now()
        return {
            'level': record.levelname,
            'message': self.format(record),
            'reference': self._reference,
            'date': now.strftime('%d-%m-%Y'),
            'time': now.strftime('%H:%M:%S'),
        }

    async def _insert(self, document: dict, record: logging.LogRecord) -> None:
        try:
            await self._collection.insert_one(document)
        except Exception:
            self.handleError(record)

    def _insert_blocking(self, document: dict, record: logging.LogRecord) -> None:
        try:
            if self._sync_collection is None:
                self._sync_collection = MongoClient(self._uri)[self._db_name].logs
            self._sync_collection.insert_one(document)
        except Exception:
            self.handleError(record)


class LoggerFactory:
    """Builds configured loggers. One instance per application, injected where needed."""

    def __init__(self, mongo_uri: str | None = None, db_name: str = 'technical_sheet',
                 level: int = logging.DEBUG, colored: bool | None = None):
        self._mongo_uri = mongo_uri
        self._db_name = db_name
        self._level = level
        self._is_test = colored if colored is not None else any('pytest' in arg for arg in sys.argv)
        self._cache: dict[str, logging.Logger] = {}

    def get(self, name: str = 'scraper', reference: str | None = None) -> logging.Logger:
        key = f'{name}:{reference}'
        if key in self._cache:
            return self._cache[key]

        logger = logging.getLogger(key)
        logger.setLevel(self._level)
        logger.propagate = False
        logger.handlers.clear()

        stream = colorlog.StreamHandler()
        stream.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] - %(message)s',
            log_colors=_TEST_LOG_COLORS if self._is_test else _LOG_COLORS,
        ))
        logger.addHandler(stream)

        if self._mongo_uri:
            mongo = MongoLogHandler(self._mongo_uri, self._db_name, reference)
            mongo.setLevel(self._level)
            logger.addHandler(mongo)

        self._cache[key] = logger
        return logger

    async def drain(self) -> None:
        """Wait for the in-flight Mongo writes.

        `asyncio.run` cancels whatever is still pending when the loop closes, which is
        exactly the tail of the run — the final counts, the reason it stopped.
        """
        pending = [
            task
            for logger in self._cache.values()
            for handler in logger.handlers
            if isinstance(handler, MongoLogHandler)
            for task in handler.pending()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    __call__ = get
