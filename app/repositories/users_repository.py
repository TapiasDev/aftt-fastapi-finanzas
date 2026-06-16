from typing import Any

from bson import ObjectId
from pymongo import ASCENDING

from app.core.database import get_database


class UsersRepository:
    @property
    def collection(self):
        return get_database()["users"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("username", ASCENDING)], unique=True)

    async def find_by_username(self, username: str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"username": username.strip().lower()})
        return await self._normalize_user_document(document)

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"id": user_id})

        if document is None:
            try:
                document = await self.collection.find_one({"_id": ObjectId(user_id)})
            except Exception:
                document = None

        return await self._normalize_user_document(document)

    async def update_password_status_and_username(
        self,
        user_id: str,
        password_hash: str,
        username: str | None = None,
    ) -> dict[str, Any] | None:
        fields_to_update: dict[str, Any] = {
            "passwordHash": password_hash,
            "status": "Active",
        }

        if username is not None:
            fields_to_update["username"] = username.strip().lower()

        await self.collection.update_one(
            {"id": user_id},
            {
                "$set": fields_to_update,
            },
        )
        return await self.find_by_id(user_id)

    async def _normalize_user_document(self, document: dict[str, Any] | None) -> dict[str, Any] | None:
        if document is None:
            return None

        public_id = document.get("id") or str(document["_id"])
        normalized_username = str(document.get("username", "")).strip().lower()
        normalized_status = str(document.get("status", "")).strip().title()

        if document.get("id") != public_id:
            await self.collection.update_one({"_id": document["_id"]}, {"$set": {"id": public_id}})
            document["id"] = public_id

        updates: dict[str, Any] = {}

        if document.get("username") != normalized_username:
            updates["username"] = normalized_username
            document["username"] = normalized_username

        if document.get("status") != normalized_status:
            updates["status"] = normalized_status
            document["status"] = normalized_status

        if updates:
            await self.collection.update_one({"_id": document["_id"]}, {"$set": updates})

        return document
