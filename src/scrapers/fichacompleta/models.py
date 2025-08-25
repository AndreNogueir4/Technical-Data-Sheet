import httpx
import asyncio
from lxml import html
from unidecode import unidecode
from fake_useragent import UserAgent
from ...logger.logger import get_logger
from ...utils.fichacompleta.get_proxy import get_proxy_fichacompleta
from typing import List, Optional

REFERENCE = "fichacompleta"
logger = get_logger("scraper_models", reference=REFERENCE)

WORDS_TO_REMOVE = {"Quem Somos", "Contato", "Política de Privacidade", "Ver mais"}

UA = UserAgent()


def generate_headers_user_agent() -> dict:
    """Gera headers com User-Agent randômico"""
    return {
        "Host": "www.fichacompleta.com.br",
        "Sec-Ch-Ua": '"Chromium";v="127", "Not)A;Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Accept-Language": "pt-BR",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": UA.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;"
        "q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Purpose": "prefetch",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://www.fichacompleta.com.br/carros/marcas/",
        "Priority": "u=4, i",
    }


def parse_models(html_text: str) -> List[str]:
    """Extrai e normaliza a lista de modelos do HTML."""
    tree = html.fromstring(html_text)
    models = tree.xpath("//div/a/text()")
    return [
        unidecode(model.lower().strip().replace(" ", "-"))
        for model in models
        if model.strip() and model.strip() not in WORDS_TO_REMOVE
    ]


async def fetch_with_proxy(url: str, headers: dict) -> Optional[List[str]]:
    """Tenta buscar o conteúdo via proxy e retorna lista de modelos."""
    try:
        response_text = await get_proxy_fichacompleta(url, headers)
        return parse_models(response_text)
    except Exception as e:
        logger.warning(f"Failed to fetch with proxies: {e}")
        return None


async def get_models(automaker: str) -> List[str]:
    """
    Obtém lista de modelos de uma montadora no site FichaCompleta.
    Se bloqueado ou der erro, tenta automaticamente com proxies.
    """
    url = f"https://www.fichacompleta.com.br/carros/{automaker}/"
    headers = generate_headers_user_agent()

    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            response = await client.get(url)

        if response.status_code == 200:
            tree = html.fromstring(response.text)
            if any("Digite o código:" in text for text in tree.xpath("//text()")):
                logger.warning("⚠️ CAPTCHA detected, retrying with proxy...")
                return await fetch_with_proxy(url, headers) or []
            return parse_models(response.text)

        elif response.status_code == 403:
            logger.warning("⚠️ Blocked with 403, retrying with proxy...")
            return await fetch_with_proxy(url, headers) or []

        else:
            logger.warning(f"⚠️ Unexpected status {response.status_code}, retrying with proxy...")
            return await fetch_with_proxy(url, headers) or []

    except (httpx.RequestError, asyncio.TimeoutError) as e:
        logger.warning(f"⚠️ Request error: {e}, retrying with proxy...")
        return await fetch_with_proxy(url, headers) or []

    except Exception as e:
        logger.error(f"❌ Unexpected error in get_models: {e}")
        return []
