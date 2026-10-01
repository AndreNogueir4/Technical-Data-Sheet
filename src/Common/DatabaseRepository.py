import logging
from datetime import datetime
from contextlib import asynccontextmanager
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorClient
from src.Model.Job import Job
from src.Model.JobStatus import JobStatus


class DatabaseRepository:
    """Acesso ao MongoDB. A fila de trabalho vive na collection `job`."""

    # O `_id` é um ObjectId: ele não atravessa JSON, e quem lê a ficha pela API não
    # tem o que fazer com ele. A identidade que importa é `source` + `reference`.
    NO_ID = {'_id': 0}

    def __init__(self, uri: str = 'mongodb://localhost:27017/',
                 db_name: str = 'technical_sheet'):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self._logger = logging.getLogger(type(self).__module__)

    def close(self) -> None:
        self.client.close()

    @classmethod
    @asynccontextmanager
    async def create(cls, uri: str = 'mongodb://localhost:27017/',
                     db_name: str = 'technical_sheet'):
        """Abre o repositório com os índices prontos e fecha o cliente na saída."""
        database = cls(uri, db_name)
        await database.ensure_indexes()
        await database.reclaim_stale_jobs()
        try:
            yield database
        finally:
            database.close()

    async def ensure_indexes(self) -> None:
        await self.db.job.create_index([('source', 1), ('status', 1), ('attempts', 1)])
        await self.db.job.create_index(
            [('source', 1), ('automaker', 1), ('model', 1), ('year', 1),
             ('version', 1), ('reference', 1)],
            name='job_identity',
        )
        await self.db.vehicle_specs.create_index(
            [('source', 1), ('reference', 1), ('montadora', 1),
             ('modelo', 1), ('ano', 1), ('versao', 1)],
            name='sheet_identity',
        )
        await self.db.logs.create_index([('date', -1), ('level', 1)])

    async def reclaim_stale_jobs(self) -> int:
        """Devolve à fila os jobs que ficaram reservados por uma run interrompida.

        `pop_pending_jobs` marca o job como `in_progress` antes de coletar. Se o
        processo morre com jobs em voo — Ctrl+C, queda, SIGTERM — eles ficam nesse
        estado para sempre, porque a consulta da fila só procura `todo`. Roda na
        subida, quando por definição não há nada em voo.
        """
        result = await self.db.job.update_many(
            {'status': JobStatus.IN_PROGRESS.value},
            {'$set': {'status': JobStatus.TODO.value}},
        )
        if result.modified_count:
            self._logger.info(f'reclaimed {result.modified_count} jobs left in progress')
        return result.modified_count

    async def insert_job(self, job: Job) -> Job | None:
        """Enfileira um job novo. Devolve None quando o veículo já está catalogado."""
        if await self.job_exists(job):
            self._logger.info(f'Job already exists: {job.label}')
            return None

        result = await self.db.job.insert_one(job.to_document())
        job.id = str(result.inserted_id)
        self._logger.info(f'Inserted: {job.label}')
        return job

    async def job_exists(self, job: Job) -> bool:
        return await self.db.job.find_one(job.identity) is not None

    async def find_job_by_id(self, doc_id: str) -> Job | None:
        try:
            document = await self.db.job.find_one({'_id': ObjectId(doc_id)})
        except Exception:
            self._logger.exception(f'Error fetching job {doc_id}')
            return None
        return Job.from_document(document) if document else None

    async def update_job(self, doc_id: str, update_fields: dict) -> int:
        try:
            result = await self.db.job.update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': update_fields},
            )
            return result.modified_count
        except Exception:
            self._logger.exception(f'Error updating job {doc_id}')
            return 0

    async def pop_pending_jobs(self, source: str, limit: int = 2) -> list[Job]:
        """Reserva até `limit` jobs de uma fonte, marcando-os como `in_progress`.

        Os menos tentados vêm primeiro: um job reenfileirado depois de um bloqueio
        temporário cai atrás de todos os intocados em vez de ser repetido na hora.
        """
        jobs: list[Job] = []
        for _ in range(limit):
            document = await self.db.job.find_one_and_update(
                {'source': source, 'status': JobStatus.TODO.value},
                {'$set': {'status': JobStatus.IN_PROGRESS.value}},
                sort=[('attempts', 1)],
                return_document=ReturnDocument.AFTER,
            )
            if document is None:
                break
            jobs.append(Job.from_document(document))
        return jobs

    async def upsert_automaker(self, automaker: str, models: list[str]) -> None:
        await self.db.fichacompleta_automakers.update_one(
            {'automaker': automaker},
            {'$set': {'models': models, 'updated_at': datetime.now()}},
            upsert=True,
        )

    async def upsert_model(self, automaker: str, model: str, reference: str,
                           versions: dict, years: list[str]) -> None:
        await self.db.fichacompleta_models.update_one(
            {'automaker': automaker, 'model': model},
            {'$set': {
                'reference': reference,
                'versions': versions,
                'years': years,
                'updated_at': datetime.now(),
            }},
            upsert=True,
        )

    async def save_sheet(self, sheet: dict) -> None:
        """Grava a ficha do veículo, substituindo a anterior se já existir.

        `replace_one` e não `update_one`: um job recoletado — depois de um 429, de um
        backoff ou de uma run interrompida — substitui a ficha em vez de criar uma
        segunda com a mesma identidade.

        Tem de ser substituição, não `$set`: as fichas trazem chaves com ponto no nome
        ('Rotação potência máx.'), e num operador de update o ponto é separador de
        caminho — o Mongo recusa com 'contains an empty field name'. Num documento de
        substituição a chave vai literal, como ia no `insert_one`.
        """
        await self.db.vehicle_specs.replace_one(
            self.sheet_identity(sheet), sheet, upsert=True)

    async def find_sheet(self, source: str, reference: str) -> dict | None:
        """A ficha de uma referência, sem o `_id` do Mongo."""
        return await self.db.vehicle_specs.find_one(
            {'source': source, 'reference': reference}, self.NO_ID)

    async def find_sheets(self, query: dict, limit: int = 20, skip: int = 0) -> list[dict]:
        """Uma página de fichas que batem com `query`.

        A ordem é a do índice `sheet_identity` — `source` e `reference` — e não a de
        inserção: sem ordem estável, duas páginas seguidas podem repetir uma ficha e
        pular outra.
        """
        cursor = (self.db.vehicle_specs.find(query, self.NO_ID)
                  .sort([('source', 1), ('reference', 1)]).skip(skip).limit(limit))
        return await cursor.to_list(length=limit)

    async def count_sheets(self, query: dict) -> int:
        return await self.db.vehicle_specs.count_documents(query)

    async def find_job_by_reference(self, source: str, reference: str) -> Job | None:
        """O job de uma referência — é dele que sai o resto da identidade do veículo."""
        document = await self.db.job.find_one({'source': source, 'reference': reference})
        return Job.from_document(document) if document else None

    @staticmethod
    def sheet_identity(sheet: dict) -> dict:
        """Os campos que identificam um veículo dentro de `vehicle_specs`."""
        return {key: sheet.get(key)
                for key in ('source', 'reference', 'montadora', 'modelo', 'ano', 'versao')}

    async def insert_log(self, level: str, message: str, reference: str = '') -> None:
        """Grava uma linha na collection `logs`.

        O console recebe tudo pelo `logging`; aqui entra só o que precisa sobreviver à
        execução — começo e fim de cada run, resultado do catálogo, bloqueio e crash.
        """
        now = datetime.now()
        await self.db.logs.insert_one({
            'level': level,
            'message': message,
            'reference': reference,
            'date': now.strftime('%d-%m-%Y'),
            'time': now.strftime('%H:%M:%S'),
        })

    async def get_proxies(self) -> list[str]:
        proxies = await self.db.proxies.find({'status': 'active'}).to_list(100)
        return [p['proxy'] for p in proxies]
