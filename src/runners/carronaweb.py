import asyncio
from ..scrapers.carronaweb import (
    automakers as cw_automakers,
    models as cw_models,
    years as cw_years,
    version_link_consultation as cw_version_link_consultation,
    technical_sheet as cw_technical_sheet
)
from ..commons.DatabaseRepository import DatabaseRepository
from ..logger.logger import get_logger

logger = get_logger('carroweb', 'carroweb')
db_repo = DatabaseRepository()
semaphore = asyncio.Semaphore(5)

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

async def run_carroweb(phase: int = 3):
    """ Runner principal para o site CarroWeb """
    logger.info('🚗 Starting CarrosWeb scraper')
    reference = 'carroweb'

    async def process_year(automaker: str, model: str, year: str):
        async with semaphore:
            versions = await cw_version_link_consultation.get_versions_link(automaker, model, year)
            if not await validate_scraper_data(versions,
                                               f'versions para {automaker}/{model}/{year}', reference):
                return False

            tasks = [
                db_repo.insert_vehicle(
                    automaker=automaker,
                    model=model,
                    year=year,
                    version=version,
                    reference=reference
                )
                for _, version in versions.items()
            ]
            await safe_gather(*tasks)
            return True

    async def process_model(automaker: str, model: str):
        years = await cw_years.get_years(automaker, model)
        if not await validate_scraper_data(years, f'years para {automaker}/{model}', reference):
            return False
        await safe_gather([process_year(automaker, model, year) for year in years])
        return True

    if phase in [1, 3]:
        automakers = await cw_automakers.get_automakers()
        if not await validate_scraper_data(automakers, 'automakers', reference):
            return False

        model_tasks = []
        for automaker in automakers:
            models = await cw_models.get_models(automaker)
            if not await validate_scraper_data(models, f'models para {automaker}', reference):
                continue
            for model in models:
                model_tasks.append(process_model(automaker, model))

        await safe_gather(model_tasks)

    if phase in [2, 3]:
        vehicles = await db_repo.get_vehicles_by_reference(reference)
        if not await validate_scraper_data(vehicles, 'vehicles salvos no banco', reference):
            return False

        async def process_vehicle(vehicle):
            async with semaphore:
                specs = await cw_technical_sheet.get_technical_sheet(vehicle)
                if not await validate_scraper_data(specs,
                                                   f'ficha técnica para {vehicle.get("model")}', reference):
                    return False
                await db_repo.insert_vehicle_specs(vehicle['_id'], specs)
                return True

        await safe_gather([process_vehicle(vehicle) for vehicle in vehicles])

    logger.info('✅ Completed CarrosWeb scraper')
    return True