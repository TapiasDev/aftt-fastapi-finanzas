from app.core.exceptions import AppError
from app.core.security import (
    create_session_token,
    get_session_expiration,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.repositories.sessions_repository import SessionsRepository
from app.repositories.users_repository import UsersRepository
from app.schemas.auth import AuthSessionResponse
from app.utils.dates import utc_now


class AuthService:
    def __init__(self) -> None:
        self.users_repository = UsersRepository()
        self.sessions_repository = SessionsRepository()

    async def get_current_session(self, session_token: str | None) -> AuthSessionResponse | None:
        if not session_token:
            return None

        token_hash = hash_session_token(session_token)
        session_document = await self.sessions_repository.find_by_token_hash(token_hash)

        if not session_document:
            return None

        user_document = await self.users_repository.find_by_id(session_document["userId"])

        if not user_document:
            return None

        return self._build_session_response(user_document)

    async def sign_in(self, username: str, password: str) -> tuple[AuthSessionResponse, str]:
        user_document = await self.users_repository.find_by_username(username)

        if not user_document or not verify_password(password, user_document["passwordHash"]):
            raise AppError("Invalid username or password.", 401)

        raw_token = create_session_token()
        token_hash = hash_session_token(raw_token)

        await self.sessions_repository.create_session(
            {
                "userId": user_document["id"],
                "tokenHash": token_hash,
                "createdAt": utc_now(),
                "expiresAt": get_session_expiration(),
            }
        )

        return self._build_session_response(user_document), raw_token

    async def change_initial_password(
        self,
        session_token: str | None,
        new_password: str,
        confirm_password: str,
        username: str | None,
    ) -> AuthSessionResponse:
        if not session_token:
            raise AppError("No active session was found.", 401)

        if new_password != confirm_password:
            raise AppError("Password confirmation must match the new password.", 400)

        if len(new_password) < 8:
            raise AppError("New password must contain at least 8 characters.", 400)

        current_session = await self.get_current_session(session_token)

        if not current_session:
            raise AppError("No active session was found.", 401)

        if current_session.user.status != "New":
            raise AppError("Initial password change is only available for new users.", 409)

        normalized_username = username.strip().lower() if username is not None else None

        if normalized_username == "":
            normalized_username = None

        if normalized_username is not None:
            existing_user = await self.users_repository.find_by_username(normalized_username)

            if existing_user and existing_user["id"] != current_session.user.id:
                raise AppError("Username is already in use.", 409)

        updated_user = await self.users_repository.update_password_status_and_username(
            current_session.user.id,
            hash_password(new_password),
            normalized_username,
        )

        if not updated_user:
            raise AppError("Authenticated user was not found.", 404)

        return self._build_session_response(updated_user)

    async def sign_out(self, session_token: str | None) -> None:
        if not session_token:
            return

        await self.sessions_repository.delete_by_token_hash(hash_session_token(session_token))

    @staticmethod
    def _build_session_response(user_document: dict) -> AuthSessionResponse:
        return AuthSessionResponse(
            user={
                "id": user_document["id"],
                "username": user_document["username"],
                "status": user_document["status"],
            }
        )
