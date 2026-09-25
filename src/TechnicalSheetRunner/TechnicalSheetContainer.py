from argparse import ArgumentParser
from dependency_injector import containers, providers
from src.Common.settings import Settings
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository
from src.CarrosWeb.CarrosWebContainer import CarrosWebContainer
from src.FichaCompleta.FichaCompletaContainer import FichaCompletaContainer
from src.TechnicalSheetRunner.TechnicalSheet import TechnicalSheet


class TechnicalSheetContainer(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings.from_env)
    argument_parser = providers.Factory(
        ArgumentParser,
        prog='python -m src',
        description='Crawler de fichas técnicas de veículos',
    )

    network = providers.Resource(
        NetworkManager.create,
        cffi_impersonate=settings.provided.impersonate,
        timeout=settings.provided.timeout,
        tcp_limit=settings.provided.tcp_limit,
    )

    database = providers.Resource(
        DatabaseRepository.create,
        uri=settings.provided.mongo_uri,
        db_name=settings.provided.mongo_db,
    )

    fichacompleta = providers.Container(
        FichaCompletaContainer,
        settings=settings, network=network, database=database,
    )

    carrosweb = providers.Container(
        CarrosWebContainer,
        settings=settings, network=network, database=database,
    )

    technical_sheet_runner = providers.Factory(
        TechnicalSheet,
        parser=argument_parser,
        database=database,
        crawlers=providers.List(
            fichacompleta.crawler,
            carrosweb.crawler,
        ),
        worker_count=settings.provided.worker_count,
        sleep_time=settings.provided.sleep_time,
        batch_size=settings.provided.batch_size,
        max_failures=settings.provided.max_failures,
    )
