from ..proxy import get_proxy
from lxml import html

REFERENCE = 'fichacompleta'

def captcha_checker(response_text: str) -> bool:
    tree = html.fromstring(response_text)
    return any('Digite o código:' in text for text in tree.xpath('//text()'))

async def get_proxy_fichacompleta(url, headers, max_retries=5):
    return await get_proxy(
        url=url,
        headers=headers,
        reference=REFERENCE,
        captcha_checker=captcha_checker,
        max_retries=max_retries,
    )