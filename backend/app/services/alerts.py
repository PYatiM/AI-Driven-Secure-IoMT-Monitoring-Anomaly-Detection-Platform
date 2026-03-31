from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.models import Alert, AlertSeverity, AlertStatus, DeviceData
from backend.app.schemas.alerts import AlertCreate

CRITICAL_STATUS_VALUES = {"critical", "error", "fault", "offline", "tampered"}


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, score))


def _severity_from_score(score: float | None) -> AlertSeverity:
    if score is None:
        return AlertSeverity.MEDIUM
    if score >= 0.9:
        return AlertSeverity.CRITICAL
    if score >= 0.75:
        return AlertSeverity.HIGH
    if score >= 0.5:
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW


def _coerce_severity(value: Any, fallback: AlertSeverity) -> AlertSeverity:
    if isinstance(value, AlertSeverity):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for severity in AlertSeverity:
            if severity.value == normalized:
                return severity
    return fallback


def store_alert(db: Session, payload: AlertCreate) -> Alert:
    alert = Alert(
        device_id=payload.device_id,
        data_id=payload.data_id,
        assigned_user_id=payload.assigned_user_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        status=payload.status,
        anomaly_score=payload.anomaly_score,
        triggered_at=payload.triggered_at or datetime.now(timezone.utc),
    )
    db.add(alert)
    db.flush()
    return alert


def maybe_store_alert_for_telemetry(db: Session, telemetry: DeviceData) -> Alert | None:
    payload = telemetry.payload or {}
    anomaly_score = telemetry.anomaly_score
    if anomaly_score is None:
        anomaly_score = _coerce_score(payload.get("anomaly_score"))

    anomaly_detected = bool(telemetry.anomaly_flag) or bool(payload.get("anomaly_detected"))
    if anomaly_score is not None:
        anomaly_detected = True

    status_text = (telemetry.value_text or "").strip().lower()
    critical_status = (
        (telemetry.metric_type or "").strip().lower() == "status"
        and status_text in CRITICAL_STATUS_VALUES
    )

    if not anomaly_detected and not critical_status:
        return None

    default_severity = (
        AlertSeverity.CRITICAL if critical_status else _severity_from_score(anomaly_score)
    )
    severity = _coerce_severity(payload.get("severity"), default_severity)
    title = payload.get("alert_title") or f"{telemetry.metric_name} anomaly detected"
    description = payload.get("alert_description")
    if description is None:
        if critical_status:
            description = (
                f"Device reported status '{telemetry.value_text}' for metric "
                f"'{telemetry.metric_name}'."
            )
        elif telemetry.anomaly_flag:
            confidence = (
                f" with confidence {telemetry.confidence_score:.2f}"
                if telemetry.confidence_score is not None
                else ""
            )
            model_name = telemetry.model_name or "configured model"
            description = (
                f"The {model_name} flagged metric '{telemetry.metric_name}' as anomalous"
                f"{confidence}."
            )
        elif anomaly_score is not None:
            description = (
                f"Telemetry for metric '{telemetry.metric_name}' exceeded the anomaly "
                f"threshold with score {anomaly_score:.2f}."
            )
        else:
            description = f"Telemetry anomaly detected for metric '{telemetry.metric_name}'."

    alert_payload = AlertCreate(
        device_id=telemetry.device_id,
        data_id=telemetry.id,
        title=title,
        description=description,
        severity=severity,
        status=AlertStatus.OPEN,
        anomaly_score=anomaly_score,
        triggered_at=telemetry.recorded_at,
    )
    return store_alert(db, alert_payload)
