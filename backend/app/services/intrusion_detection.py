from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ai.inference.pipeline import AnomalyInferenceResult
from backend.app.core.config import get_settings

SECURITY_CATEGORY_RULES: dict[str, tuple[float, set[str]]] = {
    "unauthorized_access": (
        0.14,
        {
            "access violation",
            "authentication failure",
            "brute force",
            "credential",
            "denied",
            "failed auth",
            "forbidden",
            "invalid api key",
            "invalid token",
            "login failure",
            "privilege escalation",
            "unauthorized",
        },
    ),
    "device_tampering": (
        0.15,
        {
            "calibration changed",
            "configuration drift",
            "device clone",
            "firmware change",
            "integrity violation",
            "sensor override",
            "spoofed",
            "tamper",
            "tampered",
            "unauthorized firmware",
        },
    ),
    "reconnaissance": (
        0.12,
        {
            "discovery",
            "enumeration",
            "network scan",
            "port scan",
            "probe",
            "recon",
            "scan",
            "service mapping",
            "syn sweep",
        },
    ),
    "denial_of_service": (
        0.14,
        {
            "connection flood",
            "ddos",
            "denial of service",
            "dos",
            "flood",
            "packet storm",
            "queue saturation",
            "rate limit",
            "resource exhaustion",
            "traffic burst",
        },
    ),
    "data_exfiltration": (
        0.15,
        {
            "bulk export",
            "data leak",
            "egress spike",
            "exfiltration",
            "large transfer",
            "payload dump",
            "suspicious upload",
            "unauthorized transfer",
        },
    ),
    "malware_activity": (
        0.16,
        {
            "beacon",
            "botnet",
            "command and control",
            "malware",
            "ransomware",
            "remote shell",
            "trojan",
            "worm",
        },
    ),
}

STRONG_SECURITY_PHRASES = {
    "brute force",
    "command and control",
    "credential",
    "data leak",
    "ddos",
    "denial of service",
    "exfiltration",
    "invalid token",
    "malware",
    "port scan",
    "privilege escalation",
    "ransomware",
    "remote shell",
    "spoofed",
    "tampered",
    "unauthorized",
    "unauthorized firmware",
}

EXPLICIT_INTRUSION_SIGNAL_KEYS = {
    "attack_detected": "anomalous_activity",
    "compromise_detected": "anomalous_activity",
    "intrusion_detected": "anomalous_activity",
    "security_incident": "anomalous_activity",
    "tamper_detected": "device_tampering",
    "unauthorized_access": "unauthorized_access",
}

STATUS_INTRUSION_TYPES = {
    "blocked": "denial_of_service",
    "compromised": "malware_activity",
    "spoofed": "device_tampering",
    "tampered": "device_tampering",
    "unauthorized": "unauthorized_access",
}


@dataclass
class IntrusionDetectionResult:
    intrusion_flag: bool
    intrusion_score: float
    intrusion_type: str | None
    intrusion_reason: str | None
    matched_indicators: list[str]


