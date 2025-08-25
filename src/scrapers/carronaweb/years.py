import httpx
import asyncio
import unicodedata
from lxml import html
from fake_useragent import UserAgent
from src.logger.logger import get_logger
from src.utils.carroweb.get_proxy import get_proxy

REFERENCE = 'carrosweb'
logger = get_logger('scraper_years', reference=REFERENCE)

def generate_headers_user_agent(automaker):
    ua = UserAgent()
    referer = f'https://www.carrosnaweb.com.br/catalogofabricante.asp?fabricante={automaker}'

    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
        'Referer': referer,
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'DNT': '1',
        'Sec-GPC': '1',
        'Priority': 'u=0, i',
    }
    return headers

async def get_years(automaker, model):
    words_to_remove = [
        'Página Principal', 'Comparativo', 'Avaliação', 'Notícias', 'Opinião do Dono', 'Concessionárias',
        'Ranking', 'Carros Mais Vendidos', 'Todos', 'Hatchback', 'Sedã', 'Perua', 'Minivan', 'Cupê',
        'Conversível', 'SUV', 'Picape', 'Van', 'Furgão', 'Jipe', 'Chassi-cabine', 'Mapa do site',
        'Sobre o site', 'Privacidade', 'Termos de uso', 'Mobile', 'Fale Conosco', 'Comunicar erro',
        'Carros mais Vendidos', 'Próximos Lançamentos', '\r\n\t\t', 'Comparativos', 'Versão Clássica'
    ]
    url = 'https://www.carrosnaweb.com.br/catalogomodelo.asp'
    headers = generate_headers_user_agent(automaker)
    model = ''.join(c for c in unicodedata.normalize('NFD', model) if not unicodedata.combining(c))
    params = {'fabricante': automaker, 'modelo': model}

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        try:
            response = await client.get(url)
            response_text = response.text

            if response.status_code == 200:
                tree = html.fromstring(response_text)
                all_text = tree.xpath('//text()')
                if any('Ocorreu um erro.' in text for text in all_text):
                    logger.warning('CAPTCHA found in response, trying with proxies')
                    try:
                        response_text = await get_proxy(url, headers, params)
                        tree = html.fromstring(response_text)
                    except Exception as proxy_e:
                        logger.warning(f'Failed to attempt with proxies after CAPTCHA: {proxy_e}')
                        return []

                years = tree.xpath('//a/font/text()')
                years = [year.lower() for year in years if year not in words_to_remove]
                return years

            elif response.status_code == 403:
                logger.warning('Status_code: 403 - Blocked, trying with proxies')
                try:
                    response_text = await get_proxy(url, headers, params)
                    tree = html.fromstring(response_text)
                    years = tree.xpath('//a/font/text()')
                    years = [year.lower() for year in years if year not in words_to_remove]
                    return years
                except Exception as proxy_e:
                    logger.warning(f'Failed to try with proxies after 403: {proxy_e}')
                    return []

            else:
                logger.warning(f'Initial error {response.status_code}. Trying with proxies')
                try:
                    response_text = await get_proxy(url, headers, params)
                    tree = html.fromstring(response_text)
                    years = tree.xpath('//a/font/text()')
                    years = [year.lower() for year in years if year not in words_to_remove]
                    return years
                except Exception as proxy_e:
                    logger.warning(f'Failed to attempt with proxies after error {response.status_code}: {proxy_e}')
                    return []

        except httpx.RequestError as e:
            logger.warning(f'httpx request error on initial request: {e}')
            logger.info('Trying with proxies due to initial error')
            try:
                response_text = await get_proxy(url, headers, params)
                tree = html.fromstring(response_text)
                years = tree.xpath('//a/font/text()')
                years = [year.lower() for year in years if year not in words_to_remove]
                return years
            except Exception as proxy_e:
                logger.warning(f'Failed to try with proxies after initial error: {proxy_e}')
                return []

        except asyncio.TimeoutError:
            logger.warning('Timeout on initial request')
            logger.info('Trying with proxies due to initial timeout')
            try:
                response_text = await get_proxy(url, headers, params)
                tree = html.fromstring(response_text)
                years = tree.xpath('//a/font/text()')
                years = [year.lower() for year in years if year not in words_to_remove]
                return years
            except Exception as proxy_e:
                logger.warning(f'Failed to attempt with proxies after initial timeout: {proxy_e}')
                return []

        except Exception as e:
            logger.warning(f'Unexpected error in main function: {e}')
            return []