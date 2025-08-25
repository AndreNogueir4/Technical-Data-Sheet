import asyncio
from ..logger.logger import get_logger

logger = get_logger('commons', 'commons')

async def validate_scraper_data(data, data_name, scraper_name):
    if not data:
        logger.error(f'⚠️ Empty data from scraper={scraper_name}, data_name={data_name}')
        return False
    return True

async def safe_gather(*tasks, return_exceptions=True):
    """
    Executa gather mas loga as exceptions sem quebrar o pipelina inteiro
    """
    results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    for r in results:
        if isinstance(r, Exception):
            logger.error(f'Task failed: {r}')
    return results