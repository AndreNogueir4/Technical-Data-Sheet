import os
from argparse import Namespace
from dataclasses import dataclass

STAGES = ('catalog', 'worker')

_DEFAULT_MONGO_URI = 'mongodb://localhost:27017/'
_DEFAULT_MONGO_DB = 'technical_sheet'


@dataclass(frozen=True)
class Settings:
    """Everything the application needs to know, resolved from CLI args and the environment."""

    site: str = 'all'
    stage: str = 'all'
    loop: bool = False
    interval: int = 3600
    mongo_uri: str = _DEFAULT_MONGO_URI
    mongo_db: str = _DEFAULT_MONGO_DB
    batch_size: int = 4
    concurrency: int = 2
    delay: tuple[float, float] = (10.0, 50.0)
    impersonate: str = 'chrome124'

    @classmethod
    def from_args(cls, args: Namespace) -> 'Settings':
        return cls(
            site=args.site,
            stage=args.stage,
            loop=args.loop,
            interval=args.interval,
            mongo_uri=os.getenv('MONGO_URI', _DEFAULT_MONGO_URI),
            mongo_db=os.getenv('MONGO_DB', _DEFAULT_MONGO_DB),
            batch_size=int(os.getenv('BATCH_SIZE', '4')),
            concurrency=int(os.getenv('CONCURRENCY', '2')),
            delay=(float(os.getenv('MIN_DELAY', '10')), float(os.getenv('MAX_DELAY', '50'))),
            impersonate=os.getenv('CFFI_IMPERSONATE', 'chrome124'),
        )

    @property
    def stages(self) -> tuple[str, ...]:
        return STAGES if self.stage == 'all' else (self.stage,)
