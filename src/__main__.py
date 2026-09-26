import asyncio
import logging
import timeit
from datetime import timedelta
from dependency_injector.wiring import inject, Provide
from src.Common.DatabaseRepository import DatabaseRepository
from src.TechnicalSheetRunner.TechnicalSheet import TechnicalSheet
from src.TechnicalSheetRunner.TechnicalSheetContainer import TechnicalSheetContainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s - %(message)s')
logger = logging.getLogger('src.main')


@inject
async def main(sheet_runner: TechnicalSheet = Provide[TechnicalSheetContainer.technical_sheet_runner],
               database: DatabaseRepository = Provide[TechnicalSheetContainer.database]) -> int:
    start = timeit.default_timer()
    try:
        return await sheet_runner.run()
    except Exception:
        logger.exception('crashed')
        await database.insert_log('ERROR', 'crashed', 'run')
        return 1
    finally:
        elapsed = timedelta(seconds=round(timeit.default_timer() - start))
        logger.info(f'total time: {elapsed}')
        await database.insert_log('INFO', f'total time: {elapsed}', 'run')


async def run() -> int:
    container = TechnicalSheetContainer()
    container.wire(modules=[__name__])
    await container.init_resources()

    try:
        return await main()
    except Exception:
        logger.exception('crashed before the run started')
        return 1
    finally:
        await container.shutdown_resources()


if __name__ == '__main__':
    try:
        code = asyncio.run(run())
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)
