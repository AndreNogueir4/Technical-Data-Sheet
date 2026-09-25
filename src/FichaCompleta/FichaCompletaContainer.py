from dependency_injector import containers, providers
from src.Common.settings import Settings
from src.Common.RateLimiter import RateLimiter
from src.Common.NetworkManager import NetworkManager
from src.Common.DatabaseRepository import DatabaseRepository
from src.FichaCompleta.FichaCompletaCrawler import FichaCompletaCrawler
from src.FichaCompleta.FichaCompletaParser import FichaCompletaParser
from src.FichaCompleta.FichaCompletaRequestFactory import FichaCompletaRequestFactory


class FichaCompletaContainer(containers.DeclarativeContainer):
    """As peças do fichacompleta. A infra vem de fora, montada uma vez pelo container raiz."""

    settings = providers.Dependency(instance_of=Settings)
    network = providers.Dependency(instance_of=NetworkManager)
    database = providers.Dependency(instance_of=DatabaseRepository)

    # Singleton: o limitador precisa ser o mesmo para todos os workers da fonte,
    # senão cada um espera a própria vez e a rajada volta.
    limiter = providers.Singleton(
        RateLimiter, per_second=settings.provided.requests_per_second)

    request_factory = providers.Factory(FichaCompletaRequestFactory, network=network, db=database)
    parser = providers.Factory(FichaCompletaParser)

    crawler = providers.Factory(
        FichaCompletaCrawler,
        factory=request_factory,
        parser=parser,
        db=database,
        limiter=limiter,
        source='fichacompleta',
        concurrent=settings.provided.concurrent,
        try_limit=settings.provided.try_limit,
    )
