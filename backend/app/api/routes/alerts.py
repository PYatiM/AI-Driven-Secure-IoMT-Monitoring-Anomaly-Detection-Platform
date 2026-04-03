import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_device
from backend.app.db.models import Alert, AlertSeverity, AlertStatus, Device
from backend.app.db.session import get_db
from backend.app.schemas.alerts import AlertPage
from backend.app.services.audit import set_audit_context

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get(
    "",
    response_model=AlertPage,
    summary="Fetch alerts for the authenticated device",
)
def fetch_alerts(
    request: Request,
    device_id: int | None = Query(default=None, ge=1),
    severity: AlertSeverity | None = Query(default=None),
    status: AlertStatus | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> AlertPage:
    normalized_start = _normalize_datetime(start_time)
    normalized_end = _normalize_datetime(end_time)

    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(
            status_code=400,
            detail="start_time must be earlier than or equal to end_time.",
        )

    effective_device_id = device_id or current_device.id
    if effective_device_id != current_device.id:
        raise HTTPException(
            status_code=403,
            detail="Devices can only access their own alerts.",
        )

    filters = [Alert.device_id == effective_device_id]
    if severity is not None:
        filters.append(Alert.severity == severity)
    if status is not None:
        filters.append(Alert.status == status)
    if normalized_start is not None:
        filters.append(Alert.triggered_at >= normalized_start)
    if normalized_end is not None:
        filters.append(Alert.triggered_at <= normalized_end)

    total_items = db.scalar(select(func.count()).select_from(Alert).where(*filters)) or 0
    alert_items = list(
        db.scalars(
            select(Alert)
            .where(*filters)
            .order_by(Alert.triggered_at.desc(), Alert.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    set_audit_context(
        request,
        action="alert.list",
        resource_type="alert",
        details={
            "device_id": effective_device_id,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
        },
    )
    return AlertPage(
        items=alert_items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        device_id=effective_device_id,
        severity=severity,
        status=status,
        start_time=normalized_start,
        end_time=normalized_end,
    )
