from __future__ import annotations

from pathlib import Path
import json


class ModelPerformanceMonitor:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record_prediction(self, prediction_result) -> None:
        payload = self._load()
        key = f"{prediction_result.model_name}:{prediction_result.model_version}"
        metrics = payload.get(
            key,
            {
                "model_name": prediction_result.model_name,
                "model_version": prediction_result.model_version,
                "total_predictions": 0,
                "anomalies_detected": 0,
                "average_anomaly_score": 0.0,
                "average_confidence_score": 0.0,
                "last_prediction_at": None,
            },
        )

        total_predictions = metrics["total_predictions"] + 1
        anomalies_detected = metrics["anomalies_detected"] + int(prediction_result.is_anomaly)

        metrics["average_anomaly_score"] = (
            (metrics["average_anomaly_score"] * metrics["total_predictions"])
            + prediction_result.anomaly_score
        ) / total_predictions
        metrics["average_confidence_score"] = (
            (metrics["average_confidence_score"] * metrics["total_predictions"])
            + prediction_result.confidence_score
        ) / total_predictions
        metrics["total_predictions"] = total_predictions
        metrics["anomalies_detected"] = anomalies_detected
        metrics["anomaly_rate"] = anomalies_detected / total_predictions
        metrics["last_prediction_at"] = prediction_result.predicted_at

        payload[key] = metrics
        self._save(payload)
