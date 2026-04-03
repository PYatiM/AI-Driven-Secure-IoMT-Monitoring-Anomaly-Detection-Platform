from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.db.models import DeviceStatus
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_text_input,
)


class DeviceRegistrationRequest(BaseModel):
    device_identifier: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    owner_user_id: int | None = Field(default=None, ge=1)

    @field_validator("device_identifier", mode="before")
    @classmethod
    def sanitize_device_identifier(cls, value: str) -> str:
        return require_non_empty_sanitized_text(value, field_name="device_identifier")

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, value: str) -> str:
        return require_non_empty_sanitized_text(value, field_name="name")

    @field_validator("device_type", mode="before")
    @classmethod
    def sanitize_device_type(cls, value: str) -> str:
        return require_non_empty_sanitized_text(value, field_name="device_type")

    @field_validator(
        "manufacturer",
        "model",
        "firmware_version",
        "location",
        mode="before",
    )
    @classmethod
    def sanitize_optional_text_fields(cls, value: str | None) -> str | None:
        return sanitize_text_input(value, empty_to_none=True)

    @field_validator("ip_address", mode="before")
    @classmethod
    def sanitize_ip_address(cls, value: str | None) -> str | None:
        return sanitize_text_input(value, lowercase=True, empty_to_none=True)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_identifier: str
    name: str
    device_type: str
    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    location: str | None
    ip_address: str | None
    status: DeviceStatus
    owner_user_id: int | None
    created_at: datetime
    updated_at: datetime
    api_key_prefix: str
    api_key_created_at: datetime
    last_authenticated_at: datetime | None


class DeviceRegistrationResponse(DeviceRead):
    api_key: str
    message: str
