from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    device_id: int = Field(..., ge=1)
    data_id: int | None = Field(default=None, ge=1)
    assigned_user_id: int | None = Field(default=None, ge=1)
    title: str = Field(..., max_length=255)
    description: str | None = None
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.OPEN
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    triggered_at: datetime | None = None


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
