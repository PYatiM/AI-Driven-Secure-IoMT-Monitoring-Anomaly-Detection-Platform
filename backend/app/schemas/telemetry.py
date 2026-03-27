from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TelemetryIngestRequest(BaseModel):
    recorded_at: datetime
    metric_name: str = Field(..., max_length=100)
    metric_type: str | None = Field(default=None, max_length=100)
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = Field(default=None, max_length=50)
    payload: dict[str, Any] | None = None

    @field_validator("recorded_at", mode="after")
    @classmethod
    def normalize_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("recorded_at cannot be more than five minutes in the future.")
        return value

    @model_validator(mode="after")
    def validate_measurement_payload(self) -> "TelemetryIngestRequest":
        if (
            self.value_numeric is None
            and self.value_text is None
            and not self.payload
        ):
            raise ValueError(
                "At least one of value_numeric, value_text, or payload must be provided."
            )
        return self


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    recorded_at: datetime
    metric_name: str
    metric_type: str | None
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    payload: dict[str, Any] | None
    ingested_at: datetime
    created_at: datetime
    updated_at: datetime


class TelemetryPage(BaseModel):
    items: list[TelemetryRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    device_id: int
    start_time: datetime | None
    end_time: datetime | None
