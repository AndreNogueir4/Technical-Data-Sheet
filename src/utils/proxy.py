import httpx
import asyncio
from ..commons.DatabaseRepository import DatabaseRepository
from ..logger.logger import get_logger

db = DatabaseRepository()

async def get_proxy(
    url: str,
    headers: dict,
    reference: str,
    captcha_checker,
    params: dict | None = None,
    max_retries: int = 5,
):
    """
    Faz requisição HTTP usando proxies obtidos do banco.

    Args:
        url (str): URL de destino.
        headers (dict): Headers para a requisição.
        reference (str): Nome do site (ex: 'carrosweb').
        captcha_checker (Callable): Função que recebe o texto da página e retorna True se for CAPTCHA.
        params (dict|None): Query params opcionais.
        max_retries (int): Número de tentativas por proxy.

    Raises:
        Exception: Se nenhum proxy funcionar.

    Returns:
        str: Conteúdo HTML da página.
    """
    logger = get_logger('get_proxy', reference=reference)
    PROXIES = await db.get_proxies()

    if not PROXIES:
        logger.warning('No proxy configured to try')
        raise Exception('Attempt to use proxies failed: No proxy provided')

    for proxy in PROXIES:
        proxy = proxy.strip()
        if not proxy.startswith(('http://', 'https://')):
            logger.warning(f'Invalid proxy format: {proxy}')
            continue

        proxy_dict = {'http://': proxy, 'https://': proxy}
        logger.info(f'Trying proxy: {proxy}')

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f'Attempt {attempt}/{max_retries} with proxy {proxy}')

                async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                    response = await client.get(url, params=params, proxies=proxy_dict)
                    response_text = response.text

                    if response.status_code == 200:
                        if captcha_checker(response_text):
                            logger.warning(f'CAPTCHA present with proxy: {proxy}')
                        return response_text
                    else:
                        logger.warning(f'Proxy {proxy} failed with status: {response.status_code}')

            except httpx.RequestError as e:
                logger.warning(f'Request error with proxy {proxy} (attempt {attempt}): {e}')
            except asyncio.TimeoutError:
                logger.warning(f'Timeout with proxy: {proxy} (attempt {attempt})')
            except Exception as e:
                logger.warning(f'Unexpected error with proxy {proxy} (attempt {attempt}): {e}')

            if attempt < max_retries:
                await asyncio.sleep(5)

        logger.warning(f'All attempts with proxy failed: {proxy}')
    raise Exception('All proxies failed, request could not be completed')
