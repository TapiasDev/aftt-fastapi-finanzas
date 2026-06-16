from pydantic import BaseModel, EmailStr, Field


class AuthUserResponse(BaseModel):
    id: str
    email: EmailStr
    status: str


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ChangeInitialPasswordRequest(BaseModel):
    newPassword: str = Field(min_length=8)
    confirmPassword: str = Field(min_length=1)
