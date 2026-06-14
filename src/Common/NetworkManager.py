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
    m = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
    return m.group(1) if m else 'latin-1'


class NetworkManager:
    def __init__(self, session: ClientSession, cffi_session: curl_cffi.AsyncSession | None = None,
        responses: list | None = None):
        self._session = session
        self._cffi_session = cffi_session or curl_cffi.AsyncSession(impersonate="chrome124")
        self._responses = responses if responses is not None else []
        self._ua = fake_useragent.UserAgent()

    async def get(self, url: str, headers: dict | None = None, params: dict | None = None,
                  use_cffi: bool = False, proxy: str | None = None) -> Response:
        start = timeit.default_timer()
        if use_cffi:
            proxies = {'https': proxy, 'http': proxy} if proxy else None
            r = await self._cffi_session.get(url, headers=headers, params=params, proxies=proxies)
            elapsed = timeit.default_timer() - start
            response = Response(
                url=URL(str(r.url)),
                status=r.status_code,
                response_time=elapsed,
                cookies=r.cookies,
                content=r.content.decode(_charset_from_headers(r.headers), errors='replace'),
                headers=r.headers,
            )
        else:
            async with self._session.get(url, headers=headers, params=params, proxy=proxy) as r:
                elapsed = timeit.default_timer() - start
                response = Response(
                    url=r.url,
                    status=r.status,
                    response_time=elapsed,
                    cookies=r.cookies,
                    content=await r.text(errors='replace'),
                    headers=r.headers,
                )

        self._responses.append(response)
        return response

    async def post(self, url: str, headers: dict | None = None, params: dict | None = None,
                   data: Any | None = None, json: dict | None = None,
                   use_cffi: bool = False, proxy: str | None = None) -> Response:
        start = timeit.default_timer()
        if use_cffi:
            proxies = {'https': proxy, 'http': proxy} if proxy else None
            r = await self._cffi_session.post(url, headers=headers, params=params, data=data, json=json,
                                              proxies=proxies)
            elapsed = timeit.default_timer() - start
            response = Response(
                url=URL(str(r.url)),
                status=r.status_code,
                response_time=elapsed,
                cookies=r.cookies,
                content=r.content.decode(_charset_from_headers(r.headers), errors='replace'),
                headers=r.headers,
            )
        else:
            async with self._session.post(url, headers=headers, params=params, data=data, json=json,
                                          proxy=proxy) as r:
                elapsed = timeit.default_timer() - start
                response = Response(
                    url=r.url,
                    status=r.status,
                    response_time=elapsed,
                    cookies=r.cookies,
                    content=await r.text(errors='replace'),
                    headers=r.headers,
                )

        self._responses.append(response)
        return response

    async def get_bytes(self, url: str, headers: dict | None = None, params: dict | None = None,
                        use_cffi: bool = False, proxy: str | None = None) -> Response:
        start = timeit.default_timer()
        if use_cffi:
            proxies = {'https': proxy, 'http': proxy} if proxy else None
            r = await self._cffi_session.get(url, headers=headers, params=params, proxies=proxies)
            elapsed = timeit.default_timer() - start
            response = Response(
                url=URL(str(r.url)),
                status=r.status_code,
                response_time=elapsed,
                cookies=r.cookies,
                content=r.content,
                headers=r.headers,
            )
        else:
            async with self._session.get(url, headers=headers, params=params, proxy=proxy) as r:
                elapsed = timeit.default_timer() - start
                response = Response(
                    url=r.url,
                    status=r.status,
                    response_time=elapsed,
                    cookies=r.cookies,
                    content=await r.read(),
                    headers=r.headers,
                )
        self._responses.append(response)
        return response

    def random_ua(self) -> str:
        return self._ua.random

    @staticmethod
    @asynccontextmanager
    async def create(cffi_impersonate: str = "chrome124"):
        async with aiohttp.ClientSession() as session:
            cffi_session = curl_cffi.AsyncSession(impersonate=cffi_impersonate)
            try:
                yield NetworkManager(session, cffi_session)
            finally:
                await cffi_session.close()
