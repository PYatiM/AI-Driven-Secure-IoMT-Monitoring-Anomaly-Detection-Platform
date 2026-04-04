from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin
from backend.app.db.types import EncryptedJSONType, EncryptedTextType


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AuditActorType(str, Enum):
    ANONYMOUS = "anonymous"
    USER = "user"
    DEVICE = "device"
    SYSTEM = "system"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(EncryptedTextType(), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.ANALYST,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    devices: Mapped[list[Device]] = relationship(back_populates="owner")
    assigned_alerts: Mapped[list[Alert]] = relationship(back_populates="assigned_user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor_user")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_identifier_status", "device_identifier", "status"),
        Index("ix_devices_api_key_prefix", "api_key_prefix", unique=True),
        Index("ix_devices_api_key_hash", "api_key_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_identifier: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(
        SqlEnum(DeviceStatus, name="device_status"),
        nullable=False,
        default=DeviceStatus.ACTIVE,
    )
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    last_authenticated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    owner: Mapped[User | None] = relationship(back_populates="devices")
    data_points: Mapped[list[DeviceData]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list[Alert]] = relationship(back_populates="device")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor_device")


class DeviceData(TimestampMixin, Base):
    __tablename__ = "device_data"
    __table_args__ = (
        Index("ix_device_data_device_recorded_at", "device_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict | None] = mapped_column(EncryptedJSONType(), nullable=True)
    anomaly_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intrusion_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    intrusion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intrusion_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intrusion_reason: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    device: Mapped[Device] = relationship(back_populates="data_points")
    alerts: Mapped[list[Alert]] = relationship(back_populates="source_data")


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_device_status", "device_id", "status"),
        Index("ix_alerts_triggered_at", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_data.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        SqlEnum(AlertSeverity, name="alert_severity"),
        nullable=False,
        default=AlertSeverity.MEDIUM,
    )
    status: Mapped[AlertStatus] = mapped_column(
        SqlEnum(AlertStatus, name="alert_status"),
        nullable=False,
        default=AlertStatus.OPEN,
    )
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped[Device] = relationship(back_populates="alerts")
    source_data: Mapped[DeviceData | None] = relationship(back_populates="alerts")
    assigned_user: Mapped[User | None] = relationship(back_populates="assigned_alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_occurred_at", "occurred_at"),
        Index("ix_audit_logs_action_status", "action", "status_code"),
        Index("ix_audit_logs_actor_user", "actor_user_id", "occurred_at"),
        Index("ix_audit_logs_actor_device", "actor_device_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[AuditActorType] = mapped_column(
        SqlEnum(AuditActorType, name="audit_actor_type"),
        nullable=False,
        default=AuditActorType.ANONYMOUS,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    ip_address: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(EncryptedTextType(), nullable=True)
    details: Mapped[dict | None] = mapped_column(EncryptedJSONType(), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    actor_user: Mapped[User | None] = relationship(back_populates="audit_logs")
    actor_device: Mapped[Device | None] = relationship(back_populates="audit_logs")