def _clip_score(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _normalize_probability(value: Any) -> float:
    if value is None:
        return 0.0

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if 0.0 <= numeric_value <= 1.0:
        return numeric_value

    return 1.0 / (1.0 + math.exp(-numeric_value))


def _normalize_text(value: str) -> str:
    tokens: list[str] = []
    current: list[str] = []
    for character in value.lower():
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return f" {' '.join(tokens)} " if tokens else " "


def _normalize_intrusion_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = "_".join(_normalize_text(value).split())
    return normalized[:100] if normalized else None


def _iter_payload_entries(value: Any, prefix: str = "payload"):
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            next_prefix = f"{prefix}.{key_text}" if prefix else key_text
            yield next_prefix, key_text
            yield from _iter_payload_entries(item, next_prefix)
        return

    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            yield from _iter_payload_entries(item, f"{prefix}[{index}]")
        return

    yield prefix, value


def detect_intrusion(
    record: dict[str, Any],
    inference_result: AnomalyInferenceResult | None,
) -> IntrusionDetectionResult:
    settings = get_settings()
    if not settings.intrusion_detection_enabled:
        return IntrusionDetectionResult(
            intrusion_flag=False,
            intrusion_score=0.0,
            intrusion_type=None,
            intrusion_reason=None,
            matched_indicators=[],
        )

    payload = record.get("payload") or {}
    combined_parts = [
        str(record.get("metric_name") or ""),
        str(record.get("metric_type") or ""),
        str(record.get("value_text") or ""),
        str(record.get("unit") or ""),
    ]
    numeric_entries: list[tuple[str, float]] = []
    indicator_reasons: list[str] = []
    category_scores = {category: 0.0 for category in SECURITY_CATEGORY_RULES}
    payload_intrusion_type: str | None = None
    explicit_intrusion = False

    for path, value in _iter_payload_entries(payload):
        combined_parts.append(path)
        if isinstance(value, str):
            combined_parts.append(value)
            if path.lower().endswith("intrusion_type"):
                payload_intrusion_type = _normalize_intrusion_type(value)
        elif isinstance(value, bool):
            combined_parts.append(f"{path} {'true' if value else 'false'}")
            key_name = path.rsplit(".", 1)[-1].lower()
            category = EXPLICIT_INTRUSION_SIGNAL_KEYS.get(key_name)
            if category and value:
                explicit_intrusion = True
                if category in category_scores:
                    category_scores[category] = max(category_scores[category], 0.45)
                elif payload_intrusion_type is None:
                    payload_intrusion_type = category
                indicator_reasons.append(f"{path} explicitly reported a security incident.")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_entries.append((path, float(value)))
            combined_parts.append(f"{path} {value}")
        elif value is not None:
            combined_parts.append(str(value))

    normalized_text = _normalize_text(" ".join(combined_parts))

    for category, (base_weight, phrases) in SECURITY_CATEGORY_RULES.items():
        for phrase in sorted(phrases):
            normalized_phrase = _normalize_text(phrase)
            if normalized_phrase in normalized_text:
                weight = base_weight + (0.08 if phrase in STRONG_SECURITY_PHRASES else 0.0)
                category_scores[category] = min(category_scores[category] + weight, 0.5)
                indicator_reasons.append(f"Matched security indicator '{phrase}' in telemetry context.")

    metric_type = (record.get("metric_type") or "").strip().lower()
    status_value = (record.get("value_text") or "").strip().lower()
    if metric_type == "status":
        status_intrusion_type = STATUS_INTRUSION_TYPES.get(status_value)
        if status_intrusion_type is not None:
            category_scores[status_intrusion_type] = min(
                category_scores[status_intrusion_type] + 0.3,
                0.5,
            )
            indicator_reasons.append(
                f"Device status reported '{status_value}', which maps to a security condition."
            )

    for path, value in numeric_entries:
        path_lower = path.lower()
        if any(
            hint in path_lower
            for hint in (
                "auth_fail",
                "failed_attempt",
                "failed_login",
                "invalid_token",
                "login_retry",
                "rejected_request",
            )
        ) and value >= 5:
            category_scores["unauthorized_access"] = min(
                category_scores["unauthorized_access"] + 0.22,
                0.5,
            )
            indicator_reasons.append(
                f"{path}={value:g} indicates repeated authentication or access failures."
            )

        if any(
            hint in path_lower
            for hint in (
                "probe_count",
                "scan_count",
                "scan_rate",
                "port_scan",
                "syn_count",
            )
        ) and value >= 3:
            category_scores["reconnaissance"] = min(
                category_scores["reconnaissance"] + 0.24,
                0.5,
            )
            indicator_reasons.append(
                f"{path}={value:g} indicates scanning or reconnaissance behaviour."
            )

        if any(
            hint in path_lower
            for hint in (
                "connection_count",
                "connection_rate",
                "packet_rate",
                "queue_depth",
                "request_rate",
                "session_count",
            )
        ) and value >= 100:
            category_scores["denial_of_service"] = min(
                category_scores["denial_of_service"] + 0.2,
                0.5,
            )
            indicator_reasons.append(
                f"{path}={value:g} suggests burst traffic or resource exhaustion."
            )

        if any(
            hint in path_lower
            for hint in (
                "bytes_out",
                "data_volume",
                "egress",
                "export_size",
                "transfer_size",
                "upload_size",
            )
        ) and value >= 1000000:
            category_scores["data_exfiltration"] = min(
                category_scores["data_exfiltration"] + 0.24,
                0.5,
            )
            indicator_reasons.append(
                f"{path}={value:g} suggests unusually large outbound transfer volume."
            )

    anomaly_score = _normalize_probability(
        inference_result.anomaly_score if inference_result else payload.get("anomaly_score")
    )
    confidence_score = _clip_score(
        inference_result.confidence_score if inference_result else payload.get("confidence_score")
    )

    score = 0.0
    if inference_result and inference_result.is_anomaly:
        score += 0.3
        indicator_reasons.append("The configured AI model marked this telemetry as anomalous.")

    score += anomaly_score * 0.2
    score += confidence_score * 0.1

    if anomaly_score >= settings.intrusion_anomaly_score_threshold:
        score += 0.1
    if confidence_score >= settings.intrusion_confidence_threshold:
        score += 0.08

    indicator_score = min(sum(category_scores.values()), 0.55)
    score = _clip_score(score + indicator_score)

    top_category = None
    if any(category_scores.values()):
        top_category = max(category_scores.items(), key=lambda item: item[1])[0]

    inferred_intrusion_type = payload_intrusion_type or top_category
    high_anomaly_signal = bool(
        inference_result
        and inference_result.is_anomaly
        and anomaly_score >= settings.intrusion_anomaly_score_threshold
        and confidence_score >= settings.intrusion_confidence_threshold
    )
    intrusion_flag = explicit_intrusion or (
        score >= settings.intrusion_score_threshold
        and (indicator_score > 0.0 or high_anomaly_signal)
    )

    if intrusion_flag and inferred_intrusion_type is None:
        inferred_intrusion_type = "anomalous_activity"

    summary_reasons = list(dict.fromkeys(indicator_reasons))
    intrusion_reason = None
    if intrusion_flag and summary_reasons:
        intrusion_reason = " ".join(summary_reasons[:3])
    elif summary_reasons:
        intrusion_reason = " ".join(summary_reasons[:2])

    return IntrusionDetectionResult(
        intrusion_flag=intrusion_flag,
        intrusion_score=score,
        intrusion_type=inferred_intrusion_type,
        intrusion_reason=intrusion_reason,
        matched_indicators=summary_reasons,
    )
