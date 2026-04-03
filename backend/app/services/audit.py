from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.db.models import AuditActorType, AuditLog


@dataclass
class AuditContext:
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    actor_type: AuditActorType | None = None
    actor_user_id: int | None = None
    actor_device_id: int | None = None


def set_audit_context(
    request: Request,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    actor_type: AuditActorType | None = None,
    actor_user_id: int | None = None,
    actor_device_id: int | None = None,
) -> None:
    context = getattr(request.state, "audit_context", None)
    if context is None:
        context = AuditContext()

    if action is not None:
        context.action = action
    if resource_type is not None:
        context.resource_type = resource_type
    if resource_id is not None:
        context.resource_id = str(resource_id)
    if details:
        context.details.update(details)
    if actor_type is not None:
        context.actor_type = actor_type
    if actor_user_id is not None:
        context.actor_user_id = actor_user_id
    if actor_device_id is not None:
        context.actor_device_id = actor_device_id

    request.state.audit_context = context


def write_audit_log(db: Session, request: Request, status_code: int) -> None:
    context = getattr(request.state, "audit_context", None)
    actor_user = getattr(request.state, "current_user", None)
    actor_device = getattr(request.state, "current_device", None)

    actor_type = context.actor_type if context and context.actor_type else None
    actor_user_id = context.actor_user_id if context else None
    actor_device_id = context.actor_device_id if context else None

    if actor_user_id is None and actor_user is not None:
        actor_user_id = actor_user.id
    if actor_device_id is None and actor_device is not None:
        actor_device_id = actor_device.id

    if actor_type is None:
        if actor_user_id is not None:
            actor_type = AuditActorType.USER
        elif actor_device_id is not None:
            actor_type = AuditActorType.DEVICE
        else:
            actor_type = AuditActorType.ANONYMOUS

    audit_log = AuditLog(
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        actor_device_id=actor_device_id,
        action=(context.action if context and context.action else derive_action_name(request))[:100],
        resource_type=(context.resource_type if context and context.resource_type else derive_resource_type(request)),
        resource_id=context.resource_id if context else None,
        http_method=request.method,
        path=str(request.url.path)[:255],
        status_code=status_code,
        success=200 <= status_code < 400,
        ip_address=resolve_client_ip(request),
        user_agent=(request.headers.get("user-agent") or None),
        details=(context.details if context and context.details else None),
    )
    db.add(audit_log)
    db.commit()


def derive_action_name(request: Request) -> str:
    segments = [segment for segment in request.url.path.strip("/").split("/") if segment]
    if segments[:2] == ["api", "v1"]:
        segments = segments[2:]
    action_segments = [request.method.lower(), *(segments or ["root"])]
    return ".".join(action_segments)


def derive_resource_type(request: Request) -> str | None:
    segments = [segment for segment in request.url.path.strip("/").split("/") if segment]
    if segments[:2] == ["api", "v1"]:
        segments = segments[2:]
    return segments[0] if segments else None


def resolve_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None

    client = request.client
    if client is not None:
        return client.host
    return None
