import httpx
import asyncio
from lxml import html
from fake_useragent import UserAgent
from ...logger.logger import get_logger
from ...utils.fichacompleta.get_proxy import get_proxy_fichacompleta
from typing import List, Tuple, Dict, Optional

REFERENCE = 'fichacompleta'
logger = get_logger('scraper_technical_sheet', reference=REFERENCE)

UA = UserAgent()

def generate_headers(automaker: str, model: str) -> dict:
    """ Gera headers com User-Agent randômico """
    return {
        "User-Agent": UA.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": f"https://www.fichacompleta.com.br/carros/{automaker}/{model}/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
        "Sec-GPC": "1",
        "Priority": "u=0, i",
    }

def parse_technical_sheet(html_text: str) -> Tuple[Dict[str, str], List[str]]:
    """ Extrai ficha técnica e lista de equipamentos do HTML """
    tree = html.fromstring(html_text)

    keys = tree.xpath('//div[1]/b/text()')
    values = [value.strip() for value in tree.xpath('//div[2]/text()') if value.strip()]
    technical_data = {title: value for title, value in zip(keys, values)}

    equipments = [equip.strip() for equip in tree.xpath('//li/span/text()') if equip.strip()]
    if not equipments:
        equipments = ['Equipment not listed for this model']

    return technical_data, equipments

async def fetch_with_proxy(url: str, headers: dict) -> Optional[Tuple[Dict[str, str], List[str]]]:
    """ Tenta buscar a ficha técnica com proxy """
    try:
        response_text = await get_proxy_fichacompleta(url, headers)
        return parse_technical_sheet(response_text)
    except Exception as e:
        logger.warning(f'⚠️ Failed to fetch with proxies: {e}')
        return None

async def get_technical_sheet(automaker: str, model: str, href: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Obtém a ficha técnica e lista de equipamentos
    Se bloqueado ou ocorrer erro, tenta automaticamente com proxy
    """
    url = f'https://www.fichacompleta.com.br{href}'
    headers = generate_headers(automaker, model)

    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            response = await client.get(url)

        if response.status_code == 200:
            tree = html.fromstring(response.text)
            if any('Digite o código:' in text for text in tree.xpath('//text()')):
                logger.warning('⚠️ CAPTCHA detected, retrying with proxy...')
                return await fetch_with_proxy(url, headers) or ({}, [])
            return parse_technical_sheet(response.text)

        elif response.status_code == 403:
            logger.warning('⚠️ Blocked with 403, retrying with proxy...')
            return await fetch_with_proxy(url, headers) or ({}, [])

        else:
            logger.warning(f'⚠️ Unexpected status {response.status_code}, retrying with proxy...')
            return await fetch_with_proxy(url, headers) or ({}, [])

    except (httpx.RequestError, asyncio.TimeoutError) as e:
        logger.warning(f'⚠️ Request/Timeout error: {e}, retrying with proxy...')
        return await fetch_with_proxy(url, headers) or ({}, [])

    except Exception as e:
        logger.error(f'❌ Unexpected error in get_technical_sheet: {e}')
        return {}, []