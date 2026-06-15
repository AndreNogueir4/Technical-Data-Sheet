import unicodedata
from datetime import datetime
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


class DatabaseRepository:
    def __init__(self, uri: str = 'mongodb://admin:admin@localhost:27017/', db_name: str = 'technical_sheet'):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

    async def insert_vehicle(self, automaker: str, model: str, year: str, version: str, reference: str):
        from src.Logger import get_logger
        logger = get_logger()

        model_clean = self._remove_accents(model.lower())
        if await self.vehicle_exists(automaker, model, year, version, reference):
            logger.info(f'Vehicle already exists: {automaker} {model} {year} ({reference})')
            return None

        document = {
            'timestamp': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
            'status': 'todo',
            'reference': reference,
            'automaker': automaker.lower(),
            'model': model_clean,
            'year': year,
            'version': version,
        }
        await self.db.vehicle.insert_one(document)
        logger.info(f'Inserted: {automaker} {model_clean} {year} ({reference})')
        return document

    async def vehicle_exists(self, automaker: str, model: str, year: str, version: str, reference: str) -> bool:
        model_clean = self._remove_accents(model.lower())
        doc = await self.db.vehicle.find_one({
            'automaker': automaker.lower(),
            'model': model_clean,
            'year': year,
            'version': version,
            'reference': reference,
        })
        return doc is not None

    async def find_vehicle_by_id(self, doc_id: str):
        from src.Logger import get_logger
        logger = get_logger()
        try:
            return await self.db.vehicle.find_one({'_id': ObjectId(doc_id)})
        except Exception as e:
            logger.error(f'Error fetching document: {e}')
            return None

    async def update_vehicle(self, doc_id: str, update_fields: dict) -> int:
        from src.Logger import get_logger
        logger = get_logger()
        try:
            result = await self.db.vehicle.update_one(
                {'_id': ObjectId(doc_id)},
                {'$set': update_fields},
            )
            return result.modified_count
        except Exception as e:
            logger.error(f'Error updating: {e}')
            return 0

    async def pop_pending_jobs(self, limit: int = 2) -> list[dict]:
        docs = []
        for _ in range(limit):
            doc = await self.db.vehicle.find_one_and_update(
                {'status': 'todo'},
                {'$set': {'status': 'in_progress'}},
                return_document=True,
            )
            if doc is None:
                break
            docs.append(doc)
        return docs

    async def get_vehicles_by_reference(self, reference: str) -> list[dict]:
        from src.Logger import get_logger
        logger = get_logger()
        try:
            await self.db.vehicle.update_many(
                {'reference': reference, 'status': 'todo'},
                {'$set': {'status': 'in_progress'}},
            )
            cursor = self.db.vehicle.find({'reference': reference, 'status': 'in_progress'})
            docs = await cursor.to_list(length=None)
            logger.info(f'{len(docs)} vehicles set as in_progress for ref: {reference}')
            return docs
        except Exception as e:
            logger.error(f'Error getting vehicles by ref {reference}: {e}')
            return []

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

    async def get_scraped_hrefs(self, automaker: str, model: str) -> set[str]:
        doc = await self.db.fichacompleta_models.find_one(
            {'automaker': automaker, 'model': model},
            {'scraped_hrefs': 1},
        )
        return set(doc.get('scraped_hrefs', [])) if doc else set()

    async def mark_href_scraped(self, automaker: str, model: str, href: str) -> None:
        await self.db.fichacompleta_models.update_one(
            {'automaker': automaker, 'model': model},
            {'$addToSet': {'scraped_hrefs': href}},
        )

    async def save_sheet(self, sheet: dict) -> None:
        await self.db.vehicle_specs.insert_one(sheet)

    async def insert_vehicle_specs(self, vehicle_id, automaker: str, model: str, version: str,
                                   year: str, result: dict, equipments) -> bool:
        from src.Logger import get_logger
        logger = get_logger()
        try:
            await self.db.vehicle.update_one({'_id': ObjectId(vehicle_id)}, {'$set': {'status': 'done'}})
            await self.db.vehicle_specs.insert_one({
                'automaker': automaker,
                'model': model,
                'version': version,
                'year': year,
                'result': result,
                'equipments': equipments,
            })
            logger.info(f'Specs inserted for vehicle {vehicle_id}')
            return True
        except Exception as e:
            logger.error(f'Error inserting specs: {e}')
            return False

    async def get_proxies(self) -> list[str]:
        proxies = await self.db.proxies.find({'status': 'active'}).to_list(100)
        return [p['proxy'] for p in proxies]

    @staticmethod
    def _remove_accents(text: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
