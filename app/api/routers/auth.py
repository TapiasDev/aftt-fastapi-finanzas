from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_auth_service, get_current_session, get_current_session_token
from app.schemas.auth import AuthLoginResponse, AuthSessionResponse, ChangeInitialPasswordRequest, SignInRequest
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
    description="Returns the authenticated session resolved from the bearer token.",
    responses={401: {"description": "No active session."}},
)
async def get_current_user_session(session: AuthSessionResponse = Depends(get_current_session)) -> AuthSessionResponse:
    return session


@router.post(
    "/login",
    response_model=AuthLoginResponse,
    summary="Sign in user",
    description="Authenticates a user with username and password and returns a bearer token.",
    responses=AUTH_ERROR_RESPONSES,
)
async def sign_in(
    payload: SignInRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthLoginResponse:
    session, raw_token = await auth_service.sign_in(payload.username, payload.password)
    return AuthLoginResponse(user=session.user, accessToken=raw_token)


@router.post(
    "/change-initial-password",
    response_model=AuthSessionResponse,
    summary="Change initial password",
    description="Allows a `New` user to replace the temporary password, optionally update the username and become `Active`.",
    responses=AUTH_ERROR_RESPONSES,
)
async def change_initial_password(
    payload: ChangeInitialPasswordRequest,
    session_token: str = Depends(get_current_session_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    return await auth_service.change_initial_password(
        session_token,
        payload.newPassword,
        payload.confirmPassword,
        payload.username,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out user",
    description="Deletes the active session associated with the current bearer token.",
    responses={204: {"description": "Session closed."}},
)
async def sign_out(
    response: Response,
    session_token: str = Depends(get_current_session_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    await auth_service.sign_out(session_token)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
