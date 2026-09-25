import random
import asyncio
from typing import Any
from src.Model.Job import Job
from src.Common.Crawler import Crawler
from src.Common.RateLimiter import RateLimiter
from src.Common.utils import repeatable
from src.Common.DatabaseRepository import DatabaseRepository
from src.FichaCompleta.FichaCompletaParser import FichaCompletaParser
from src.FichaCompleta.FichaCompletaRequestFactory import FichaCompletaRequestFactory


class FichaCompletaCrawler(Crawler):
    _FILLER_KEYS = frozenset({'equipamentos'})

    def __init__(self, factory: FichaCompletaRequestFactory, parser: FichaCompletaParser,
                 db: DatabaseRepository, limiter: RateLimiter, source: str = 'fichacompleta',
                 concurrent: int = 30, try_limit: int = 4):
        super().__init__(source, db, limiter, concurrent, try_limit)
        self._factory = factory
        self._parser = parser

    async def catalog_phase(self) -> int:
        total_jobs = 0

        for automaker in await self._get_automakers():
            models = await self._get_models(automaker)
            if models:
                await self.database.upsert_automaker(automaker, models)

            for model in models:
                await asyncio.sleep(random.uniform(1, 5))

                versions, years = await self._get_version_years(automaker, model)
                if not versions:
                    continue

                reference = self._factory.model_url(automaker, model)
                await self.database.upsert_model(automaker, model, reference, versions, years)

                for (version_name, href), year in zip(versions.items(), years):
                    job = Job(source=self.source, reference=href, automaker=automaker,
                              model=model, year=year, version=version_name)
                    if await self.database.insert_job(job):
                        total_jobs += 1

            await asyncio.sleep(random.uniform(2, 8))

        self.logger.info(f'catalog_phase - {total_jobs} new jobs created')
        return total_jobs

    @repeatable
    async def fetch_sheet(self, job: Job) -> dict:
        href = job.reference
        sheet = await self.fetch_sheet_response(
            f'technical_sheet [{href}]',
            self._factory.get_technical_sheet(job.automaker, job.model, href),
            self._parser.technical_sheet,
        )
        if sheet:
            self.logger.info(f'technical_sheet [{href}] - parsed')
        return sheet

    def blocked_reason(self, content: Any) -> str | None:
        return 'captcha detected' if self._parser.is_captcha(content) else None

    def invalid_reason(self, sheet: dict) -> str | None:
        # O parser sempre devolve `equipamentos`, nem que seja o placeholder. Se não veio
        # nenhuma especificação junto, a página existe mas não tem ficha nenhuma.
        specs = {key: value for key, value in sheet.items() if key not in self._FILLER_KEYS}
        return None if specs else 'page has no technical sheet'

    async def _get_automakers(self) -> list[str]:
        automakers = await self.fetch(
            'get_automakers', self._factory.get_automakers(), self._parser.automakers, [])
        self.logger.info(f'get_automakers - found {len(automakers)} automakers')
        return automakers

    async def _get_models(self, automaker: str) -> list[str]:
        models = await self.fetch(
            f'{automaker} | get_models', self._factory.get_models(automaker), self._parser.models, [])
        self.logger.info(f'{automaker} | get_models - found {len(models)} models')
        return models

    async def _get_version_years(self, automaker: str, model: str) -> tuple[dict, list[str]]:
        versions, years = await self.fetch(
            f'{automaker} : {model} | get_version_years',
            self._factory.get_version_years(automaker, model),
            self._parser.version_years,
            ({}, []),
        )
        self.logger.info(
            f'{automaker} : {model} | get_version_years - found {len(versions)} versions')
        return versions, years
