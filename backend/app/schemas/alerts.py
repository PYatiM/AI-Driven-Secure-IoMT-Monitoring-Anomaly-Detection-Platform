from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.db.models import AlertSeverity, AlertStatus
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_text_input,
)


class AlertCreate(BaseModel):
    device_id: int = Field(..., ge=1)
    data_id: int | None = Field(default=None, ge=1)
    assigned_user_id: int | None = Field(default=None, ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.OPEN
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    triggered_at: datetime | None = None

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, value: str) -> str:
        return require_non_empty_sanitized_text(value, field_name="title")

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, value: str | None) -> str | None:
        return sanitize_text_input(value, empty_to_none=True)


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    data_id: int | None
    assigned_user_id: int | None
    title: str
    description: str | None
    severity: AlertSeverity
    status: AlertStatus
    anomaly_score: float | None
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertPage(BaseModel):
    items: list[AlertRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    device_id: int
    severity: AlertSeverity | None
    status: AlertStatus | None
    start_time: datetime | None
    end_time: datetime | None
