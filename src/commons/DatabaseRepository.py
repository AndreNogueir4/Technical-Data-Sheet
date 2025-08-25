import unicodedata
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson.objectid import ObjectId


class DatabaseRepository:
    def __init__(self, uri="mongodb://localhost:27017", db_name="technical_sheet"):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

    def remove_accents(self, text: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(c)
        )

    async def insert_vehicle(self, automaker, model, year, version, reference):
        from src.logger.logger import get_logger
        logger = get_logger()

        model_clean = self.remove_accents(model.lower())

        exists = await self.vehicle_exists(automaker, model, year, version, reference)
        if exists:
            logger.info(f"Vehicle already exists: {automaker} {model} {year} ({reference})")
            return None

        document = {
            "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "status": "todo",
            "reference": reference,
            "automaker": automaker.lower(),
            "model": model_clean,
            "year": year,
            "version": version,
        }
        await self.db.vehicle.insert_one(document)
        logger.info(f"Inserted: {automaker} {model_clean} {year} ({reference})")
        return document

    async def vehicle_exists(self, automaker, model, year, version, reference):
        model_clean = self.remove_accents(model.lower())
        query = {
            "automaker": automaker.lower(),
            "model": model_clean,
            "year": year,
            "version": version,
            "reference": reference,
        }
        document = await self.db.vehicle.find_one(query)
        return document is not None

    async def find_vehicle_by_id(self, doc_id):
        from src.logger.logger import get_logger
        logger = get_logger()
        try:
            return await self.db.vehicle.find_one({"_id": ObjectId(doc_id)})
        except Exception as e:
            logger.error(f"Error fetching document: {e}")
            return None

    async def update_vehicle(self, doc_id, update_fields):
        from src.logger.logger import get_logger
        logger = get_logger()
        try:
            result = await self.db.vehicle.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_fields}
            )
            logger.info(f"Document updated, modified: {result.modified_count}")
            return result.modified_count
        except Exception as e:
            logger.error(f"Error updating: {e}")
            return 0

    async def insert_vehicle_specs(self, vehicle_id, automaker, model, version, year, result, equipments):
        from src.logger.logger import get_logger
        logger = get_logger()

        technical_data = {
            "automaker": automaker,
            "model": model,
            "version": version,
            "year": year,
            "result": result,
            "equipments": equipments,
        }

        try:
            await self.db.vehicle.update_one(
                {"_id": ObjectId(vehicle_id)},
                {"$set": {"status": "done"}}
            )
            await self.db.vehicle_specs.insert_one(technical_data)
            logger.info(f"Specs inserted for vehicle {vehicle_id}")
            return True
        except Exception as e:
            logger.error(f"Error inserting specs: {e}")
            return None

    async def get_vehicles_by_reference(self, reference):
        from src.logger.logger import get_logger
        logger = get_logger()
        try:
            await self.db.vehicle.update_many(
                {"reference": reference, "status": "todo"},
                {"$set": {"status": "in_progress"}}
            )
            cursor = self.db.vehicle.find(
                {"reference": reference, "status": "in_progress"}
            )
            docs = await cursor.to_list(length=None)
            logger.info(f"{len(docs)} vehicles set as in_progress for ref: {reference}")
            return docs
        except Exception as e:
            logger.error(f"Error getting vehicles by ref {reference}: {e}")
            return []

    async def insert_log(self, log_entry, reference=None):
        log_entry["date"] = datetime.now().strftime("%d-%m-%Y")
        log_entry["time"] = datetime.now().strftime("%H:%M:%S")
        log_entry["reference"] = reference
        await self.db.logs.insert_one(log_entry)

    async def get_proxies(self) -> list[str]:
        """ Busca todos os proxies ativos na collection 'proxies' """
        proxies = await self.db['proxies'].find({'status': 'active'}).to_list(100)
        return [p['proxy'] for p in proxies]

    def vehicle_helper(self, vehicle) -> dict:
        return {
            "id": str(vehicle["_id"]),
            "sheet_code": vehicle.get("sheet_code"),
            "automaker": vehicle["automaker"],
            "model": vehicle["model"],
            "version": vehicle["version"],
            "year": vehicle["year"],
            "result": vehicle.get("result"),
            "equipments": vehicle.get("equipments"),
        }

    def user_helper(self, user) -> dict:
        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "api_key": user["api_key"],
            "is_active": user["is_active"],
            "created_at": user["created_at"],
            "last_used": user.get("last_used"),
        }

    def request_log_helper(self, log) -> dict:
        return {
            "id": str(log["_id"]),
            "endpoint": log["endpoint"],
            "params": log["params"],
            "date": log["date"],
            "time": log["time"],
            "user_id": log["user_id"],
        }
