from datetime import datetime

from pydantic import EmailStr, Field, SecretStr

from app.schemas.common import CamelModel


class UserCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)


class UserLogin(CamelModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class UserResponse(CamelModel):
    id: str
    role: str
    name: str
    email: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class TokenResponse(CamelModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    user: UserResponse