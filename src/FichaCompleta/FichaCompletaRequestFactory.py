from src.Model.Response import Response
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository


class FichaCompletaRequestFactory:
    def __init__(self, network: NetworkManager, db: DatabaseRepository,
                 base_url: str = 'https://www.fichacompleta.com.br'):
        self._network = network
        self._db = db
        self._base_url = base_url

    def model_url(self, automaker: str, model: str) -> str:
        return f'{self._base_url}/carros/{automaker}/{self._normalize(model)}/'

    async def get_automakers(self) -> Response:
        return await self._fetch(f'{self._base_url}/carros/marcas/',
                                 referer=f'{self._base_url}/carros/')

    async def get_models(self, automaker: str) -> Response:
        return await self._fetch(f'{self._base_url}/carros/{automaker}/',
                                 referer=f'{self._base_url}/carros/marcas/')

    async def get_version_years(self, automaker: str, model: str) -> Response:
        return await self._fetch(self.model_url(automaker, model),
                                 referer=f'{self._base_url}/carros/{automaker}/')

    async def get_technical_sheet(self, automaker: str, model: str, href: str) -> Response:
        return await self._fetch(f'{self._base_url}{href}',
                                 referer=self.model_url(automaker, model))

    async def _fetch(self, url: str, referer: str = '') -> Response:
        """Try a direct request first, then fall back to the proxy pool when blocked."""
        headers = self._headers(referer)
        response = await self._network.get(url=url, headers=headers)

        if not self._is_blocked(response):
            return response

        for proxy in await self._db.get_proxies():
            retry = await self._network.get(url=url, headers=headers, proxy=proxy)
            if not self._is_blocked(retry):
                return retry

        return response

    @staticmethod
    def _is_blocked(response: Response) -> bool:
        """Bloqueio é o que vale a pena repetir por proxy.

        Um 404 não é: a referência morreu e vai morrer igual em todos os proxies —
        quem trata disso é o `invalid` do crawler.
        """
        if response.status in (404, 410):
            return False
        if response.status != 200:
            return True
        return isinstance(response.content, str) and 'Digite o código:' in response.content

    @staticmethod
    def _normalize(model: str) -> str:
        return model.replace('.', '-').replace(':', '-').replace(' ', '-').rstrip('-')

    def _headers(self, referer: str) -> dict:
        return {
            'User-Agent': self._network.random_ua(),
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
