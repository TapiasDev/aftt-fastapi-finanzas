from typing import Any

from pymongo import ASCENDING

from app.core.database import get_database
from app.utils.dates import utc_now


class ExpenseRecurrencesRepository:
    @property
    def collection(self):
        return get_database()["expense_recurrences"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("id", ASCENDING)], unique=True)
        await self.collection.create_index([("userId", ASCENDING), ("isActive", ASCENDING)])
        await self.collection.create_index([("userId", ASCENDING), ("startYear", ASCENDING), ("startMonth", ASCENDING)])

    async def create_recurrence(self, recurrence: dict[str, Any]) -> None:
        await self.collection.insert_one(recurrence)

    async def find_by_id(self, recurrence_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"id": recurrence_id}, {"_id": 0})

    async def list_active_for_user(self, user_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"userId": user_id, "isActive": True}, {"_id": 0})
        return await cursor.to_list(length=None)

    async def update_recurrence(self, recurrence_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates["updatedAt"] = utc_now()
        await self.collection.update_one({"id": recurrence_id}, {"$set": updates})
        return await self.find_by_id(recurrence_id)

    async def deactivate_recurrence(self, recurrence_id: str) -> None:
        await self.update_recurrence(recurrence_id, {"isActive": False})
