import asyncio
import signal
import sys
import argparse
from src.Logger import get_logger
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository
from src.CarrosWeb.CarrosWebParser import CarrosWebParser
from src.CarrosWeb.CarrosWebRequestFactory import CarrosWebRequestFactory
from src.CarrosWeb.CarrosWebCrawler import CarrosWebCrawler
from src.FichaCompleta.FichaCompletaParser import FichaCompletaParser
from src.FichaCompleta.FichaCompletaRequestFactory import FichaCompletaRequestFactory
from src.FichaCompleta.FichaCompletaCrawler import FichaCompletaCrawler

logger = get_logger('main', 'main')


async def run_carrosweb() -> int:
    logger.info('Starting CarrosWeb crawler')
    db = DatabaseRepository()
    async with NetworkManager.create() as network:
        factory = CarrosWebRequestFactory(network)
        parser = CarrosWebParser()
        crawler = CarrosWebCrawler(factory, parser)
        sheets = await crawler.crawler()

    for sheet in sheets:
        await db.save_sheet(sheet)

    logger.info(f'CarrosWeb: saved {len(sheets)} sheets')
    return len(sheets)


async def run_carrosweb_catalog() -> int:
    logger.info('Starting CarrosWeb catalog phase')
    db = DatabaseRepository()
    async with NetworkManager.create() as network:
        factory = CarrosWebRequestFactory(network)
        parser = CarrosWebParser()
        crawler = CarrosWebCrawler(factory, parser, db)
        count = await crawler.catalog_phase()

    logger.info(f'CarrosWeb catalog: {count} new jobs created')
    return count


async def run_carrosweb_worker() -> int:
    logger.info('Starting CarrosWeb sheet worker')
    db = DatabaseRepository()
    async with NetworkManager.create() as network:
        factory = CarrosWebRequestFactory(network)
        parser = CarrosWebParser()
        crawler = CarrosWebCrawler(factory, parser, db)
        count = await crawler.sheet_worker()

    logger.info(f'CarrosWeb worker: {count} sheets saved')
    return count


async def run_fichacompleta_catalog() -> int:
    logger.info('Starting FichaCompleta catalog phase')
    db = DatabaseRepository()
    async with NetworkManager.create() as network:
        factory = FichaCompletaRequestFactory(network, db)
        parser = FichaCompletaParser()
        crawler = FichaCompletaCrawler(factory, parser, db)
        count = await crawler.catalog_phase()

    logger.info(f'FichaCompleta catalog: {count} new jobs created')
    return count


async def run_fichacompleta_worker() -> int:
    logger.info('Starting FichaCompleta sheet worker')
    db = DatabaseRepository()
    async with NetworkManager.create() as network:
        factory = FichaCompletaRequestFactory(network, db)
        parser = FichaCompletaParser()
        crawler = FichaCompletaCrawler(factory, parser, db)
        count = await crawler.sheet_worker()

    logger.info(f'FichaCompleta worker: {count} sheets saved')
    return count


async def run_all() -> None:
    await asyncio.gather(run_carrosweb(), run_fichacompleta_catalog())
    await run_fichacompleta_worker()

async def run_forever(interval: int = 3600) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, stop.set)
    loop.add_signal_handler(signal.SIGTERM, stop.set)

    logger.info(f'run_forever started | interval={interval}s | workers=5 per site')

    while not stop.is_set():
        logger.info('Starting new cycle')
        await run_all()

        if stop.is_set():
            break

        logger.info(f'Cycle complete. Next cycle in {interval}s (Ctrl+C to stop)...')
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info('run_forever stopped gracefully')

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Technical Data Sheet scraper')
    sub = parser.add_subparsers(dest='command', required=True)

    site_p = sub.add_parser('site', help='Rodar scraper de um site específico')
    site_p.add_argument('site', choices=[
        'carrosweb',
        'carrosweb-catalog',
        'carrosweb-worker',
        'fichacompleta-catalog',
        'fichacompleta-worker',
    ])

    sub.add_parser('full', help='Rodar todos os scrapers')

    forever_p = sub.add_parser('run-forever', help='Rodar todos os scrapers em loop contínuo')
    forever_p.add_argument('--interval', type=int, default=3600,
                           help='Intervalo em segundos entre ciclos (default: 3600)')

    return parser


async def main() -> None:
    args = _build_parser().parse_args()

    try:
        if args.command == 'site':
            if args.site == 'carrosweb':
                await run_carrosweb()
            elif args.site == 'carrosweb-catalog':
                await run_carrosweb_catalog()
            elif args.site == 'carrosweb-worker':
                await run_carrosweb_worker()
            elif args.site == 'fichacompleta-catalog':
                await run_fichacompleta_catalog()
            elif args.site == 'fichacompleta-worker':
                await run_fichacompleta_worker()

        elif args.command == 'full':
            await run_all()

        elif args.command == 'run-forever':
            await run_forever(interval=args.interval)

    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        sys.exit(1)


asyncio.run(main())
