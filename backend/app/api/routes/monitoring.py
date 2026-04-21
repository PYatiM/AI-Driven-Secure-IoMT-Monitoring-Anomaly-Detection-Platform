from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.models import Alert, AlertSeverity, AlertStatus, Device, DeviceData, DeviceStatus, User, UserRole
from backend.app.db.session import get_db, get_session_factory
from backend.app.schemas.monitoring import (
    MonitoringAlertPage,
    MonitoringAlertRead,
    MonitoringDeviceDetail,
    MonitoringDevicePage,
    MonitoringDeviceRead,
    MonitoringTelemetryPage,
    MonitoringTelemetryPoint,
)
from backend.app.security.auth import decode_access_token
from backend.app.security.key_storage import get_jwt_secret_key
from backend.app.security.tokens import InvalidTokenError
from backend.app.services.audit import set_audit_context

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_device_access(device: Device | None, user: User) -> Device:
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    if user.role == UserRole.OPERATOR and device.owner_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this device.",
        )
    return device


def _to_telemetry_point(item: DeviceData) -> MonitoringTelemetryPoint:
    return MonitoringTelemetryPoint(
        id=item.id,
        device_id=item.device_id,
        recorded_at=item.recorded_at,
        metric_name=item.metric_name,
        metric_type=item.metric_type,
        value_numeric=item.value_numeric,
        value_text=item.value_text,
        unit=item.unit,
        anomaly_flag=item.anomaly_flag,
        anomaly_score=item.anomaly_score,
        confidence_score=item.confidence_score,
        intrusion_flag=item.intrusion_flag,
        intrusion_score=item.intrusion_score,
    )


def _to_alert_read(alert: Alert, device_name: str) -> MonitoringAlertRead:
    return MonitoringAlertRead(
        id=alert.id,
        device_id=alert.device_id,
        device_name=device_name,
        title=alert.title,
        description=alert.description,
        severity=alert.severity,
        status=alert.status,
        anomaly_score=alert.anomaly_score,
        escalated=alert.escalated,
        escalation_target=alert.escalation_target,
        triggered_at=alert.triggered_at,
        escalated_at=alert.escalated_at,
    )


