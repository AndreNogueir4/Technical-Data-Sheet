import httpx
import asyncio
import unicodedata
import re
from lxml import html
from fake_useragent import UserAgent
from src.logger.logger import get_logger
from src.utils.carroweb.get_proxy import get_proxy

REFERENCE = 'carrosweb'
logger = get_logger('scraper_years', reference=REFERENCE)

def generate_headers_user_agent():
    ua = UserAgent()
    headers = {
        'Host': 'www.carrosnaweb.com.br',
        'Sec-Ch-Ua': '"Chromium";v="127", "Not)A;Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Accept-Language': 'pt-BR',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;'
                  'q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Priority': 'u=0, i',
        'Connection': 'keep-alive',
    }
    return headers

async def get_versions_link(automaker, model, year):
    url = 'https://www.carrosnaweb.com.br/m/catalogo.asp'
    headers = generate_headers_user_agent()
    model = ''.join(c for c in unicodedata.normalize('NFD', model) if not unicodedata.combining(c))
    params = {'fabricante': automaker, 'varnome': model, 'anoini': year, 'anofim': year}

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

                links = tree.xpath('//font/a')
                versions = {}

                for link in links:
                    href = link.get('href')
                    text = link.text_content().strip()
                    text = re.sub(r'\s+', ' ', text).strip()
                    if href and text and href.startswith('fichadetalhe.aps?codigo'):
                        versions[text] = href
                return versions

            elif response.status_code == 403:
                logger.warning('Status_code: 403 - Blocked, trying with proxies')
                try:
                    response_text = await get_proxy(url, headers, params)
                    tree = html.fromstring(response_text)
                    links = tree.xpath('//font/a')
                    versions = {}

                    for link in links:
                        href = link.get('href')
                        text = link.text_content().strip()
                        text = re.sub(r'\s+', ' ', text).strip()
                        if href and text and href.startswith('fichadetalhe.aps?codigo'):
                            versions[text] = href
                    return versions
                except Exception as proxy_e:
                    logger.warning(f'Failed to try with proxies after 403: {proxy_e}')
                    return []

            else:
                logger.warning(f'Initial error {response.status_code}. Trying with proxies')
                try:
                    response_text = await get_proxy(url, headers, params)
                    tree = html.fromstring(response_text)
                    links = tree.xpath('//font/a')
                    versions = {}

                    for link in links:
                        href = link.get('href')
                        text = link.text_content().strip()
                        text = re.sub(r'\s+', ' ', text).strip()
                        if href and text and href.startswith('fichadetalhe.aps?codigo'):
                            versions[text] = href
                    return versions
                except Exception as proxy_e:
                    logger.warning(f'Failed to attempt with proxies after error {response.status_code}: {proxy_e}')
                    return []

        except httpx.RequestError as e:
            logger.warning(f'httpx request error on initial request: {e}')
            logger.info('Trying with proxies due to initial error')
            try:
                response_text = await get_proxy(url, headers, params)
                tree = html.fromstring(response_text)
                links = tree.xpath('//font/a')
                versions = {}

                for link in links:
                    href = link.get('href')
                    text = link.text_content().strip()
                    text = re.sub(r'\s+', ' ', text).strip()
                    if href and text and href.startswith('fichadetalhe.aps?codigo'):
                        versions[text] = href
                return versions
            except Exception as proxy_e:
                logger.warning(f'Failed to try with proxies after initial error: {proxy_e}')
                return []

        except asyncio.TimeoutError:
            logger.warning('Timeout on initial request')
            logger.info('Trying with proxies due to initial timeout')
            try:
                response_text = await get_proxy(url, headers, params)
                tree = html.fromstring(response_text)
                links = tree.xpath('//font/a')
                versions = {}

                for link in links:
                    href = link.get('href')
                    text = link.text_content().strip()
                    text = re.sub(r'\s+', ' ', text).strip()
                    if href and text and href.startswith('fichadetalhe.aps?codigo'):
                        versions[text] = href
                return versions
            except Exception as proxy_e:
                logger.warning(f'Failed to attempt with proxies after initial timeout: {proxy_e}')
                return []

        except Exception as e:
            logger.warning(f'Unexpected error in main function: {e}')
            return []