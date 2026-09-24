from enum import StrEnum


class SheetMode(StrEnum):
    ALL = 'all'
    CATALOG = 'catalog'
    WORKER = 'worker'

    @classmethod
    def choices(cls) -> tuple[str, ...]:
        return tuple(mode.value for mode in cls)

    @property
    def stages(self) -> tuple['SheetMode', ...]:
        return (SheetMode.CATALOG, SheetMode.WORKER) if self is SheetMode.ALL else (self,)

    @property
    def keep_alive(self) -> bool:
        return self is SheetMode.WORKER
