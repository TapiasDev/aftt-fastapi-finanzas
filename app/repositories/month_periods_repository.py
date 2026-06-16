from typing import Any

from pymongo import ASCENDING

from app.core.database import get_database
from app.utils.dates import create_month_aggregate, utc_now


class MonthPeriodsRepository:
    @property
    def collection(self):
        return get_database()["month_periods"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            [("userId", ASCENDING), ("year", ASCENDING), ("monthNumber", ASCENDING)], unique=True
        )
        await self.collection.create_index([("id", ASCENDING)], unique=True)
        await self.collection.create_index([("userId", ASCENDING), ("year", ASCENDING)])

    async def ensure_year_data(self, user_id: str, year: int) -> list[dict[str, Any]]:
        existing_months = await self.list_year_months(user_id, year)

        if existing_months:
            return existing_months

        documents = [create_month_aggregate(user_id, year, month_number) for month_number in range(1, 13)]

        if documents:
            await self.collection.insert_many(documents)

        return await self.list_year_months(user_id, year)

    async def list_available_years(self, user_id: str) -> list[int]:
        return await self.collection.distinct("year", {"userId": user_id})

    async def list_year_months(self, user_id: str, year: int) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {"userId": user_id, "year": year},
            {"_id": 0},
        ).sort("monthNumber", ASCENDING)
        return await cursor.to_list(length=None)

    async def list_months_from_year(self, user_id: str, start_year: int) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {"userId": user_id, "year": {"$gte": start_year}},
            {"_id": 0},
        ).sort([("year", ASCENDING), ("monthNumber", ASCENDING)])
        return await cursor.to_list(length=None)

    async def find_month(self, user_id: str, year: int, month_number: int) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"userId": user_id, "year": year, "monthNumber": month_number},
            {"_id": 0},
        )

    async def find_month_by_id(self, user_id: str, month_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"userId": user_id, "id": month_id}, {"_id": 0})

    async def find_month_by_fortnight_id(self, user_id: str, fortnight_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"userId": user_id, "fortnights.id": fortnight_id},
            {"_id": 0},
        )

    async def find_month_by_expense_id(self, user_id: str, expense_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"userId": user_id, "expenses.id": expense_id},
            {"_id": 0},
        )

    async def replace_month(self, user_id: str, month_id: str, month_document: dict[str, Any]) -> dict[str, Any] | None:
        month_document["updatedAt"] = utc_now()
        await self.collection.replace_one({"userId": user_id, "id": month_id}, month_document)
        return await self.find_month_by_id(user_id, month_id)
