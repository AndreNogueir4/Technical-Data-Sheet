import logging
import sys
import colorlog
from .handlers import MongoDBHandler
from .formatter import get_formatter

_logger_cache = {}

def get_logger(name: str = 'scraper', reference: str = None):
    """
    Retorna um logger com saída colorida no terminal e envio de logs para o Banco
    O campo 'reference' indica de qual site o log se origina
    """
    cache_key = f'{name}:{reference}'
    if cache_key in _logger_cache:
        return _logger_cache[cache_key]

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

    _logger_cache[cache_key] = logger
    return logger