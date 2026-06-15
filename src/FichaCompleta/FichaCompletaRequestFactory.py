from fake_useragent import UserAgent
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository
from src.Model.Response import Response

_ua = UserAgent()


class FichaCompletaRequestFactory:
    def __init__(self, network: NetworkManager, db: DatabaseRepository):
        self._network = network
        self._db = db
        self._base_url = 'https://www.fichacompleta.com.br'

    async def get_automakers(self) -> Response:
        url = f'{self._base_url}/carros/marcas/'
        return await self._fetch(url, referer=f'{self._base_url}/carros/')

    async def get_models(self, automaker: str) -> Response:
        url = f'{self._base_url}/carros/{automaker}/'
        return await self._fetch(url, referer=f'{self._base_url}/carros/marcas/')

    async def get_version_years(self, automaker: str, model: str) -> Response:
        model = self._normalize(model)
        url = f'{self._base_url}/carros/{automaker}/{model}/'
        return await self._fetch(url, referer=f'{self._base_url}/carros/{automaker}/')

    async def get_technical_sheet(self, automaker: str, model: str, href: str) -> Response:
        model = self._normalize(model)
        url = f'{self._base_url}{href}'
        return await self._fetch(url, referer=f'{self._base_url}/carros/{automaker}/{model}/')

    async def _fetch(self, url: str, referer: str = '') -> Response:
        headers = self._headers(referer)
        response = await self._network.get(url=url, headers=headers)

        if not self._is_blocked(response):
            return response

        proxies = await self._db.get_proxies()
        for proxy in proxies:
            r = await self._network.get(url=url, headers=headers, proxy=proxy)
            if not self._is_blocked(r):
                return r

        return response

    @staticmethod
    def _is_blocked(response: Response) -> bool:
        if response.status != 200:
            return True
        if isinstance(response.content, str) and 'Digite o código:' in response.content:
            return True
        return False

    @staticmethod
    def _normalize(model: str) -> str:
        m = model.replace('.', '-').replace(':', '-').replace(' ', '-')
        return m.rstrip('-')

    @staticmethod
    def _headers(referer: str) -> dict:
        return {
            'User-Agent': _ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer': referer,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        }
