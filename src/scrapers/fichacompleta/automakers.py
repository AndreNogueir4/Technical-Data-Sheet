import httpx
import asyncio
from lxml import html
from unidecode import unidecode
from fake_useragent import UserAgent
from ...logger.logger import get_logger
from ...utils.fichacompleta.get_proxy import get_proxy_fichacompleta
from typing import List, Optional

REFERENCE = 'fichacompleta'
logger = get_logger('scraper_automakers', reference=REFERENCE)

WORDS_TO_REMOVE = {'Quem Somos', 'Contato', 'Política de Privacidade', 'Ver mais'}

UA = UserAgent()

def generate_headers() -> dict:
    """ Gera headers com User-Agent randômico """
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;"
                  "q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "cache-control": "max-age=0",
        "priority": "u=0, i",
        "referer": "https://www.fichacompleta.com.br/carros/",
        "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": UA.random,
    }

def parse_automakers(html_text: str) -> List[str]:
    """ Extrai e normaliza a lista de montadoras do HTML """
    tree = html.fromstring(html_text)
    automakers = tree.xpath('//div/a/text()')
    return [
        unidecode(maker.lower().strip().replace(' ', '-'))
        for maker in automakers
        if maker.strip() and maker.strip() not in WORDS_TO_REMOVE
    ]

async def fetch_with_proxy(url: str, headers: dict) -> Optional[List[str]]:
    """ Tenta buscar o conteúdo via proxy e retorna lista de automakers """
    try:
        response_text = await get_proxy_fichacompleta(url, headers)
        return parse_automakers(response_text)
    except Exception as e:
        logger.warning(f'Failed to fetch with proxies: {e}')
        return None

async def get_automakers() -> List[str]:
    """
    Obtém lista de montadoras do site FichaCompleta
    Se bloqueado ou der erro, tenta automaticamente com proxies
    """
    url = 'https://www.fichacompleta.com.br/carros/marcas/'
    headers = generate_headers()

    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            response = await client.get(url)

        if response.status_code == 200:
            tree = html.fromstring(response.text)
            if any('Digite o código:' in text for text in tree.xpath('//text()')):
                logger.warning('⚠️ CAPTCHA detected, retrying with proxy...')
                return await fetch_with_proxy(url, headers) or []
            return parse_automakers(response.text)

        elif response.status_code == 403:
            logger.warning('⚠️ Blocked with 403, retrying with proxy...')
            return await fetch_with_proxy(url, headers) or []

        else:
            logger.warning(f'⚠️ Unexpected status {response.status_code}, retrying with proxy...')
            return await fetch_with_proxy(url, headers) or []

    except (httpx.RequestError, asyncio.TimeoutError) as e:
        logger.warning(f'⚠️ Request error: {e}, retrying with proxy...')
        return await fetch_with_proxy(url, headers) or []

    except Exception as e:
        logger.error(f'❌ Unexpected error in get_automakers: {e}')
        return []