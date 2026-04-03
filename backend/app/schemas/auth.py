from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.users import UserRead
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_email_input,
    validate_secret_input,
)


class UserRegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def sanitize_full_name(cls, value: str) -> str:
        return require_non_empty_sanitized_text(value, field_name="full_name")

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, value: str) -> str:
        return sanitize_email_input(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_secret_input(value, field_name="password")


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, value: str) -> str:
        return sanitize_email_input(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_secret_input(value, field_name="password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
