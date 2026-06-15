import asyncio
import random
from src.Logger import get_logger
from src.Common.utils import ocr_numeric_image
from src.Common.DatabaseRepository import DatabaseRepository
from src.CarrosWeb.CarrosWebParser import CarrosWebParser
from src.CarrosWeb.CarrosWebRequestFactory import CarrosWebRequestFactory

logger = get_logger('CarrosWebCrawler', reference='carrosweb')


class CarrosWebCrawler:
    def __init__(self, factory: CarrosWebRequestFactory, parser: CarrosWebParser,
                 db: DatabaseRepository = None):
        self._factory = factory
        self._parser = parser
        self._db = db

    async def catalog_phase(self) -> int:
        automakers = await self._get_automakers()
        total_jobs = 0

        for automaker in automakers:
            models = await self._get_models(automaker)
            for model in models:
                years = await self._get_years(automaker, model)
                for year in years:
                    versions = await self._get_versions_code(automaker, model, [year, year])
                    for version_name, href in versions.items():
                        code = href.split('=')[-1] if '=' in href else href
                        doc = await self._db.insert_vehicle(automaker, model, year, version_name, code)
                        if doc:
                            total_jobs += 1

        logger.info(f'catalog_phase - {total_jobs} new jobs created')
        return total_jobs

    async def sheet_worker(self) -> int:
        total = 0

        while True:
            jobs = await self._db.pop_pending_jobs(limit=2)
            if not jobs:
                logger.info('sheet_worker - no pending jobs, done')
                break

            for job in jobs:
                code = job['reference']
                sheet = await self._technical_sheet(code)
                if sheet:
                    sheet.update({
                        'montadora': job['automaker'],
                        'modelo': job['model'],
                        'versao': job['version'],
                        'ano': job['year'],
                        'source': 'carrosweb',
                    })
                    await self._db.save_sheet(sheet)
                    await self._db.update_vehicle(str(job['_id']), {'status': 'done'})
                    total += 1
                else:
                    await self._db.update_vehicle(str(job['_id']), {'status': 'error'})
                    logger.warning(f'sheet_worker - failed job {job["_id"]} [{code}], marked as error')

            delay = random.uniform(10, 50)
            logger.info(f'sheet_worker - processed {len(jobs)} jobs, sleeping {delay:.0f}s')
            await asyncio.sleep(delay)

        logger.info(f'sheet_worker - finished, {total} sheets saved')
        return total

    async def crawler(self) -> list[dict]:
        automakers = await self._get_automakers()
        all_sheets: list[dict] = []
        seen_codes: set[str] = set()

        for automaker in automakers:
            models = await self._get_models(automaker)

            for model in models:
                years = await self._get_years(automaker, model)

                for year in years:
                    versions = await self._get_versions_code(automaker, model, [year, year])

                    for version_name, href in versions.items():
                        code = href.split('=')[-1] if '=' in href else href
                        if code in seen_codes:
                            continue
                        seen_codes.add(code)

                        sheet = await self._technical_sheet(code)
                        if sheet:
                            sheet['montadora'] = automaker
                            sheet['modelo'] = model
                            sheet['ano'] = year
                            sheet['versao'] = version_name
                            sheet['source'] = 'carrosweb'
                            all_sheets.append(sheet)

        logger.info(f'crawler - finished, collected {len(all_sheets)} technical sheets')
        return all_sheets

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    async def _get_automakers(self) -> list[str]:
        response = await self._factory.get_automakers()

        if response.status != 200:
            logger.warning(f'get_automakers - unexpected status: {response.status}')
            return []

        if self._parser.is_error_page(response.content):
            logger.warning('get_automakers - error page detected')
            return []

        automakers = self._parser.automakers(response.content)
        logger.info(f'get_automakers - found {len(automakers)} automakers')
        return automakers

    async def _get_models(self, automaker: str) -> list[str]:
        response = await self._factory.get_models(automaker)

        if response.status != 200:
            logger.warning(f'get_models - unexpected status: {response.status}')
            return []

        if self._parser.is_error_page(response.content):
            logger.warning('get_models - error page detected')
            return []

        models = self._parser.models(response.content)
        logger.info(f'{automaker} | get_models - found {len(models)} models')
        return models

    async def _get_years(self, automaker: str, model: str) -> list[str]:
        response = await self._factory.get_years(automaker, model)

        if response.status != 200:
            logger.warning(f'get_years - unexpected status: {response.status}')
            return []

        if self._parser.is_error_page(response.content):
            logger.warning('get_years - error page detected')
            return []

        years = self._parser.years(response.content)
        logger.info(f'{automaker} : {model} | get_years - found {len(years)} years')
        return years

    async def _get_versions_code(self, automaker: str, model: str, year: list) -> dict:
        start_year = year[0]
        final_year = year[1]

        response = await self._factory.get_versions(automaker, model, start_year, final_year)

        if response.status != 200:
            logger.warning(f'get_versions_code - unexpected status: {response.status}')
            return {}

        if self._parser.is_error_page(response.content):
            logger.warning('get_versions_code - error page detected')
            return {}

        versions = self._parser.versions_code(response.content)
        logger.info(
            f'{automaker} : {model} : {start_year}-{final_year} | '
            f'get_versions_code - found {len(versions)} versions'
        )
        return versions

    async def _technical_sheet(self, code: str) -> dict:
        response = await self._factory.get_technical_sheet(code)

        if response.status != 200:
            logger.warning(f'technical_sheet [{code}] - unexpected status: {response.status}')
            return {}

        if self._parser.is_error_page(response.content):
            logger.warning(f'technical_sheet [{code}] - error page detected')
            return {}

        sheet = self._parser.technical_sheet(response.content)
        sheet = await self._resolve_ocr_values(sheet, code)

        logger.info(f'technical_sheet [{code}] - parsed: {sheet.get("nome", "unknown")}')
        return sheet

    async def _resolve_ocr_values(self, sheet: dict, code: str) -> dict:
        """Replace __ocr__ placeholder dicts with values extracted from anti-scraping images."""
        for key, value in list(sheet.items()):
            if not isinstance(value, dict) or '__ocr__' not in value:
                continue

            image_path = value['__ocr__']
            unit = value.get('__unit__', '')

            image_response = await self._factory.get_image_value(image_path)

            if image_response.status != 200 or not isinstance(image_response.content, bytes):
                logger.warning(
                    f'technical_sheet [{code}] - could not fetch OCR image for "{key}" '
                    f'({image_path}), status={image_response.status}'
                )
                sheet[key] = None
                continue

            ocr_text = ocr_numeric_image(image_response.content)
            if ocr_text:
                sheet[key] = f'{ocr_text} {unit}'.strip() if unit else ocr_text
            else:
                logger.warning(
                    f'technical_sheet [{code}] - OCR returned empty result for "{key}" ({image_path})'
                )
                sheet[key] = None

        return sheet
