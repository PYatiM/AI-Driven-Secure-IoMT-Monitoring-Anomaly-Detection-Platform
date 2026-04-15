from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import AlertSeverity, AlertStatus, DeviceStatus


class MonitoringDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_identifier: str
    name: str
    device_type: str
    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    location: str | None
    status: DeviceStatus
    owner_user_id: int | None
    last_seen_at: datetime | None
    last_authenticated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitoringDevicePage(BaseModel):
    items: list[MonitoringDeviceRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    status: DeviceStatus | None
    search: str | None


class MonitoringTelemetryPoint(BaseModel):
    id: int
    device_id: int
    recorded_at: datetime
    metric_name: str
    metric_type: str | None
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    anomaly_flag: bool
    anomaly_score: float | None
    confidence_score: float | None
    intrusion_flag: bool
    intrusion_score: float | None


class MonitoringTelemetryPage(BaseModel):
    items: list[MonitoringTelemetryPoint]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    device_id: int
    metric_name: str | None
    start_time: datetime | None
    end_time: datetime | None


class MonitoringAlertRead(BaseModel):
    id: int
    device_id: int
    device_name: str
    title: str
    description: str | None
    severity: AlertSeverity
    status: AlertStatus
    anomaly_score: float | None
    escalated: bool
    escalation_target: str | None
    triggered_at: datetime
    escalated_at: datetime | None


class MonitoringAlertPage(BaseModel):
    items: list[MonitoringAlertRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    device_id: int | None
    severity: AlertSeverity | None
    status: AlertStatus | None
    start_time: datetime | None
    end_time: datetime | None
    sort_by: str
    sort_order: str


class MonitoringDeviceDetail(BaseModel):
    device: MonitoringDeviceRead
    telemetry_preview: list[MonitoringTelemetryPoint] = Field(default_factory=list)
    active_alerts: list[MonitoringAlertRead] = Field(default_factory=list)
