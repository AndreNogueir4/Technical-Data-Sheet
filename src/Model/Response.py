from yarl import URL
from typing import Any, ClassVar
from collections.abc import Mapping
from dataclasses import dataclass, fields
from http.cookies import SimpleCookie


@dataclass
class Response:
    """A resposta HTTP, igual para os dois backends do `NetworkManager`.

    O aiohttp e o curl_cffi devolvem tipos diferentes para headers e cookies — os dois
    são `Mapping`, e é por aí que `to_dict` os normaliza.
    """

    # Não vão para o log: cookie é credencial.
    HIDDEN: ClassVar[tuple[str, ...]] = ('cookies',)

    url: URL | None = None
    status: int | None = 200
    response_time: float | None = 0.0
    cookies: SimpleCookie[str] | Mapping[str, str] | None = None
    content: str | bytes | None = None
    headers: Mapping[str, str] | None = None

    def to_dict(self) -> dict:
        """Uma cópia serializável da resposta, para log e depuração."""
        return {
            field.name: self._parse(getattr(self, field.name))
            for field in fields(self)
            if field.name not in self.HIDDEN
        }

    @staticmethod
    def _parse(item: Any) -> Any:
        if isinstance(item, URL):
            return str(item)
        if isinstance(item, bytes):
            return None
        if isinstance(item, Mapping):
            return dict(item)
        return item

    def __repr__(self):
        return repr(self.to_dict())
