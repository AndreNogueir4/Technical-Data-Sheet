import logging
import unicodedata
from datetime import datetime
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorClient


class DatabaseRepository:
    def __init__(self, uri: str = 'mongodb://localhost:27017/',
                 db_name: str = 'technical_sheet', logger: logging.Logger | None = None):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self._logger = logger or logging.getLogger('database')

    async def ensure_indexes(self) -> None:
        await self.db.vehicle.create_index([('source', 1), ('status', 1), ('attempts', 1)])
        await self.db.vehicle.create_index(
            [('source', 1), ('automaker', 1), ('model', 1), ('year', 1),
             ('version', 1), ('reference', 1)],
            name='vehicle_identity',
        )

    async def insert_vehicle(self, source: str, automaker: str, model: str, year: str,
                             version: str, reference: str) -> dict | None:
        if await self.vehicle_exists(source, automaker, model, year, version, reference):
            self._logger.info(f'Vehicle already exists: {automaker} {model} {year} ({reference})')
            return None

        document = {
            'timestamp': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
            'status': 'todo',
            'source': source,
            'reference': reference,
            'automaker': automaker.lower(),
            'model': self._remove_accents(model.lower()),
            'year': year,
            'version': version,
        }
        await self.db.vehicle.insert_one(document)
        self._logger.info(f'Inserted: {automaker} {document["model"]} {year} ({reference})')
        return document

    async def vehicle_exists(self, source: str, automaker: str, model: str, year: str,
                             version: str, reference: str) -> bool:
        doc = await self.db.vehicle.find_one({
            'source': source,
            'automaker': automaker.lower(),
            'model': self._remove_accents(model.lower()),
            'year': year,
            'version': version,
            'reference': reference,
        })
        return doc is not None

    async def find_vehicle_by_id(self, doc_id: str) -> dict | None:
        try:
            return await self.db.vehicle.find_one({'_id': ObjectId(doc_id)})
        except Exception:
            self._logger.exception(f'Error fetching vehicle {doc_id}')
            return None

    async def update_vehicle(self, doc_id: str, update_fields: dict) -> int:
        try:
            result = await self.db.vehicle.update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': update_fields},
            )
            return result.modified_count
        except Exception:
            self._logger.exception(f'Error updating vehicle {doc_id}')
            return 0

    async def pop_pending_jobs(self, source: str, limit: int = 2) -> list[dict]:
        """Claim up to `limit` queued jobs of one source, flipping them to in_progress.

        Least-tried jobs come first: a job requeued after a transient block lands behind
        every untouched one instead of being retried straight away.
        """
        docs = []
        for _ in range(limit):
            doc = await self.db.vehicle.find_one_and_update(
                {'source': source, 'status': 'todo'},
                {'$set': {'status': 'in_progress'}},
                sort=[('attempts', 1)],
                return_document=ReturnDocument.AFTER,
            )
            if doc is None:
                break
            docs.append(doc)
        return docs

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
        await self.db.vehicle_specs.insert_one(sheet)

    async def get_proxies(self) -> list[str]:
        proxies = await self.db.proxies.find({'status': 'active'}).to_list(100)
        return [p['proxy'] for p in proxies]

    @staticmethod
    def _remove_accents(text: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
