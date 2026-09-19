"""Pydantic v2 request/response schemas."""
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    ward: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: str
    department_id: str | None = None
    department_name: str | None = None
    ward: str | None = None
    preferred_language: str
    is_active: bool


class RefreshIn(BaseModel):
    refresh_token: str


class UserAdminUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    department_id: str | None = None
