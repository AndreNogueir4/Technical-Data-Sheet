import asyncio
from ..scrapers.fichacompleta import (
    automakers as fc_automakers,
    models as fc_models,
    version_and_years as fc_version,
    technical_sheet as fc_technical,
)
from ..logger.logger import get_logger
from ..commons.DatabaseRepository import DatabaseRepository

logger = get_logger('fichacompleta', 'fichacompleta')
semaphore = asyncio.Semaphore(5)
db = DatabaseRepository()

async def validate_scraper_data(data, context: str, reference: str) -> bool:
    """ Valida se os dados retornados pelo scraper são validos """
    if not data:
        logger.warning(f'[{reference}] Nenhum dado encontrado para {context}')
        return False
    return True

async def safe_gather(*tasks):
    """ Executa múltiplas corrotinas de forma segura, tratando exceções """
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            logger.error(f'Erro durante execução da tarefa: {res}')
    return results

async def run_fichacompleta(phase: int = 3):
    """
        Pipeline principal do fichacompleta.
        Args:
            phase: controla as etapas
                1 -> automakers/models/versions/years
                2 -> technical sheets
                3 -> ambos
    """
    logger.info('🚗 Starting Full Sheet scrapers (fichacompleta)')
    reference = 'fichacompleta'

    automakers = await fc_automakers.get_automakers()
    if not await validate_scraper_data(automakers, 'automakers', reference):
        return False

    async def process_model(automaker, model):
        async with semaphore:
            versions, years = await fc_version.get_version_years(automaker, model)
            if not await validate_scraper_data(versions, f'versions para {automaker}/{model}', reference):
                return
            if not await validate_scraper_data(years, f'years para {automaker}/{model}', reference):
                return

            versions_items = list(versions.items())
            num_pairs = min(len(versions_items), len(years))

            tasks = []
            for i in range(num_pairs):
                version_name, version_link = versions_items[i]
                year = years[i]
                tasks.append(db.insert_vehicle(
                    automaker=automaker,
                    model=model,
                    year=year,
                    version=version_name,
                    reference=reference
                ))
            await safe_gather(*tasks)

    async def process_automaker(automaker):
        models = await fc_models.get_models(automaker)
        if not await validate_scraper_data(models, f'models para {automaker}', reference):
            return
        await safe_gather(*[process_model(automaker, model) for model in models])

    if phase in [1, 3]:
        await safe_gather(*[process_automaker(automaker) for automaker in automakers])

    if phase in [2, 3]:
        vehicles = await db.get_vehicles_by_reference(reference)

        async def process_vehicle(vehicle):
            async with semaphore:
                automaker = vehicle['automaker']
                model = vehicle['model']
                version_key = vehicle['version']
                year = str(vehicle['year'])

                versions, _ = await fc_version.get_version_years(automaker, model)
                link_query = versions.get(version_key)
                if not link_query:
                    logger.warning(f'Link not found for version={version_key}')
                    return

                result, equipments = await fc_technical.get_technical_sheet(automaker, model, link_query)
                if not result and not equipments:
                    logger.warning(f'No technical data found for: {link_query}')
                    return

                await db.insert_vehicle_specs(
                    vehicle_id=vehicle['_id'],
                    automaker=automaker,
                    model=model,
                    version=str(version_key),
                    year=str(year),
                    result=result,
                    equipments=equipments,
                )
                logger.info(f'✅ Technical sheet inserted for: {link_query}')

        await safe_gather(*[process_vehicle(vehicle) for vehicle in vehicles])

    logger.info('✅ Completed Complete Sheet')
    return True