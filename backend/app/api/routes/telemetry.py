import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_device
from backend.app.db.models import Device, DeviceData
from backend.app.db.session import get_db
from backend.app.schemas.telemetry import (
    TelemetryIngestRequest,
    TelemetryPage,
    TelemetryRead,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post(
    "",
    response_model=TelemetryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest telemetry data from an authenticated device",
)
def ingest_telemetry(
    payload: TelemetryIngestRequest,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> TelemetryRead:
    telemetry = DeviceData(
        device_id=current_device.id,
        recorded_at=payload.recorded_at,
        metric_name=payload.metric_name,
        metric_type=payload.metric_type,
        value_numeric=payload.value_numeric,
        value_text=payload.value_text,
        unit=payload.unit,
        payload=payload.payload,
    )
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    return telemetry


@router.get(
    "",
    response_model=TelemetryPage,
    summary="Fetch telemetry data for the authenticated device",
)
def fetch_telemetry(
    device_id: int | None = Query(default=None, ge=1),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> TelemetryPage:
    normalized_start = _normalize_datetime(start_time)
    normalized_end = _normalize_datetime(end_time)

    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than or equal to end_time.",
        )

    effective_device_id = device_id or current_device.id
    if effective_device_id != current_device.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Devices can only access their own telemetry data.",
        )

    filters = [DeviceData.device_id == effective_device_id]
    if normalized_start is not None:
        filters.append(DeviceData.recorded_at >= normalized_start)
    if normalized_end is not None:
        filters.append(DeviceData.recorded_at <= normalized_end)

    total_items = db.scalar(
        select(func.count()).select_from(DeviceData).where(*filters)
    ) or 0

    telemetry_items = list(
        db.scalars(
            select(DeviceData)
            .where(*filters)
            .order_by(DeviceData.recorded_at.desc(), DeviceData.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    return TelemetryPage(
        items=telemetry_items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        device_id=effective_device_id,
        start_time=normalized_start,
        end_time=normalized_end,
    )
