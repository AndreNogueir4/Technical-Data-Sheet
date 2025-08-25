import datetime
from ..commons.DatabaseRepository import DatabaseRepository

class LogRepository:
    def __init__(self):
        self.db = DatabaseRepository()

    async def insert_log(self, level, message, reference=None):
        log_entry = {
            'level': level,
            'message': message,
            'date': datetime.datetime.now().strftime("%d-%m-%Y"),
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'reference': reference,
        }
        await self.db.db.logs.insert_one(log_entry)