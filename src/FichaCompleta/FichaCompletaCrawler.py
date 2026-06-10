from src.Logger import get_logger
from src.Common.DatabaseRepository import DatabaseRepository
from src.FichaCompleta.FichaCompletaParser import FichaCompletaParser
from src.FichaCompleta.FichaCompletaRequestFactory import FichaCompletaRequestFactory

logger = get_logger('FichaCompletaCrawler', reference='fichacompleta')


class FichaCompletaCrawler:
    def __init__(self, factory: FichaCompletaRequestFactory, parser: FichaCompletaParser,
                 db: DatabaseRepository):
        self._factory = factory
        self._parser = parser
        self._db = db

    async def crawler(self) -> int:
        automakers = await self._get_automakers()
        total = 0

        for automaker in automakers:
            models = await self._get_models(automaker)
            if models:
                await self._db.upsert_automaker(automaker, models)

            for model in models:
                versions, years = await self._get_version_years(automaker, model)
                if not versions:
                    continue

                reference = f'{self._factory._base_url}/carros/{automaker}/{model}/'
                await self._db.upsert_model(automaker, model, reference, versions, years)

                scraped = await self._db.get_scraped_hrefs(automaker, model)
                new_pairs = [
                    (name, href, year)
                    for (name, href), year in zip(versions.items(), years)
                    if href not in scraped
                ]

                if not new_pairs:
                    logger.info(f'{automaker} : {model} | nothing new, skipping')
                    continue

                for version_name, href, year in new_pairs:
                    sheet = await self._technical_sheet(automaker, model, href)
                    if sheet:
                        sheet.update({
                            'montadora': automaker,
                            'modelo': model,
                            'versao': version_name,
                            'ano': year,
                        })
                        await self._db.save_sheet(sheet)
                        await self._db.mark_href_scraped(automaker, model, href)
                        total += 1

        logger.info(f'crawler - finished, {total} new technical sheets saved')
        return total

    async def _get_automakers(self) -> list[str]:
        response = await self._factory.get_automakers()

        if response.status != 200:
            logger.warning(f'get_automakers - unexpected status: {response.status}')
            return []

        if self._parser.is_captcha(response.content):
            logger.warning('get_automakers - captcha detected')
            return []

        automakers = self._parser.automakers(response.content)
        logger.info(f'get_automakers - found {len(automakers)} automakers')
        return automakers

    async def _get_models(self, automaker: str) -> list[str]:
        response = await self._factory.get_models(automaker)

        if response.status != 200:
            logger.warning(f'get_models - unexpected status: {response.status}')
            return []

        if self._parser.is_captcha(response.content):
            logger.warning(f'{automaker} | get_models - captcha detected')
            return []

        models = self._parser.models(response.content)
        logger.info(f'{automaker} | get_models - found {len(models)} models')
        return models

    async def _get_version_years(self, automaker: str, model: str) -> tuple[dict, list[str]]:
        response = await self._factory.get_version_years(automaker, model)

        if response.status != 200:
            logger.warning(f'get_version_years - unexpected status: {response.status}')
            return {}, []

        if self._parser.is_captcha(response.content):
            logger.warning(f'{automaker} : {model} | get_version_years - captcha detected')
            return {}, []

        versions, years = self._parser.version_years(response.content)
        logger.info(f'{automaker} : {model} | get_version_years - found {len(versions)} versions')
        return versions, years

    async def _technical_sheet(self, automaker: str, model: str, href: str) -> dict:
        response = await self._factory.get_technical_sheet(automaker, model, href)

        if response.status != 200:
            logger.warning(f'technical_sheet [{href}] - unexpected status: {response.status}')
            return {}

        if self._parser.is_captcha(response.content):
            logger.warning(f'technical_sheet [{href}] - captcha detected')
            return {}

        sheet = self._parser.technical_sheet(response.content)
        logger.info(f'technical_sheet [{href}] - parsed')
        return sheet
