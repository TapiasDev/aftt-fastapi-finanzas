from fastapi import Depends
from fastapi.security import APIKeyCookie

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.auth import AuthSessionResponse
from app.services.auth_service import AuthService

session_cookie_scheme = APIKeyCookie(
    name=get_settings().session_cookie_name,
    auto_error=False,
    description="Cookie de sesión HttpOnly creada por `POST /auth/login`.",
)


def get_auth_service() -> AuthService:
    return AuthService()


async def get_current_session(
    auth_service: AuthService = Depends(get_auth_service),
    session_token: str | None = Depends(session_cookie_scheme),
) -> AuthSessionResponse:
    session = await auth_service.get_current_session(session_token)

    if not session:
        raise AppError("No active session.", 401)

    return session


async def get_current_active_session(
    session: AuthSessionResponse = Depends(get_current_session),
) -> AuthSessionResponse:
    if session.user.status != "Active":
        raise AppError("User must complete the initial password change.", 403)

    return session
