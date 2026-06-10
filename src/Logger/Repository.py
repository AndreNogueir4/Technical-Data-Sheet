import datetime
from src.Common.DatabaseRepository import DatabaseRepository


class LogRepository:
    def __init__(self):
        self.db = DatabaseRepository()

    async def insert_log(self, level: str, message: str, reference: str | None = None):
        await self.db.db.logs.insert_one({
            'level': level,
            'message': message,
            'reference': reference,
            'date': datetime.datetime.now().strftime('%d-%m-%Y'),
            'time': datetime.datetime.now().strftime('%H:%M:%S'),
        })
