from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
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

    if 0.0 <= score <= 1.0:
        return score

    if score < 0.0:
        return 0.0
    return 1.0


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


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


def _resolve_escalation_target() -> str | None:
    target = get_settings().alert_escalation_target.strip()
    return target or None


def _should_escalate_alert(severity: AlertSeverity) -> bool:
    settings = get_settings()
    return settings.alert_escalation_enabled and severity == AlertSeverity.CRITICAL


def _build_escalation_reason(
    telemetry: DeviceData,
    *,
    intrusion_detected: bool,
    critical_status: bool,
    anomaly_score: float | None,
    intrusion_score: float | None,
) -> str:
    if intrusion_detected:
        readable_type = (telemetry.intrusion_type or "anomalous_activity").replace("_", " ")
        if intrusion_score is not None:
            return (
                f"Critical intrusion anomaly '{readable_type}' detected for metric "
                f"'{telemetry.metric_name}' with intrusion score {intrusion_score:.2f}."
            )
        return (
            f"Critical intrusion anomaly '{readable_type}' detected for metric "
            f"'{telemetry.metric_name}'."
        )

    if critical_status:
        return (
            f"Device status metric '{telemetry.metric_name}' reported critical state "
            f"'{telemetry.value_text}'."
        )

    if telemetry.anomaly_flag:
        model_name = telemetry.model_name or "configured model"
        confidence = (
            f" and confidence {telemetry.confidence_score:.2f}"
            if telemetry.confidence_score is not None
            else ""
        )
        score_text = (
            f" with anomaly score {anomaly_score:.2f}"
            if anomaly_score is not None
            else ""
        )
        return (
            f"{model_name} classified metric '{telemetry.metric_name}' as a critical anomaly"
            f"{score_text}{confidence}."
        )

    if anomaly_score is not None:
        return (
            f"Metric '{telemetry.metric_name}' reached critical anomaly severity with "
            f"score {anomaly_score:.2f}."
        )

    return f"Critical anomaly detected for metric '{telemetry.metric_name}'."


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
        escalated=payload.escalated,
        escalation_level=payload.escalation_level,
        escalation_target=payload.escalation_target,
        escalation_reason=payload.escalation_reason,
        triggered_at=payload.triggered_at or datetime.now(timezone.utc),
        escalated_at=payload.escalated_at,
    )
    db.add(alert)
    db.flush()
    return alert


def maybe_store_alert_for_telemetry(db: Session, telemetry: DeviceData) -> Alert | None:
    payload = telemetry.payload or {}
    anomaly_score = _coerce_score(telemetry.anomaly_score)
    if anomaly_score is None:
        anomaly_score = _coerce_score(payload.get("anomaly_score"))

    intrusion_score = _coerce_score(telemetry.intrusion_score)
    if intrusion_score is None:
        intrusion_score = _coerce_score(payload.get("intrusion_score"))

    intrusion_detected = bool(telemetry.intrusion_flag) or _coerce_bool(
        payload.get("intrusion_detected")
    )
    anomaly_detected = bool(telemetry.anomaly_flag) or _coerce_bool(
        payload.get("anomaly_detected")
    )

    status_text = (telemetry.value_text or "").strip().lower()
    critical_status = (
        (telemetry.metric_type or "").strip().lower() == "status"
        and status_text in CRITICAL_STATUS_VALUES
    )

    if not intrusion_detected and not anomaly_detected and not critical_status:
        return None

    score_for_storage = anomaly_score
    if intrusion_detected:
        score_for_storage = intrusion_score if intrusion_score is not None else anomaly_score
        default_severity = (
            AlertSeverity.CRITICAL
            if intrusion_score is None or intrusion_score >= 0.85
            else AlertSeverity.HIGH
        )
    else:
        default_severity = (
            AlertSeverity.CRITICAL if critical_status else _severity_from_score(anomaly_score)
        )

    severity = _coerce_severity(payload.get("severity"), default_severity)

    if intrusion_detected:
        intrusion_type = (
            telemetry.intrusion_type or payload.get("intrusion_type") or "anomalous_activity"
        )
        readable_type = intrusion_type.replace("_", " ")
        title = payload.get("alert_title") or f"Potential intrusion detected: {telemetry.metric_name}"
        description = payload.get("alert_description") or telemetry.intrusion_reason
        if description is None:
            if intrusion_score is not None:
                description = (
                    f"Telemetry for metric '{telemetry.metric_name}' was classified as {readable_type} "
                    f"with intrusion score {intrusion_score:.2f}."
                )
            else:
                description = (
                    f"Telemetry for metric '{telemetry.metric_name}' was classified as {readable_type}."
                )
    else:
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

    should_escalate = _should_escalate_alert(severity)
    escalation_reason = None
    escalation_target = None
    escalated_at = None
    if should_escalate:
        escalation_reason = _build_escalation_reason(
            telemetry,
            intrusion_detected=intrusion_detected,
            critical_status=critical_status,
            anomaly_score=anomaly_score,
            intrusion_score=intrusion_score,
        )
        escalation_target = _resolve_escalation_target()
        escalated_at = datetime.now(timezone.utc)

    alert_payload = AlertCreate(
        device_id=telemetry.device_id,
        data_id=telemetry.id,
        title=title,
        description=description,
        severity=severity,
        status=AlertStatus.OPEN,
        anomaly_score=score_for_storage,
        escalated=should_escalate,
        escalation_level=severity.value if should_escalate else None,
        escalation_target=escalation_target,
        escalation_reason=escalation_reason,
        triggered_at=telemetry.recorded_at,
        escalated_at=escalated_at,
    )
    return store_alert(db, alert_payload)
