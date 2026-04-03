from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.db.models import UserRole
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_email_input,
    validate_secret_input,
)


class UserCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.ANALYST
    is_active: bool = True

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


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