@router.get("/devices", response_model=MonitoringDevicePage, summary="List devices for monitoring")
def list_devices(
    request: Request,
    status: DeviceStatus | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringDevicePage:
    filters = []
    if current_user.role == UserRole.OPERATOR:
        filters.append(Device.owner_user_id == current_user.id)
    if status is not None:
        filters.append(Device.status == status)

    sanitized_search = (search or "").strip()
    if sanitized_search:
        pattern = f"%{sanitized_search}%"
        filters.append(
            or_(
                Device.name.ilike(pattern),
                Device.device_identifier.ilike(pattern),
                Device.device_type.ilike(pattern),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(Device).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Device)
            .where(*filters)
            .order_by(Device.name.asc(), Device.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    set_audit_context(
        request,
        action="monitoring.device_list",
        resource_type="device",
        details={
            "page": page,
            "page_size": page_size,
            "status": status.value if status else None,
            "search": sanitized_search or None,
            "total_items": total_items,
        },
    )
    return MonitoringDevicePage(
        items=[MonitoringDeviceRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        status=status,
        search=sanitized_search or None,
    )


@router.get(
    "/devices/{device_id}",
    response_model=MonitoringDeviceDetail,
    summary="Get a device detail view",
)
def get_device_detail(
    request: Request,
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringDeviceDetail:
    device = _ensure_device_access(
        db.scalar(select(Device).where(Device.id == device_id)),
        current_user,
    )

    telemetry_preview = list(
        db.scalars(
            select(DeviceData)
            .where(DeviceData.device_id == device.id)
            .order_by(DeviceData.recorded_at.desc(), DeviceData.id.desc())
            .limit(120)
        )
    )

    active_alert_rows = list(
        db.execute(
            select(Alert, Device.name)
            .join(Device, Device.id == Alert.device_id)
            .where(
                Alert.device_id == device.id,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
            .order_by(Alert.triggered_at.desc(), Alert.id.desc())
            .limit(50)
        )
    )

    set_audit_context(
        request,
        action="monitoring.device_detail",
        resource_type="device",
        resource_id=device.id,
    )
    return MonitoringDeviceDetail(
        device=MonitoringDeviceRead.model_validate(device),
        telemetry_preview=[_to_telemetry_point(item) for item in telemetry_preview],
        active_alerts=[_to_alert_read(alert, device_name) for alert, device_name in active_alert_rows],
    )


@router.get(
    "/devices/{device_id}/telemetry",
    response_model=MonitoringTelemetryPage,
    summary="Get telemetry points for a device",
)
def get_device_telemetry(
    request: Request,
    device_id: int,
    metric_name: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=10, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringTelemetryPage:
    _ensure_device_access(db.scalar(select(Device).where(Device.id == device_id)), current_user)

    normalized_start = _normalize_datetime(start_time)
    normalized_end = _normalize_datetime(end_time)
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(
            status_code=400,
            detail="start_time must be earlier than or equal to end_time.",
        )

    filters = [DeviceData.device_id == device_id]
    cleaned_metric_name = (metric_name or "").strip()
    if cleaned_metric_name:
        filters.append(DeviceData.metric_name == cleaned_metric_name)
    if normalized_start is not None:
        filters.append(DeviceData.recorded_at >= normalized_start)
    if normalized_end is not None:
        filters.append(DeviceData.recorded_at <= normalized_end)

    total_items = db.scalar(select(func.count()).select_from(DeviceData).where(*filters)) or 0
    items = list(
        db.scalars(
            select(DeviceData)
            .where(*filters)
            .order_by(DeviceData.recorded_at.desc(), DeviceData.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    set_audit_context(
        request,
        action="monitoring.telemetry",
        resource_type="device",
        resource_id=device_id,
        details={
            "metric_name": cleaned_metric_name or None,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
        },
    )
    return MonitoringTelemetryPage(
        items=[_to_telemetry_point(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        device_id=device_id,
        metric_name=cleaned_metric_name or None,
        start_time=normalized_start,
        end_time=normalized_end,
    )


@router.get("/alerts", response_model=MonitoringAlertPage, summary="Get alert feed")
def list_alerts(
    request: Request,
    device_id: int | None = Query(default=None, ge=1),
    severity: AlertSeverity | None = Query(default=None),
    status: AlertStatus | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    sort_by: str = Query(default="triggered_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringAlertPage:
    normalized_start = _normalize_datetime(start_time)
    normalized_end = _normalize_datetime(end_time)
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(
            status_code=400,
            detail="start_time must be earlier than or equal to end_time.",
        )

    filters = []
    if current_user.role == UserRole.OPERATOR:
        filters.append(Device.owner_user_id == current_user.id)
    if device_id is not None:
        filters.append(Alert.device_id == device_id)
    if severity is not None:
        filters.append(Alert.severity == severity)
    if status is not None:
        filters.append(Alert.status == status)
    if normalized_start is not None:
        filters.append(Alert.triggered_at >= normalized_start)
    if normalized_end is not None:
        filters.append(Alert.triggered_at <= normalized_end)

    sort_key = sort_by.strip().lower() if sort_by else "triggered_at"
    if sort_key not in {"triggered_at", "severity", "anomaly_score"}:
        sort_key = "triggered_at"

    sort_dir = sort_order.strip().lower() if sort_order else "desc"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    if sort_key == "severity":
        sort_expression = case(
            (Alert.severity == AlertSeverity.CRITICAL, 4),
            (Alert.severity == AlertSeverity.HIGH, 3),
            (Alert.severity == AlertSeverity.MEDIUM, 2),
            else_=1,
        )
    elif sort_key == "anomaly_score":
        sort_expression = Alert.anomaly_score
    else:
        sort_expression = Alert.triggered_at

    ordered_expression = sort_expression.asc() if sort_dir == "asc" else desc(sort_expression)

    total_items = db.scalar(
        select(func.count())
        .select_from(Alert)
        .join(Device, Device.id == Alert.device_id)
        .where(*filters)
    ) or 0

    rows = list(
        db.execute(
            select(Alert, Device.name)
            .join(Device, Device.id == Alert.device_id)
            .where(*filters)
            .order_by(ordered_expression, Alert.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    set_audit_context(
        request,
        action="monitoring.alert_feed",
        resource_type="alert",
        details={
            "device_id": device_id,
            "severity": severity.value if severity else None,
            "status": status.value if status else None,
            "sort_by": sort_key,
            "sort_order": sort_dir,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
        },
    )
    return MonitoringAlertPage(
        items=[_to_alert_read(alert, device_name) for alert, device_name in rows],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        device_id=device_id,
        severity=severity,
        status=status,
        start_time=normalized_start,
        end_time=normalized_end,
        sort_by=sort_key,
        sort_order=sort_dir,
    )


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _build_monitoring_snapshot(db: Session, user: User) -> dict:
    device_filters = []
    if user.role == UserRole.OPERATOR:
        device_filters.append(Device.owner_user_id == user.id)

    visible_device_ids_subquery = select(Device.id).where(*device_filters)

    total_devices = db.scalar(select(func.count()).select_from(Device).where(*device_filters)) or 0
    active_devices = db.scalar(
        select(func.count()).select_from(Device).where(*device_filters, Device.status == DeviceStatus.ACTIVE)
    ) or 0

    alert_filters = [Alert.device_id.in_(visible_device_ids_subquery)]
    open_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(*alert_filters, Alert.status == AlertStatus.OPEN)
    ) or 0
    critical_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(*alert_filters, Alert.severity == AlertSeverity.CRITICAL)
    ) or 0

    recent_window = datetime.now(timezone.utc) - timedelta(minutes=15)
    recent_anomalies = db.scalar(
        select(func.count())
        .select_from(DeviceData)
        .where(
            DeviceData.device_id.in_(visible_device_ids_subquery),
            DeviceData.recorded_at >= recent_window,
            DeviceData.anomaly_flag.is_(True),
        )
    ) or 0

    latest_alert_rows = list(
        db.execute(
            select(Alert, Device.name)
            .join(Device, Device.id == Alert.device_id)
            .where(*alert_filters)
            .order_by(Alert.triggered_at.desc(), Alert.id.desc())
            .limit(5)
        )
    )

    return {
        "summary": {
            "total_devices": total_devices,
            "active_devices": active_devices,
            "open_alerts": open_alerts,
            "critical_alerts": critical_alerts,
            "recent_anomalies": recent_anomalies,
        },
        "latest_alerts": [
            {
                "id": alert.id,
                "device_id": alert.device_id,
                "device_name": device_name,
                "title": alert.title,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "triggered_at": _serialize_datetime(alert.triggered_at),
                "escalated": alert.escalated,
            }
            for alert, device_name in latest_alert_rows
        ],
    }


def _load_user_from_socket_token(db: Session, token: str) -> User | None:
    settings = get_settings()
    try:
        payload = decode_access_token(
            token=token,
            secret_key=get_jwt_secret_key(),
            algorithm=settings.jwt_algorithm,
        )
        user_id = int(payload.get("sub", "0"))
    except (InvalidTokenError, TypeError, ValueError):
        return None

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        return None
    return user


@router.websocket("/ws")
async def monitoring_updates_socket(websocket: WebSocket, token: str = Query(default="")):
    if not token:
        await websocket.close(code=1008, reason="Missing token.")
        return

    initial_session = get_session_factory()()
    try:
        user = _load_user_from_socket_token(initial_session, token)
    finally:
        initial_session.close()

    if user is None:
        await websocket.close(code=1008, reason="Invalid token.")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "type": "connected",
            "timestamp": _serialize_datetime(datetime.now(timezone.utc)),
            "payload": {
                "user_id": user.id,
                "role": user.role.value,
            },
        }
    )

    try:
        while True:
            db = get_session_factory()()
            try:
                snapshot = _build_monitoring_snapshot(db, user)
            finally:
                db.close()

            await websocket.send_json(
                {
                    "type": "snapshot",
                    "timestamp": _serialize_datetime(datetime.now(timezone.utc)),
                    "payload": snapshot,
                }
            )
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
