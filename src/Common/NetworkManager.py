import re
import timeit
import aiohttp
import curl_cffi
import fake_useragent
from yarl import URL
from typing import Any
from aiohttp import ClientSession
from contextlib import asynccontextmanager
from src.Model.Response import Response


def _charset_from_headers(headers) -> str:
    content_type = headers.get('content-type', '')
    match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
    return match.group(1) if match else 'latin-1'


class NetworkManager:
    """Single entry point for HTTP traffic, backed by aiohttp or by curl_cffi
    when a request needs browser impersonation."""

    def __init__(self, session: ClientSession, cffi_session: curl_cffi.AsyncSession):
        self._session = session
        self._cffi_session = cffi_session
        self._ua = fake_useragent.UserAgent()

    async def get(self, url: str, headers: dict | None = None, params: dict | None = None,
                  use_cffi: bool = False, proxy: str | None = None) -> Response:
        return await self._request('GET', url, headers=headers, params=params,
                                   use_cffi=use_cffi, proxy=proxy)

    async def get_bytes(self, url: str, headers: dict | None = None, params: dict | None = None,
                        use_cffi: bool = False, proxy: str | None = None) -> Response:
        return await self._request('GET', url, headers=headers, params=params,
                                   use_cffi=use_cffi, proxy=proxy, raw=True)

    async def post(self, url: str, headers: dict | None = None, params: dict | None = None,
                   data: Any | None = None, json: dict | None = None,
                   use_cffi: bool = False, proxy: str | None = None) -> Response:
        return await self._request('POST', url, headers=headers, params=params, data=data,
                                   json=json, use_cffi=use_cffi, proxy=proxy)

    def random_ua(self) -> str:
        return self._ua.random

    async def _request(self, method: str, url: str, headers: dict | None = None,
                       params: dict | None = None, data: Any | None = None,
                       json: dict | None = None, use_cffi: bool = False,
                       proxy: str | None = None, raw: bool = False) -> Response:
        start = timeit.default_timer()

        if use_cffi:
            proxies = {'https': proxy, 'http': proxy} if proxy else None
            r = await self._cffi_session.request(method, url, headers=headers, params=params,
                                                 data=data, json=json, proxies=proxies)
            content = r.content if raw else r.content.decode(_charset_from_headers(r.headers),
                                                             errors='replace')
            return Response(
                url=URL(str(r.url)),
                status=r.status_code,
                response_time=timeit.default_timer() - start,
                cookies=r.cookies,
                content=content,
                headers=r.headers,
            )

        async with self._session.request(method, url, headers=headers, params=params,
                                         data=data, json=json, proxy=proxy) as r:
            content = await r.read() if raw else await r.text(errors='replace')
            return Response(
                url=r.url,
                status=r.status,
                response_time=timeit.default_timer() - start,
                cookies=r.cookies,
                content=content,
                headers=r.headers,
            )

    @staticmethod
    @asynccontextmanager
    async def create(cffi_impersonate: str = 'chrome124'):
        async with aiohttp.ClientSession() as session:
            cffi_session = curl_cffi.AsyncSession(impersonate=cffi_impersonate)
            try:
                yield NetworkManager(session, cffi_session)
            finally:
                await cffi_session.close()
