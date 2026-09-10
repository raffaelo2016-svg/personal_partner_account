import re
from typing import Self

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import UserRole
from app.validation.ru_requisites import normalize_and_validate_partner_inn_kpp


def _validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Пароль должен быть минимум 8 символов")
    if not re.search(r"[A-Za-zА-Яа-я]", value):
        raise ValueError("Пароль должен содержать минимум одну букву")
    if not re.search(r"\d", value):
        raise ValueError("Пароль должен содержать минимум одну цифру")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class PasswordResetResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    user: "UserRead"


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class RefreshResponse(BaseModel):
    access_token: str


class UserRead(BaseModel):
    id: str
    email: str
    role: UserRole
    company_name: str | None = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    partner_type: str = Field(default="individual", pattern=r"^(individual|legal|entrepreneur)$")
    company_name: str = Field(min_length=1, max_length=255)
    director_name: str = Field(min_length=1, max_length=255)
    inn: str = Field(default="", max_length=12)
    phone: str = Field(min_length=10, max_length=30)
    short_name: str | None = None
    full_legal_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    kpp: str | None = None

    # Yandex SmartCaptcha. None для dev-окружения без ключа.
    captcha_token: str | None = None

    @model_validator(mode="after")
    def _normalize_inn_kpp(self) -> Self:
        inn, kpp = normalize_and_validate_partner_inn_kpp(self.partner_type, self.inn, self.kpp)
        self.inn = inn
        self.kpp = kpp
        return self


class RegisterResponse(BaseModel):
    message: str
    user: UserRead
