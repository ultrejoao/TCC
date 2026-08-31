"""Schemas de autenticacao."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import password_issues


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class LoginResponse(BaseModel):
    """O access token vai no corpo E em cookie httpOnly.

    O corpo serve a clientes nao-navegador (script, app nativo); o navegador usa
    o cookie, que JavaScript nao consegue ler. O refresh token vai SOMENTE no
    cookie — nunca no corpo.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str
    user: UserOut


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(default="MANUTENCAO", pattern="^(ADMIN|MANUTENCAO|OPERADOR)$")

    @field_validator("password")
    @classmethod
    def _senha_forte(cls, v: str) -> str:
        problemas = password_issues(v)
        if problemas:
            raise ValueError("senha fraca: " + "; ".join(problemas))
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _senha_forte(cls, v: str) -> str:
        problemas = password_issues(v)
        if problemas:
            raise ValueError("senha fraca: " + "; ".join(problemas))
        return v
