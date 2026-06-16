from pydantic import BaseModel, EmailStr


class UserDocument(BaseModel):
    id: str
    email: EmailStr
    passwordHash: str
    status: str
