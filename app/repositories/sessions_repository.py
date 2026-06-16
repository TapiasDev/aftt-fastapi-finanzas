from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING

from app.core.database import get_database


class SessionsRepository:
    @property
    def collection(self):
        return get_database()["sessions"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("tokenHash", ASCENDING)], unique=True)
        await self.collection.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0)

    async def create_session(self, session: dict[str, Any]) -> None:
        await self.collection.insert_one(session)

    async def find_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"tokenHash": token_hash, "expiresAt": {"$gt": datetime.now(UTC)}}
        )

    async def delete_by_token_hash(self, token_hash: str) -> None:
        await self.collection.delete_one({"tokenHash": token_hash})
