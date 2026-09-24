import asyncio
import logging
import timeit
import aiohttp
import traceback
import inspect
import ua_generator
from abc import abstractmethod
from typing import Any, Awaitable, Callable
from src.Model.Job import Job
from src.Model.JobStatus import JobStatus
from src.Model.Response import Response
from src.Common.exceptions import InvalidJobError
from src.Common.DatabaseRepository import DatabaseRepository
from typing import Tuple, List, Optional, Any


class Crawler:
    def __init__(self, website, concurrent=30, timeout=100, tcp_limit=90, try_limit=4):
        self.website = website
        self.database = DatabaseRepository.instance()
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(value=concurrent)
        self._tcp_limit = tcp_limit
        self._try_limit = try_limit

    # source: str = ''
    # dead_statuses: tuple[int, ...] = (404, 410)
    #
    # def __init__(self, website, db: DatabaseRepository, logger: logging.Logger,
    #              delay: tuple[float, float] = (10.0, 50.0), concurrency: int = 2,
    #              max_attempts: int = 3):
    #     self._db = db
    #     self._logger = logger
    #     self._delay = delay
    #     self._concurrency = max(1, concurrency)
    #     self._max_attempts = max_attempts

    # @property
    # def delay(self) -> tuple[float, float]:
    #     """Intervalo (min, max) em segundos que um worker espera entre dois jobs deste site."""
    #     return self._delay
    #
    # @property
    # def logger(self) -> logging.Logger:
    #     return self._logger
    #
    # @abstractmethod
    # async def catalog_phase(self) -> int:
    #     """Descobre veículos e enfileira um job por versão. Devolve quantos jobs são novos."""
    #
    # @abstractmethod
    # async def fetch_sheet(self, job: Job) -> dict:
    #     """Baixa e faz o parse da ficha técnica de um job."""
    #
    # async def crawl_task_with_job(self, job: Job) -> JobStatus:
    #     """Baixa a ficha de um job e fecha o job. Devolve o status em que ele ficou.
    #
    #     `done` quando a ficha foi salva, `invalid` quando a página respondeu mas não
    #     tem ficha nenhuma, `todo`/`error` quando a coleta falhou e cabe repetir.
    #     """
    #     try:
    #         sheet = await self.fetch_sheet(job)
    #     except InvalidJobError as error:
    #         return await self.invalidate(job, str(error))
    #
    #     if not sheet:
    #         return await self.requeue(job)
    #
    #     reason = self._invalid_reason(sheet)
    #     if reason:
    #         return await self.invalidate(job, reason)
    #
    #     await self._save(job, sheet)
    #     return job.status
    #
    # async def crawl_list(self, jobs: list[Job], raise_error: bool = True) -> list[dict]:
    #     """Baixa as fichas de uma lista de jobs sem passar pela fila.
    #
    #     Usado pelo `TechnicalSheet.get_list_result` — nada é persistido, as fichas
    #     voltam na mesma ordem dos jobs recebidos (um dict vazio onde falhou).
    #     """
    #     semaphore = asyncio.Semaphore(self._concurrency)
    #
    #     async def fetch(job: Job) -> dict:
    #         async with semaphore:
    #             try:
    #                 return await self.fetch_sheet(job)
    #             except asyncio.CancelledError:
    #                 raise
    #             except InvalidJobError as error:
    #                 self._logger.warning(f'crawl_list - {job.label}: {error}')
    #                 return {}
    #             except Exception:
    #                 self._logger.exception(f'crawl_list - {job.label} raised')
    #                 if raise_error:
    #                     raise
    #                 return {}
    #
    #     return list(await asyncio.gather(*(fetch(job) for job in jobs)))
    #
    # async def requeue(self, job: Job) -> JobStatus:
    #     """Devolve um job que falhou para a fila até ele esgotar as tentativas.
    #
    #     Uma falha costuma ser um bloqueio temporário (429, captcha), então o job volta
    #     para `todo` com o contador de tentativas somado — `pop_pending_jobs` serve os
    #     menos tentados primeiro, o que o joga para o fim da fila em vez de repeti-lo agora.
    #     """
    #     job.attempts += 1
    #
    #     if job.attempts < self._max_attempts:
    #         job.status = JobStatus.TODO
    #         await self._db.update_job(job.id, {'status': job.status.value, 'attempts': job.attempts})
    #         self._logger.warning(
    #             f'{job.label} - failed, requeued (attempt {job.attempts}/{self._max_attempts})')
    #         return job.status
    #
    #     job.status = JobStatus.ERROR
    #     await self._db.update_job(job.id, {'status': job.status.value, 'attempts': job.attempts})
    #     self._logger.warning(f'{job.label} - failed {job.attempts}x, marked as error')
    #     return job.status
    #
    # async def invalidate(self, job: Job, reason: str) -> JobStatus:
    #     """Fecha um job que nunca vai dar certo, sem gastar tentativa.
    #
    #     É o caso da referência que morreu e da página que responde 200 mas não traz
    #     ficha — repetir só queimaria requisição. O motivo fica gravado no documento.
    #     """
    #     job.status = JobStatus.INVALID
    #     await self._db.update_job(job.id, {'status': job.status.value, 'reason': reason})
    #     self._logger.warning(f'{job.label} - {reason}, marked as invalid')
    #     return job.status
    #
    # async def _save(self, job: Job, sheet: dict) -> None:
    #     sheet.update({
    #         'montadora': job.automaker,
    #         'modelo': job.model,
    #         'versao': job.version,
    #         'ano': job.year,
    #         'reference': job.reference,
    #         'source': self.source,
    #     })
    #     await self._db.save_sheet(sheet)
    #
    #     job.status = JobStatus.DONE
    #     await self._db.update_job(job.id, {'status': job.status.value, 'attempts': job.attempts})
    #
    # async def _fetch(self, label: str, request: Awaitable[Response],
    #                  parse: Callable[[Any], Any], empty: Any) -> Any:
    #     """Await a request, reject unusable responses and hand the body to `parse`."""
    #     return self._parse_response(label, await request, parse, empty)
    #
    # async def _fetch_sheet(self, label: str, request: Awaitable[Response],
    #                        parse: Callable[[Any], Any]) -> dict:
    #     """Como `_fetch`, mas para a ficha de um job.
    #
    #     Um status que diz que a referência morreu não é para repetir: vira
    #     `InvalidJobError` e o job é fechado como `invalid`.
    #     """
    #     response = await request
    #
    #     if response.status in self.dead_statuses:
    #         raise InvalidJobError(f'reference is gone (status {response.status})')
    #
    #     return self._parse_response(label, response, parse, {})
    #
    # def _parse_response(self, label: str, response: Response,
    #                     parse: Callable[[Any], Any], empty: Any) -> Any:
    #     if response.status != 200:
    #         self._logger.warning(f'{label} - unexpected status: {response.status}')
    #         return empty
    #
    #     blocked = self._blocked_reason(response.content)
    #     if blocked:
    #         self._logger.warning(f'{label} - {blocked}')
    #         return empty
    #
    #     return parse(response.content)
    #
    # def _blocked_reason(self, content: Any) -> str | None:
    #     """Why this response is an anti-scraping page, or None when it is a real one."""
    #     return None
    #
    # def _invalid_reason(self, sheet: dict) -> str | None:
    #     """Por que esta ficha nunca vai servir, ou None quando ela serve.
    #
    #     Roda sobre a ficha já parseada: é aqui que cada site diz que a página existe
    #     mas está vazia — modelo tirado do ar, código de versão que não existe mais.
    #     """
    #     return None
