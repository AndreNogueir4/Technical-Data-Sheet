import logging
import sys
import colorlog
from src.Logger.Handlers import MongoDBHandler
from src.Logger.Formatter import get_formatter

_cache: dict[str, logging.Logger] = {}


def get_logger(name: str = 'scraper', reference: str | None = None) -> logging.Logger:
    cache_key = f'{name}:{reference}'
    if cache_key in _cache:
        return _cache[cache_key]

    logger = logging.getLogger(cache_key)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    is_test = any('pytest' in arg for arg in sys.argv)

    stream_handler = colorlog.StreamHandler()
    stream_handler.setFormatter(get_formatter(is_test))
    logger.addHandler(stream_handler)

    mongo_handler = MongoDBHandler(reference=reference)
    mongo_handler.setLevel(logging.DEBUG)
    logger.addHandler(mongo_handler)

    _cache[cache_key] = logger
    return logger
