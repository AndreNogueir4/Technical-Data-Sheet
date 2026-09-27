from dependency_injector import containers, providers
from src.Common.settings import Settings
from src.Common.utils import RateLimiter
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository
from src.CarrosWeb.CarrosWebCrawler import CarrosWebCrawler
from src.CarrosWeb.CarrosWebParser import CarrosWebParser
from src.CarrosWeb.CarrosWebRequestFactory import CarrosWebRequestFactory


class CarrosWebContainer(containers.DeclarativeContainer):
    """As peças do carrosnaweb. A infra vem de fora, montada uma vez pelo container raiz."""

    settings = providers.Dependency(instance_of=Settings)
    network = providers.Dependency(instance_of=NetworkManager)
    database = providers.Dependency(instance_of=DatabaseRepository)

    # Singleton: o limitador precisa ser o mesmo para todos os workers da fonte,
    # senão cada um espera a própria vez e a rajada volta.
    limiter = providers.Singleton(
        RateLimiter, per_second=settings.provided.requests_per_second)

    request_factory = providers.Factory(CarrosWebRequestFactory, network=network)
    parser = providers.Factory(CarrosWebParser)

    crawler = providers.Factory(
        CarrosWebCrawler,
        factory=request_factory,
        parser=parser,
        db=database,
        limiter=limiter,
        source='carrosweb',
        concurrent=settings.provided.concurrent,
        try_limit=settings.provided.try_limit,
    )
