from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import get_auth_service, get_current_session
from app.core.config import get_settings
from app.schemas.auth import AuthSessionResponse, ChangeInitialPasswordRequest, SignInRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

AUTH_ERROR_RESPONSES = {
    400: {"description": "Validation or business rule error."},
    401: {"description": "Authentication failed or no active session."},
    409: {"description": "State conflict for the requested auth operation."},
}


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    summary="Get current session",
    description="Returns the authenticated session resolved from the session cookie.",
    responses={401: {"description": "No active session."}},
)
async def get_current_user_session(session: AuthSessionResponse = Depends(get_current_session)) -> AuthSessionResponse:
    return session


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    summary="Sign in user",
    description="Authenticates a user with email and password and creates a session cookie.",
    responses=AUTH_ERROR_RESPONSES,
)
async def sign_in(
    payload: SignInRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    session, raw_token = await auth_service.sign_in(payload.email, payload.password)
    settings = get_settings()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.session_secure_cookie,
        samesite=settings.session_same_site,
        max_age=settings.session_expire_days * 24 * 60 * 60,
        path="/",
    )

    return session


@router.post(
    "/change-initial-password",
    response_model=AuthSessionResponse,
    summary="Change initial password",
    description="Allows a `New` user to replace the temporary password and become `Active`.",
    responses=AUTH_ERROR_RESPONSES,
)
async def change_initial_password(
    payload: ChangeInitialPasswordRequest,
    session_token: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    return await auth_service.change_initial_password(
        session_token,
        payload.newPassword,
        payload.confirmPassword,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out user",
    description="Deletes the active session and removes the session cookie.",
    responses={204: {"description": "Session closed."}},
)
async def sign_out(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    await auth_service.sign_out(session_token)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
