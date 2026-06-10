from src.Common.NetworkManager import NetworkManager
from src.Model.Response import Response


class CarrosWebRequestFactory:
    def __init__(self, network: NetworkManager):
        self._network = network
        self._base_url = 'https://www.carrosnaweb.com.br'
        self._headers = {'Host': 'www.carrosnaweb.com.br'}

    async def get_automakers(self) -> Response:
        return await self._network.get(
            url=f'{self._base_url}/avancada.asp',
            headers=self._headers,
            use_cffi=True
        )

    async def get_models(self, automaker: str) -> Response:
        params = {'fabricante': automaker}
        return await self._network.get(
            url=f'{self._base_url}/catalogofabricante.asp',
            params=params,
            headers=self._headers,
            use_cffi=True
        )

    async def get_years(self, automaker: str, model: str) -> Response:
        params = {'fabricante': automaker, 'modelo': model}
        return await self._network.get(
            url=f'{self._base_url}/catalogomodelo.asp',
            params=params,
            headers=self._headers,
            use_cffi=True
        )

    async def get_versions(self, automaker: str, model: str, start_year: str, final_year: str) -> Response:
        params = {'fabricante': automaker, 'varnome': model, 'anoini': start_year, 'anofim': final_year}
        return await self._network.get(
            url=f'{self._base_url}/catalogo.asp',
            params=params,
            headers=self._headers,
            use_cffi=True
        )

    async def get_technical_sheet(self, code: str) -> Response:
        params = {'codigo': code}
        return await self._network.get(
            url=f'{self._base_url}/fichadetalhe.asp',
            params=params,
            headers=self._headers,
            use_cffi=True
        )

    async def get_image_value(self, image_path: str) -> Response:
        """Fetch an anti-scraping image value (session-based, no explicit params needed)."""
        path = image_path.replace('\\', '/').lstrip('/')
        return await self._network.get_bytes(
            url=f'{self._base_url}/{path}',
            headers=self._headers,
            use_cffi=True
        )
