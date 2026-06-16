from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError
from app.schemas.auth import AuthSessionResponse
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer token returned by `POST /auth/login`.",
)


def get_auth_service() -> AuthService:
    return AuthService()


async def get_current_session(
    auth_service: AuthService = Depends(get_auth_service),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthSessionResponse:
    session = await auth_service.get_current_session(credentials.credentials if credentials else None)

    if not session:
        raise AppError("No active session.", 401)

    return session


async def get_current_session_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not credentials:
        raise AppError("No active session.", 401)

    return credentials.credentials


async def get_current_active_session(
    session: AuthSessionResponse = Depends(get_current_session),
) -> AuthSessionResponse:
    if session.user.status != "Active":
        raise AppError("User must complete the initial password change.", 403)

    return session
