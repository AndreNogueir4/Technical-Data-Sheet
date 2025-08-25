from ..proxy import get_proxy
from lxml import html

REFERENCE = 'carroweb'

def captcha_checker(response_text: str) -> bool:
    tree = html.fromstring(response_text)
    return any('Ocorreu um erro' in text for text in tree.xpath('//text()'))

async def get_proxy_carroweb(url, headers, params=None, max_retries=5):
    return await get_proxy(
        url=url,
        headers=headers,
        reference=REFERENCE,
        captcha_checker=captcha_checker,
        params=params,
        max_retries=max_retries,
    )