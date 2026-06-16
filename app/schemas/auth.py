from pydantic import BaseModel, Field


class AuthUserResponse(BaseModel):
    id: str
    username: str
    status: str


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse


class AuthLoginResponse(AuthSessionResponse):
    accessToken: str


class SignInRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChangeInitialPasswordRequest(BaseModel):
    newPassword: str = Field(min_length=8)
    confirmPassword: str = Field(min_length=1)
    username: str | None = None
