from pydantic import BaseModel


class UserDocument(BaseModel):
    id: str
    username: str
    passwordHash: str
    status: str
