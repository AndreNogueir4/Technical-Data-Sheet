import asyncio
import logging
from typing import Any, Awaitable, Callable
from src.Model.Job import Job
from src.Model.JobStatus import JobStatus
from src.Model.Response import Response
from src.Common.RateLimiter import RateLimiter
from src.Common.exceptions import InvalidJobError, RateLimitedError
from src.Common.DatabaseRepository import DatabaseRepository


class Crawler:
    def __init__(self, source: str, db: DatabaseRepository, limiter: RateLimiter,
                 concurrent: int = 30, try_limit: int = 4):
        self.source = source
        self.database = db
        self.logger = logging.getLogger(type(self).__module__)
        self._limiter = limiter
        self._semaphore = asyncio.Semaphore(value=concurrent)
        self._try_limit = try_limit
        self._dead_statuses = (404, 410)
        self._throttle_statuses = (429, 503)

    async def catalog_phase(self) -> int:
        """Descobre veículos e enfileira um job por versão. Devolve quantos são novos."""
        raise NotImplementedError

    async def fetch_sheet(self, job: Job) -> dict:
        """Baixa e faz o parse da ficha técnica de um job."""
        raise NotImplementedError

    def blocked_reason(self, content: Any) -> str | None:
        """Por que esta resposta é uma página de anti-scraping, ou None quando é real."""
        return None

    def invalid_reason(self, sheet: dict) -> str | None:
        """Por que esta ficha nunca vai servir, ou None quando ela serve.

        Roda sobre a ficha já parseada: é aqui que cada site diz que a página existe
        mas está vazia — modelo tirado do ar, código de versão que não existe mais.
        """
        return None

    async def crawl_task_with_job(self, job: Job) -> JobStatus:
        """Baixa a ficha de um job e fecha o job. Devolve o status em que ele ficou.

        `done` quando a ficha foi salva, `invalid` quando a página respondeu mas não
        tem ficha nenhuma, `todo`/`error` quando a coleta falhou e cabe repetir.
        """
        try:
            sheet = await self.fetch_sheet(job)
        except InvalidJobError as error:
            return await self.invalidate(job, str(error))
        except RateLimitedError as error:
            return await self.release(job, str(error))

        if not sheet:
            return await self.requeue(job)

        reason = self.invalid_reason(sheet)
        if reason:
            return await self.invalidate(job, reason)

        await self.save(job, sheet)
        return job.status

    async def crawl_list(self, jobs: list[Job], raise_error: bool = True) -> list[dict]:
        """Baixa as fichas de uma lista de jobs sem passar pela fila.

        Usado pelo `TechnicalSheet.get_list_result` — nada é persistido, as fichas
        voltam na mesma ordem dos jobs recebidos (um dict vazio onde falhou).
        """
        async def fetch(job: Job) -> dict:
            async with self._semaphore:
                try:
                    return await self.fetch_sheet(job)
                except asyncio.CancelledError:
                    raise
                except InvalidJobError as error:
                    self.logger.warning(f'crawl_list - {job.label}: {error}')
                    return {}
                except Exception:
                    self.logger.exception(f'crawl_list - {job.label} raised')
                    if raise_error:
                        raise
                    return {}

        return list(await asyncio.gather(*(fetch(job) for job in jobs)))

    async def requeue(self, job: Job) -> JobStatus:
        """Devolve um job que falhou para a fila até ele esgotar as tentativas.

        Uma falha costuma ser um bloqueio temporário (429, captcha), então o job volta
        para `todo` com o contador somado — `pop_pending_jobs` serve os menos tentados
        primeiro, o que o joga para o fim da fila em vez de repeti-lo agora.
        """
        job.attempts += 1

        if job.attempts < self._try_limit:
            job.status = JobStatus.TODO
            await self.database.update_job(
                job.id, {'status': job.status.value, 'attempts': job.attempts})
            self.logger.warning(
                f'{job.label} - failed, requeued (attempt {job.attempts}/{self._try_limit})')
            return job.status

        job.status = JobStatus.ERROR
        await self.database.update_job(
            job.id, {'status': job.status.value, 'attempts': job.attempts})
        self.logger.warning(f'{job.label} - failed {job.attempts}x, marked as error')
        return job.status

    async def release(self, job: Job, reason: str) -> JobStatus:
        """Devolve um job intocado à fila: a culpa não é dele.

        É o caso do 429 e do backoff da fonte. Diferente do `requeue`, não soma
        tentativa — senão um site recusando por 4 rodadas condenaria o job a `error`.
        """
        job.status = JobStatus.TODO
        await self.database.update_job(job.id, {'status': job.status.value})
        self.logger.warning(f'{job.label} - {reason}, released back to the queue')
        return job.status

    async def invalidate(self, job: Job, reason: str) -> JobStatus:
        """Fecha um job que nunca vai dar certo, sem gastar tentativa.

        É o caso da referência que morreu e da página que responde 200 mas não traz
        ficha — repetir só queimaria requisição. O motivo fica gravado no documento.
        """
        job.status = JobStatus.INVALID
        await self.database.update_job(job.id, {'status': job.status.value, 'reason': reason})
        self.logger.warning(f'{job.label} - {reason}, marked as invalid')
        return job.status

    async def save(self, job: Job, sheet: dict) -> None:
        sheet.update({
            'montadora': job.automaker,
            'modelo': job.model,
            'versao': job.version,
            'ano': job.year,
            'reference': job.reference,
            'source': self.source,
        })
        await self.database.save_sheet(sheet)

        job.status = JobStatus.DONE
        await self.database.update_job(
            job.id, {'status': job.status.value, 'attempts': job.attempts})

    async def request(self, request: Awaitable[Response]) -> Response:
        """Espera a vez desta fonte no limitador e só então dispara a requisição.

        Ponto único de saída: é o que garante que a taxa não dependa de quantos
        workers existem. Quem chamar a factory direto fura o limite.
        """
        try:
            await self._limiter.wait()
        except BaseException:
            # A corrotina da requisição foi criada pelo chamador e ainda não foi
            # aguardada. Se a espera na fila é cancelada (Ctrl+C), fechá-la evita o
            # RuntimeWarning de 'coroutine was never awaited' na saída.
            getattr(request, 'close', lambda: None)()
            raise

        return await request

    async def fetch(self, label: str, request: Awaitable[Response],
                    parse: Callable[[Any], Any], empty: Any) -> Any:
        """Espera a requisição, rejeita resposta inútil e entrega o corpo ao parser."""
        return self.parse_response(label, await self.request(request), parse, empty)

    async def fetch_sheet_response(self, label: str, request: Awaitable[Response],
                                   parse: Callable[[Any], Any]) -> dict:
        """Como `fetch`, mas para a ficha de um job.

        Um status que diz que a referência morreu não é para repetir: vira
        `InvalidJobError` e o job é fechado como `invalid`. Um que diz que estamos
        pedindo demais vira `RateLimitedError`, e o job volta intacto para a fila.
        """
        response = await self.request(request)

        if response.status in self._dead_statuses:
            raise InvalidJobError(f'reference is gone (status {response.status})')

        if response.status in self._throttle_statuses:
            raise RateLimitedError(f'{label} - rate limited (status {response.status})')

        return self.parse_response(label, response, parse, {})

    def parse_response(self, label: str, response: Response,
                       parse: Callable[[Any], Any], empty: Any) -> Any:
        if response.status != 200:
            self.logger.warning(f'{label} - unexpected status: {response.status}')
            return empty

        blocked = self.blocked_reason(response.content)
        if blocked:
            self.logger.warning(f'{label} - {blocked}')
            return empty

        return parse(response.content)
