import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_device
from backend.app.core.config import get_settings
from backend.app.db.models import AuditActorType, Device, DeviceData
from backend.app.db.session import get_db
from backend.app.schemas.telemetry import (
    TelemetryBatchIngestRequest,
    TelemetryBatchIngestResponse,
    TelemetryIngestRequest,
    TelemetryPage,
    TelemetryRead,
    TelemetryStreamIngestResponse,
)
from backend.app.services.alerts import maybe_store_alert_for_telemetry
from backend.app.services.anomaly_detection import infer_telemetry_record
from backend.app.services.audit import set_audit_context
from backend.app.services.intrusion_detection import detect_intrusion
from backend.app.services.security_events import (
    SecurityEventCategory,
    SecurityEventOutcome,
    SecurityEventSeverity,
    log_security_event,
)
from backend.app.services.telemetry_stream import (
    DeviceStreamContext,
    QueuedTelemetryRecord,
    get_telemetry_stream_service,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _intrusion_severity(score: float | None) -> SecurityEventSeverity:
    if score is None:
        return SecurityEventSeverity.HIGH
    if score >= 0.9:
        return SecurityEventSeverity.CRITICAL
    if score >= 0.75:
        return SecurityEventSeverity.HIGH
    return SecurityEventSeverity.MEDIUM


def _build_telemetry_entity(current_device: Device, payload: TelemetryIngestRequest) -> DeviceData:
    telemetry_record = {
        "device_id": current_device.id,
        "device_identifier": current_device.device_identifier,
        "device_type": current_device.device_type,
        "location": current_device.location,
        "recorded_at": payload.recorded_at,
        "metric_name": payload.metric_name,
        "metric_type": payload.metric_type,
        "value_numeric": payload.value_numeric,
        "value_text": payload.value_text,
        "unit": payload.unit,
        "payload": payload.payload or {},
    }
    inference_result = infer_telemetry_record(telemetry_record)
    intrusion_result = detect_intrusion(telemetry_record, inference_result)

    return DeviceData(
        device_id=current_device.id,
        recorded_at=payload.recorded_at,
        metric_name=payload.metric_name,
        metric_type=payload.metric_type,
        value_numeric=payload.value_numeric,
        value_text=payload.value_text,
        unit=payload.unit,
        payload=payload.payload,
        anomaly_flag=inference_result.is_anomaly if inference_result else False,
        anomaly_score=inference_result.anomaly_score if inference_result else None,
        confidence_score=inference_result.confidence_score if inference_result else None,
        model_name=inference_result.model_name if inference_result else None,
        intrusion_flag=intrusion_result.intrusion_flag,
        intrusion_score=intrusion_result.intrusion_score,
        intrusion_type=intrusion_result.intrusion_type if intrusion_result.intrusion_flag else None,
        intrusion_reason=intrusion_result.intrusion_reason if intrusion_result.intrusion_flag else None,
    )


def _persist_telemetry_record(
    db: Session,
    current_device: Device,
    payload: TelemetryIngestRequest,
) -> tuple[DeviceData, object | None]:
    telemetry = _build_telemetry_entity(current_device, payload)
    db.add(telemetry)
    db.flush()
    alert = maybe_store_alert_for_telemetry(db, telemetry)
    return telemetry, alert


@router.post(
    "",
    response_model=TelemetryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest telemetry data from an authenticated device",
)
def ingest_telemetry(
    request: Request,
    payload: TelemetryIngestRequest,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> TelemetryRead:
    telemetry, alert = _persist_telemetry_record(db, current_device, payload)
    db.commit()
    db.refresh(telemetry)
    if alert is not None:
        db.refresh(alert)

    if alert is not None and getattr(alert, "escalated", False):
        log_security_event(
            request=request,
            event_type="alert.escalated",
            category=SecurityEventCategory.ALERTING,
            severity=SecurityEventSeverity.CRITICAL,
            outcome=SecurityEventOutcome.DETECTED,
            description=(
                alert.escalation_reason
                or f"Alert {alert.id} was escalated for critical anomaly handling."
            ),
            details={
                "alert_id": alert.id,
                "device_id": telemetry.device_id,
                "data_id": telemetry.id,
                "metric_name": telemetry.metric_name,
                "severity": alert.severity.value,
                "escalation_target": alert.escalation_target,
                "anomaly_score": alert.anomaly_score,
                "intrusion_score": telemetry.intrusion_score,
                "intrusion_type": telemetry.intrusion_type,
            },
            actor_type=AuditActorType.DEVICE,
            actor_device_id=current_device.id,
            resource_type="alert",
            resource_id=alert.id,
        )

    if telemetry.intrusion_flag:
        log_security_event(
            request=request,
            event_type="intrusion.detected",
            category=SecurityEventCategory.INTRUSION_DETECTION,
            severity=_intrusion_severity(telemetry.intrusion_score),
            outcome=SecurityEventOutcome.DETECTED,
            description=(
                telemetry.intrusion_reason
                or f"Potential intrusion detected for metric '{telemetry.metric_name}'."
            ),
            details={
                "metric_name": telemetry.metric_name,
                "intrusion_type": telemetry.intrusion_type,
                "intrusion_score": telemetry.intrusion_score,
                "anomaly_flag": telemetry.anomaly_flag,
                "device_identifier": current_device.device_identifier,
            },
            actor_type=AuditActorType.DEVICE,
            actor_device_id=current_device.id,
            resource_type="telemetry",
            resource_id=telemetry.id,
        )

    set_audit_context(
        request,
        action="telemetry.ingest",
        resource_type="telemetry",
        resource_id=telemetry.id,
        details={
            "metric_name": telemetry.metric_name,
            "anomaly_flag": telemetry.anomaly_flag,
            "intrusion_flag": telemetry.intrusion_flag,
            "intrusion_type": telemetry.intrusion_type,
            "alert_id": alert.id if alert is not None else None,
            "alert_escalated": alert.escalated if alert is not None else False,
        },
    )
    return telemetry


@router.post(
    "/batch",
    response_model=TelemetryBatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest telemetry data in batches for higher throughput",
)
def ingest_telemetry_batch(
    request: Request,
    payload: TelemetryBatchIngestRequest,
    current_device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> TelemetryBatchIngestResponse:
    settings = get_settings()
    if len(payload.items) > settings.telemetry_batch_max_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Batch size exceeds TELEMETRY_BATCH_MAX_RECORDS "
                f"({settings.telemetry_batch_max_records})."
            ),
        )

    anomaly_items = 0
    intrusion_items = 0
    alerts_created = 0

    for item in payload.items:
        telemetry, alert = _persist_telemetry_record(db, current_device, item)
        if telemetry.anomaly_flag:
            anomaly_items += 1
        if telemetry.intrusion_flag:
            intrusion_items += 1
        if alert is not None:
            alerts_created += 1

    db.commit()

    set_audit_context(
        request,
        action="telemetry.batch_ingest",
        resource_type="telemetry",
        details={
            "items": len(payload.items),
            "anomaly_items": anomaly_items,
            "intrusion_items": intrusion_items,
            "alerts_created": alerts_created,
        },
    )
    return TelemetryBatchIngestResponse(
        ingested_items=len(payload.items),
        anomaly_items=anomaly_items,
        intrusion_items=intrusion_items,
        alerts_created=alerts_created,
    )


@router.post(
    "/stream",
    response_model=TelemetryStreamIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue telemetry records for streaming ingestion",
)
async def stream_telemetry_ingest(
    request: Request,
    payload: TelemetryBatchIngestRequest,
    current_device: Device = Depends(get_current_device),
) -> TelemetryStreamIngestResponse:
    settings = get_settings()
    if not settings.telemetry_queue_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry queue ingestion is disabled.",
        )

    if len(payload.items) > settings.telemetry_batch_max_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Batch size exceeds TELEMETRY_BATCH_MAX_RECORDS "
                f"({settings.telemetry_batch_max_records})."
            ),
        )

    stream_service = get_telemetry_stream_service()
    if not stream_service.is_running:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry queue worker is not running.",
        )

    device_context = DeviceStreamContext(
        id=current_device.id,
        device_identifier=current_device.device_identifier,
        device_type=current_device.device_type,
        location=current_device.location,
    )
    records = [
        QueuedTelemetryRecord(device=device_context, payload=item)
        for item in payload.items
    ]

    queued_items, queue_depth = await stream_service.enqueue(records)
    if queued_items == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry queue is full; try again shortly.",
        )

    set_audit_context(
        request,
        action="telemetry.stream_enqueue",
        resource_type="telemetry",
        details={
            "queued_items": queued_items,
            "queue_depth": queue_depth,
        },
    )
    return TelemetryStreamIngestResponse(
        queued_items=queued_items,
        queue_depth=queue_depth,
    )


@router.get(
    "",
    response_model=TelemetryPage,
    summary="Fetch telemetry data for the authenticated device",
)
def fetch_telemetry(
    request: Request,
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
    set_audit_context(
        request,
        action="telemetry.list",
        resource_type="telemetry",
        details={
            "device_id": effective_device_id,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
        },
    )
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

