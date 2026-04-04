from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import Request

from backend.app.core.config import get_settings
from backend.app.db.models import AuditActorType, SecurityEvent
from backend.app.db.session import get_session_factory

logger = logging.getLogger(__name__)


class SecurityEventCategory(str, Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    FIREWALL = "firewall"
    INTRUSION_DETECTION = "intrusion_detection"
    KEY_MANAGEMENT = "key_management"
    ALERTING = "alerting"
    SYSTEM = "system"


class SecurityEventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    DETECTED = "detected"
    SIMULATED = "simulated"


@dataclass
class SecurityEventCreate:
    event_type: str
    category: SecurityEventCategory = SecurityEventCategory.SYSTEM
    severity: SecurityEventSeverity = SecurityEventSeverity.MEDIUM
    outcome: SecurityEventOutcome = SecurityEventOutcome.DETECTED
    description: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    actor_type: AuditActorType | str | None = None
    actor_user_id: int | None = None
    actor_device_id: int | None = None
    http_method: str | None = None
    path: str | None = None
    resource_type: str | None = None
    resource_id: str | int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    occurred_at: datetime | None = None


def _resolve_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None

    client = request.client
    if client is not None:
        return client.host
    return None


def _normalize_actor_type(value: AuditActorType | str | None) -> str:
    if isinstance(value, AuditActorType):
        return value.value
    if isinstance(value, str) and value.strip():
        return value.strip().lower()[:20]
    return AuditActorType.ANONYMOUS.value


def _resolve_actor_context(
    request: Request | None,
    actor_type: AuditActorType | str | None,
    actor_user_id: int | None,
    actor_device_id: int | None,
) -> tuple[str, int | None, int | None]:
    if request is not None:
        current_user = getattr(request.state, "current_user", None)
        current_device = getattr(request.state, "current_device", None)
        if actor_user_id is None and current_user is not None:
            actor_user_id = current_user.id
        if actor_device_id is None and current_device is not None:
            actor_device_id = current_device.id

    resolved_actor_type = _normalize_actor_type(actor_type)
    if resolved_actor_type == AuditActorType.ANONYMOUS.value:
        if actor_user_id is not None:
            resolved_actor_type = AuditActorType.USER.value
        elif actor_device_id is not None:
            resolved_actor_type = AuditActorType.DEVICE.value

    return resolved_actor_type, actor_user_id, actor_device_id


def store_security_event(db, payload: SecurityEventCreate) -> SecurityEvent:
    security_event = SecurityEvent(
        event_type=payload.event_type[:100],
        category=payload.category.value,
        severity=payload.severity.value,
        outcome=payload.outcome.value,
        actor_type=_normalize_actor_type(payload.actor_type),
        actor_user_id=payload.actor_user_id,
        actor_device_id=payload.actor_device_id,
        http_method=(payload.http_method[:10] if payload.http_method else None),
        path=(payload.path[:255] if payload.path else None),
        resource_type=(payload.resource_type[:100] if payload.resource_type else None),
        resource_id=(str(payload.resource_id)[:100] if payload.resource_id is not None else None),
        ip_address=payload.ip_address,
        user_agent=payload.user_agent,
        description=payload.description,
        details=(payload.details or None),
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(security_event)
    db.flush()
    return security_event


def log_security_event(
    *,
    request: Request | None = None,
    event_type: str,
    category: SecurityEventCategory = SecurityEventCategory.SYSTEM,
    severity: SecurityEventSeverity = SecurityEventSeverity.MEDIUM,
    outcome: SecurityEventOutcome = SecurityEventOutcome.DETECTED,
    description: str | None = None,
    details: dict[str, Any] | None = None,
    actor_type: AuditActorType | str | None = None,
    actor_user_id: int | None = None,
    actor_device_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    occurred_at: datetime | None = None,
) -> SecurityEvent | None:
    settings = get_settings()
    if not settings.security_event_logging_enabled:
        return None

    resolved_http_method = request.method if request is not None else None
    resolved_path = str(request.url.path) if request is not None else None
    resolved_ip_address = _resolve_client_ip(request) if request is not None else None
    resolved_user_agent = request.headers.get("user-agent") if request is not None else None
    resolved_actor_type, resolved_actor_user_id, resolved_actor_device_id = _resolve_actor_context(
        request,
        actor_type,
        actor_user_id,
        actor_device_id,
    )
    payload = SecurityEventCreate(
        event_type=event_type,
        category=category,
        severity=severity,
        outcome=outcome,
        description=description,
        details=details or {},
        actor_type=resolved_actor_type,
        actor_user_id=resolved_actor_user_id,
        actor_device_id=resolved_actor_device_id,
        http_method=resolved_http_method,
        path=resolved_path,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=resolved_ip_address,
        user_agent=resolved_user_agent,
        occurred_at=occurred_at,
    )

    db = get_session_factory()()
    try:
        event = store_security_event(db, payload)
        db.commit()
        return event
    except Exception:
        db.rollback()
        logger.exception("Failed to persist security event %s", event_type)
        return None
    finally:
        db.close()
