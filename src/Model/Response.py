import httpx
from yarl import URL
from httpx import Cookies
from dataclasses import dataclass
from http.cookies import SimpleCookie
from multidict import CIMultiDictProxy


@dataclass
class Response:
    url: URL | None = None
    status: int | None = 200
    response_time: float | None = 0.0
    cookies: SimpleCookie[str] | Cookies | None = None
    content: str | dict | bytes | None = None
    headers: CIMultiDictProxy[str] | None = None

    def to_dict(self):
        items = {}
        for key, value in vars(self).items():
            if key in ['status', 'response_time']:
                items[key] = value
            elif key != 'cookies':
                item = self._dict_parse(value)
                items[key] = item
        return items

    def _dict_parse(self, item):
        if type(item) is URL or type(item) is httpx.URL:
            return str(item)
        if type(item) is CIMultiDictProxy:
            return dict(item)
        if isinstance(self.content, bytes):
            return None
        if isinstance(self.content, dict):
            return self._dict_content_parse(self.content)
        return item

    def _dict_content_parse(self, item):
        for key, value in item.items():
            if isinstance(value, dict):
                item[key] = self._dict_content_parse(value)
            elif isinstance(value, int):
                if self._is_large_int(value):
                    item[key] = str(value)
        return item

    def _is_large_int(self, value: int):
        if value == 0:
            return False
        num_bits = value.bit_length()
        num_bytes = (num_bits + 7) // 8
        return num_bytes > 8

    def __repr__(self):
        return repr(self.to_dict())
