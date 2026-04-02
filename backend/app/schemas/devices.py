from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import DeviceStatus


class DeviceRegistrationRequest(BaseModel):
    device_identifier: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    device_type: str = Field(..., max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    owner_user_id: int | None = Field(default=None, ge=1)


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
