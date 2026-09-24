from typing import ClassVar
from datetime import datetime
from dataclasses import dataclass
from src.Model.JobStatus import JobStatus
from src.Common.utils import remove_accents


@dataclass
class Job:
    TIMESTAMP_FORMAT: ClassVar[str] = '%d-%m-%Y %H:%M:%S'

    source: str
    reference: str
    automaker: str
    model: str
    year: str
    version: str
    status: JobStatus = JobStatus.TODO
    timestamp: str = ''
    attempts: int = 0
    id: str | None = None

    def __post_init__(self) -> None:
        self.status = JobStatus(self.status)
        self.timestamp = self.timestamp or self.now()
        self.automaker = self.automaker.lower().strip()
        self.model = remove_accents(self.model.lower().strip())
        self.year = str(self.year)

    @classmethod
    def now(cls) -> str:
        return datetime.now().strftime(cls.TIMESTAMP_FORMAT)

    @classmethod
    def from_document(cls, document: dict) -> 'Job':
        return cls(
            source=document['source'],
            reference=document['reference'],
            automaker=document['automaker'],
            model=document['model'],
            year=document['year'],
            version=document['version'],
            status=document.get('status', JobStatus.TODO),
            timestamp=document.get('timestamp', ''),
            attempts=document.get('attempts', 0),
            id=str(document['_id']) if document.get('_id') is not None else None,
        )

    def to_document(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'status': str(self.status),
            'source': self.source,
            'reference': self.reference,
            'automaker': self.automaker,
            'model': self.model,
            'year': self.year,
            'version': self.version,
            'attempts': self.attempts,
        }

    @property
    def identity(self) -> dict:
        return {
            'source': self.source,
            'automaker': self.automaker,
            'model': self.model,
            'year': self.year,
            'version': self.version,
            'reference': self.reference,
        }

    @property
    def label(self) -> str:
        return f'{self.automaker} {self.model} {self.year} [{self.reference}]'
