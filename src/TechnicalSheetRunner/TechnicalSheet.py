import asyncio
import logging
from collections import Counter, defaultdict
from argparse import ArgumentParser
from src.Model.Job import Job
from src.Model.JobStatus import JobStatus
from src.Model.SheetMode import SheetMode
from src.Common.Crawler import Crawler
from src.Common.exceptions import InvalidSourceError
from src.Common.DatabaseRepository import DatabaseRepository


class TechnicalSheet:
    RUN = 'run'
    def __init__(self, parser: ArgumentParser, database: DatabaseRepository, crawlers: list[Crawler],
                 worker_count: int = 20, sleep_time: int = 2, batch_size: int = 5,
                 max_failures: int = 5):
        self._parser = parser
        self._database = database
        self._crawlers = {crawler.source: crawler for crawler in crawlers}
        self._logger = logging.getLogger(type(self).__module__)
        self._worker_count = max(1, worker_count)
        self._sleep_time = sleep_time
        self._batch_size = batch_size
        self._max_failures = max_failures
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=self._worker_count)
        self._failures: Counter[str] = Counter()
        self._successes: Counter[str] = Counter()
        self._backoffs: Counter[str] = Counter()
        self._blocked_until: dict[str, float] = {}
        self._saved = 0
        self._invalid = 0
        self._all_sources = 'all'

    async def run(self, argv: list[str] | None = None) -> int:
        self._setup_args()
        args = self._parser.parse_args(argv)
        mode = SheetMode(args.mode)
        crawlers = self._crawlers_from_source(args.source)
        sources = [crawler.source for crawler in crawlers]
        await self._record('INFO', f'starting | sources={sources} | mode={mode.value}')

        failures = 0
        for stage in mode.stages:
            failures += await self._run_stage(stage, crawlers, mode.keep_alive)

        await self._record('INFO', f'finished | {self._saved} sheets saved, {self._invalid} invalid')
        return min(failures, 1)

    async def _record(self, level: str, message: str, reference: str = RUN) -> None:
        line = message if reference == self.RUN else f'{reference} - {message}'
        self._logger.log(getattr(logging, level), line)
        await self._database.insert_log(level, message, reference)

    def get_list_result(self, jobs: list[Job], raise_error: bool = True) -> list[dict]:
        return asyncio.run(self.get_list_result_task(jobs, raise_error))

    async def get_list_result_task(self, jobs: list[Job], raise_error: bool = True) -> list[dict]:
        tasks = []
        for source, source_jobs in self._group_by_source(jobs).items():
            crawler = self._get_crawler_from_source(source)
            if not crawler:
                raise InvalidSourceError(source)
            tasks.append(asyncio.create_task(crawler.crawl_list(source_jobs, raise_error)))

        results = await asyncio.gather(*tasks)
        return [sheet for sheets in results for sheet in sheets]

    async def _run_stage(self, stage: SheetMode, crawlers: list[Crawler], keep_alive: bool) -> int:
        if stage is SheetMode.CATALOG:
            return await self._run_catalog(crawlers)
        return await self._run_workers(crawlers, keep_alive)

    async def _run_catalog(self, crawlers: list[Crawler]) -> int:
        results = await asyncio.gather(*(crawler.catalog_phase() for crawler in crawlers), return_exceptions=True)

        failed = 0
        for crawler, result in zip(crawlers, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                await self._record('ERROR', f'catalog failed: {result!r}', crawler.source)
                failed += 1
                continue
            await self._record('INFO', f'catalog finished ({result} new jobs)', crawler.source)
        return failed

    async def _run_workers(self, crawlers: list[Crawler], keep_alive: bool) -> int:
        workers = self._get_workers()
        try:
            blocked = await self._feed(crawlers, keep_alive)
            await self._queue.join()
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        self._logger.info(
            f'worker - stage finished, {self._saved} sheets saved, {self._invalid} invalid')
        return len(blocked)

    async def _feed(self, crawlers: list[Crawler], keep_alive: bool) -> set[str]:
        pending = {crawler.source for crawler in crawlers}
        blocked: set[str] = set()
        idle = False

        while pending:
            if await self._fill(pending, blocked, keep_alive):
                idle = False
                continue
            await self._queue.join()

            if not pending or await self._fill(pending, blocked, keep_alive):
                idle = False
                continue

            if not keep_alive:
                for source in sorted(pending):
                    self._logger.info(f'{source} - no pending jobs left')
                pending.clear()
                continue

            if not idle:
                # Uma linha por espera: um backoff de 120s enchia o console com duas
                # dúzias de linhas idênticas a cada `sleep_time`.
                self._logger.info('worker - nothing to do, waiting')
                idle = True
            await asyncio.sleep(self._sleep_time)

        return blocked

    async def _fill(self, pending: set[str], blocked: set[str], keep_alive: bool) -> int:
        queued = 0
        now = asyncio.get_running_loop().time()

        for source in sorted(pending):
            # O bloqueio vem antes do castigo: uma fonte já em backoff não pode ser
            # castigada outra vez por falhas que já foram contadas — era isso que
            # dobrava a espera de 120s para 240s em catorze segundos.
            if self._blocked_until.get(source, 0.0) > now:
                continue

            if self._failures[source] >= self._max_failures:
                if not keep_alive:
                    await self._record(
                        'ERROR',
                        f'{self._max_failures} jobs in a row failed, stopping '
                        f'(the site is most likely blocking us)',
                        source)
                    pending.discard(source)
                    blocked.add(source)
                    continue
                await self._back_off(source, now)
                continue

            jobs = await self._database.pop_pending_jobs(source, limit=self._batch_size)
            queued += len(jobs)
            for job in jobs:
                await self._queue.put(job)

        return queued

    def _get_workers(self) -> list[asyncio.Task]:
        return [asyncio.create_task(self._worker(index), name=f'worker-{index}')
                for index in range(self._worker_count)]

    async def _worker(self, worker: int) -> None:
        while True:
            job = await self._queue.get()
            try:
                crawler = self._get_crawler_from_source(job.source)
                if not crawler:
                    self._logger.error(
                        f'worker {worker} - unknown source {job.source!r} on {job.label}, skipping')
                    continue
                if self._is_blocked(job.source):
                    # A fonte entrou em backoff depois deste job ser enfileirado: devolve
                    # sem bater no site. É o que impede a debandada dos jobs em voo.
                    await crawler.release(job, 'source is backing off')
                    continue
                await self._crawl(worker, crawler, job)
            finally:
                self._queue.task_done()

    async def _crawl(self, worker: int, crawler: Crawler, job: Job) -> None:
        label = f'worker {worker} | {job.source} | {job.label}'

        try:
            status = await crawler.crawl_task_with_job(job)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._logger.error(f'{label} - raised: {error!r}')
            status = await crawler.requeue(job)

        if status is JobStatus.DONE:
            self._saved += 1
            self._reset(job.source)
            self._logger.info(f'{label} - saved ({self._saved} so far)')
        elif status is JobStatus.INVALID:
            # O site respondeu bem, a ficha é que não existe: não é sinal de bloqueio.
            self._invalid += 1
            self._reset(job.source)
            self._logger.info(f'{label} - invalid, skipped ({self._invalid} so far)')
        else:
            # Trava no teto: são N workers somando em paralelo, e quem confere é o
            # `_fill`, que só roda entre rodadas de alimentação.
            self._failures[job.source] = min(self._failures[job.source] + 1, self._max_failures)
            self._logger.warning(
                f'{label} - failed ({self._failures[job.source]}/{self._max_failures} in a row)')

    async def _back_off(self, source: str, now: float) -> None:
        self._successes[source] = 0
        self._backoffs[source] += 1
        wait = min(60.0 * 2 ** self._backoffs[source], 900.0)
        self._blocked_until[source] = now + wait
        self._failures[source] = 0
        await self._record(
            'WARNING',
            f'{self._max_failures} jobs in a row failed, backing off {wait:.0f}s '
            f'(the site is most likely blocking us)',
            source)

    def _is_blocked(self, source: str) -> bool:
        return self._blocked_until.get(source, 0.0) > asyncio.get_running_loop().time()

    def _reset(self, source: str) -> None:
        """Zera a sequência de falhas de uma fonte que respondeu bem.

        Não levanta um backoff em curso: quem tira o bloqueio é o tempo. Uma ficha que
        passou no meio de uma leva de 429 não quer dizer que o site liberou — era isso
        que cancelava a espera de 120s e fazia o ciclo recomeçar na hora.

        A escalada é simétrica: assim como `max_failures` falhas seguidas aumentam a
        espera, `max_failures` sucessos seguidos derrubam um nível. Um acerto solto no
        meio de uma leva de 429 não conta — senão a espera nunca sai de 120s.
        """
        self._failures[source] = 0
        self._successes[source] += 1

        if self._successes[source] >= self._max_failures:
            self._successes[source] = 0
            self._backoffs[source] = max(0, self._backoffs[source] - 1)

    def _setup_args(self) -> None:
        self._parser.add_argument(
            '-s', '--source', default=self._all_sources, choices=(self._all_sources, *sorted(self._crawlers)),
            help='fonte a coletar (default: all)')
        self._parser.add_argument(
            '-m', '--mode', default=SheetMode.ALL.value, choices=SheetMode.choices(),
            help='catalog enfileira os jobs, worker drena a fila continuamente; '
                 'all roda os dois e termina quando não sobra nada (default: all)')

    def _crawlers_from_source(self, source: str) -> list[Crawler]:
        if source == self._all_sources:
            return list(self._crawlers.values())

        crawler = self._get_crawler_from_source(source)
        if not crawler:
            raise InvalidSourceError(source)
        return [crawler]

    def _get_crawler_from_source(self, source: str) -> Crawler | None:
        return self._crawlers.get(source)

    @staticmethod
    def _group_by_source(jobs: list[Job]) -> dict[str, list[Job]]:
        grouped: dict[str, list[Job]] = defaultdict(list)
        for job in jobs:
            grouped[job.source].append(job)
        return grouped
