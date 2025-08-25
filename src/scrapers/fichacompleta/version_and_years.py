import httpx
import asyncio
import re
from lxml import html
from fake_useragent import UserAgent
from ...logger.logger import get_logger
from ...utils.fichacompleta.get_proxy import get_proxy_fichacompleta

REFERENCE = "fichacompleta"
logger = get_logger("scraper_version_and_years", reference=REFERENCE)


def generate_headers_user_agent(automaker: str) -> dict:
    """Gera headers com User-Agent aleatório e referer correto."""
    ua = UserAgent()
    referer = f"https://www.fichacompleta.com.br/carros/{automaker}/"

    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": referer,
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


def normalize_model_name(model: str) -> str:
    """Normaliza o nome do modelo para ser compatível com URL."""
    model = model.replace(".", "-").replace(":", "-").replace(" ", "-")
    return model[:-1] if model.endswith("-") else model


def extract_versions_and_years(tree) -> tuple[dict, list[str]]:
    """Extrai versões e anos da árvore HTML."""
    words_to_remove = ["Quem Somos", "Contato", "Política de Privacidade", "Ver mais"]
    versions = {}
    years = []

    for element in tree.xpath("//div/a[normalize-space(text())]"):
        text = element.text.strip()
        href = element.get("href", "").strip()

        if not href or any(word in text for word in words_to_remove):
            continue

        versions[text] = href

        year_match = re.match(r"^\d{4}", text)
        if year_match:
            year = year_match.group(0)
            if year not in ["Carregando", "Carregando..."]:
                years.append(year)

    return versions, years


async def fetch_with_fallback(url: str, headers: dict) -> str | None:
    """
    Tenta buscar conteúdo da URL, primeiro normal e depois com proxy se necessário.
    Retorna o HTML ou None em caso de falha.
    """
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                logger.warning("403 Forbidden - tentando com proxy")
            else:
                logger.warning(f"Erro {response.status_code} - tentando com proxy")
        except (httpx.RequestError, asyncio.TimeoutError) as e:
            logger.warning(f"Erro de requisição ({type(e).__name__}) - tentando com proxy: {e}")
        except Exception as e:
            logger.warning(f"Erro inesperado ao buscar {url}: {e}")
            return None

        try:
            return await get_proxy_fichacompleta(url, headers)
        except Exception as proxy_e:
            logger.warning(f"Falhou até com proxy: {proxy_e}")
            return None


async def get_version_years(automaker: str, model: str) -> tuple[dict, list[str]] | list:
    """Retorna dicionário de versões e lista de anos para um automaker/model."""
    model = normalize_model_name(model)
    url = f"https://www.fichacompleta.com.br/carros/{automaker}/{model}/"
    headers = generate_headers_user_agent(automaker)

    response_text = await fetch_with_fallback(url, headers)
    if not response_text:
        return []

    tree = html.fromstring(response_text)

    all_text = tree.xpath("//text()")
    if any("Digite o código:" in text for text in all_text):
        logger.warning("CAPTCHA detectado - tentando novamente com proxy")
        try:
            response_text = await get_proxy_fichacompleta(url, headers)
            tree = html.fromstring(response_text)
        except Exception as e:
            logger.warning(f"Falha ao tentar bypass do CAPTCHA: {e}")
            return []

    return extract_versions_and_years(tree)
