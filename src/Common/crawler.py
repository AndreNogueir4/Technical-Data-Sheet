import random
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Iterator
from src.Model.Response import Response
from src.Common.DatabaseRepository import DatabaseRepository


class Crawler(ABC):
    """Shared skeleton for every site crawler.

    A crawler has two stages: `catalog_phase` discovers vehicles and queues them as
    jobs, `sheet_worker` drains that queue. Only the catalog and the sheet fetching
    are site specific — the queue handling lives here.
    """

    source: str = ''

    def __init__(self, db: DatabaseRepository, logger: logging.Logger,
                 batch_size: int = 4, delay: tuple[float, float] = (10.0, 50.0),
                 concurrency: int = 2, max_attempts: int = 3, max_failed_batches: int = 5):
        self._db = db
        self._logger = logger
        self._batch_size = batch_size
        self._concurrency = max(1, concurrency)
        self._delay = delay
        self._max_attempts = max_attempts
        self._max_failed_batches = max_failed_batches

    @abstractmethod
    async def catalog_phase(self) -> int:
        """Discover vehicles and queue one job per version. Returns the number of new jobs."""

    @abstractmethod
    async def fetch_sheet(self, job: dict) -> dict:
        """Download and parse the technical sheet of a queued job."""

    async def sheet_worker(self) -> int:
        total = 0
        failed_batches = 0

        while True:
            jobs = await self._db.pop_pending_jobs(self.source, limit=self._batch_size)
            if not jobs:
                self._logger.info('sheet_worker - no pending jobs, done')
                break

            saved = 0
            for wave in self._waves(jobs):
                saved += await self._process_wave(wave)

                delay = random.uniform(*self._delay)
                self._logger.info(
                    f'sheet_worker - wave of {len(wave)} done, {saved}/{len(jobs)} of this '
                    f'batch saved, sleeping {delay:.0f}s')
                await asyncio.sleep(delay)

            total += saved

            if saved:
                failed_batches = 0
                self._logger.info(f'sheet_worker - batch done, {total} sheets saved so far')
                continue

            failed_batches += 1
            if failed_batches >= self._max_failed_batches:
                self._logger.error(
                    f'sheet_worker - {failed_batches} batches in a row failed, stopping '
                    f'(the site is most likely blocking us)')
                break

            backoff = self._backoff(failed_batches)
            self._logger.warning(
                f'sheet_worker - whole batch failed, backing off {backoff:.0f}s '
                f'({failed_batches}/{self._max_failed_batches})')
            await asyncio.sleep(backoff)

        self._logger.info(f'sheet_worker - finished, {total} sheets saved')
        return total

    def _waves(self, jobs: list[dict]) -> Iterator[list[dict]]:
        """Split a claimed batch into the groups that are downloaded concurrently."""
        for start in range(0, len(jobs), self._concurrency):
            yield jobs[start:start + self._concurrency]

    async def _process_wave(self, wave: list[dict]) -> int:
        """Download one wave at once, waiting for all of it before the next starts.

        A job that raises is requeued rather than taking the whole wave down with it —
        `gather` would otherwise abandon its siblings mid-download.
        """
        results = await asyncio.gather(
            *(self._process(job) for job in wave), return_exceptions=True)

        saved = 0
        for job, result in zip(wave, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                self._logger.error(
                    f'sheet_worker - job {job["_id"]} [{job["reference"]}] raised: {result!r}')
                await self._requeue(job)
                continue
            saved += result
        return saved

    async def _process(self, job: dict) -> int:
        job_id = str(job['_id'])
        sheet = await self.fetch_sheet(job)

        if not sheet:
            await self._requeue(job)
            return 0

        sheet.update({
            'montadora': job['automaker'],
            'modelo': job['model'],
            'versao': job['version'],
            'ano': job['year'],
            'source': self.source,
        })
        await self._db.save_sheet(sheet)
        await self._db.update_vehicle(job_id, {'status': 'done'})
        return 1

    async def _requeue(self, job: dict) -> None:
        """Put a failed job back in the queue until it runs out of attempts.

        A failure is usually a transient block (429, captcha), so the job goes back to
        `todo` with a bumped attempt counter — `pop_pending_jobs` serves the least tried
        jobs first, which sends it to the back of the queue instead of retrying it now.
        """
        job_id = str(job['_id'])
        attempts = job.get('attempts', 0) + 1
        label = f'job {job_id} [{job["reference"]}]'

        if attempts < self._max_attempts:
            await self._db.update_vehicle(job_id, {'status': 'todo', 'attempts': attempts})
            self._logger.warning(
                f'sheet_worker - {label} failed, requeued (attempt {attempts}/{self._max_attempts})')
            return

        await self._db.update_vehicle(job_id, {'status': 'error', 'attempts': attempts})
        self._logger.warning(f'sheet_worker - {label} failed {attempts}x, marked as error')

    def _backoff(self, failed_batches: int) -> float:
        """Exponential backoff off the top of the configured delay, capped at 15 minutes."""
        return min(self._delay[1] * 2 ** failed_batches, 900.0)

    async def _fetch(self, label: str, request: Awaitable[Response],
                     parse: Callable[[Any], Any], empty: Any) -> Any:
        """Await a request, reject unusable responses and hand the body to `parse`."""
        response = await request

        if response.status != 200:
            self._logger.warning(f'{label} - unexpected status: {response.status}')
            return empty

        blocked = self._blocked_reason(response.content)
        if blocked:
            self._logger.warning(f'{label} - {blocked}')
            return empty

        return parse(response.content)

    def _blocked_reason(self, content: Any) -> str | None:
        """Why this response is an anti-scraping page, or None when it is a real one."""
        return None
