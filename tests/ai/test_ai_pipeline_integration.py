from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ai.inference.pipeline import RealtimeAnomalyInferencePipeline
from ai.training.train_models import train_models
from backend.app.core.config import get_settings
from backend.app.services.anomaly_detection import (
    get_inference_pipeline,
    get_performance_monitor,
    get_prediction_logger,
    infer_telemetry_record,
)


def _build_training_rows() -> list[dict]:
    rows: list[dict] = []
    for index in range(40):
        rows.append(
            {
                "recorded_at": f"2026-01-01T00:{index:02d}:00Z",
                "metric_name": "heart_rate",
                "metric_type": "vital_sign",
                "value_numeric": 70 + (index % 5),
                "unit": "bpm",
                "payload": {"source": "integration-test", "window": index // 10},
                "label": 0,
            }
        )

    for index in range(6):
        rows.append(
            {
                "recorded_at": f"2026-01-01T01:{index:02d}:00Z",
                "metric_name": "heart_rate",
                "metric_type": "vital_sign",
                "value_numeric": 155 + index * 3,
                "unit": "bpm",
                "payload": {"source": "integration-test", "anomaly_detected": True},
                "label": 1,
            }
        )
    return rows


def _write_training_dataset(path: Path) -> None:
    rows = _build_training_rows()
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _clear_anomaly_service_caches() -> None:
    get_settings.cache_clear()
    get_inference_pipeline.cache_clear()
    get_prediction_logger.cache_clear()
    get_performance_monitor.cache_clear()


def test_training_and_inference_pipeline_end_to_end(tmp_path: Path) -> None:
    data_path = tmp_path / "telemetry_training.json"
    artifacts_dir = tmp_path / "artifacts"
    _write_training_dataset(data_path)

    results = train_models(
        data_path=data_path,
        output_dir=artifacts_dir,
        file_format="json",
        target_column="label",
        models=["zscore"],
        test_size=0.25,
        random_state=7,
        stratify=True,
    )

    zscore_result = results["zscore"]
    artifact_path = Path(zscore_result["artifact_path"])
    assert artifact_path.exists()
    assert zscore_result["metrics"] is not None

    pipeline = RealtimeAnomalyInferencePipeline.from_path(artifact_path)
    point_result = pipeline.infer(
        {
            "recorded_at": "2026-01-01T02:00:00Z",
            "metric_name": "heart_rate",
            "metric_type": "vital_sign",
            "value_numeric": 182.0,
            "unit": "bpm",
            "payload": {"source": "integration-test"},
        }
    )

    assert point_result.model_name == "zscore"
    assert point_result.model_version == zscore_result["version"]
    assert isinstance(point_result.is_anomaly, bool)
    assert isinstance(point_result.anomaly_score, float)
    assert 0.0 <= point_result.confidence_score <= 1.0

    frame_result = pipeline.infer_dataframe(
        pd.DataFrame(
            [
                {
                    "recorded_at": "2026-01-01T02:01:00Z",
                    "metric_name": "heart_rate",
                    "metric_type": "vital_sign",
                    "value_numeric": 75.0,
                    "unit": "bpm",
                    "payload": {"source": "integration-test"},
                },
                {
                    "recorded_at": "2026-01-01T02:02:00Z",
                    "metric_name": "heart_rate",
                    "metric_type": "vital_sign",
                    "value_numeric": 176.0,
                    "unit": "bpm",
                    "payload": {"source": "integration-test"},
                },
            ]
        )
    )
    assert set(frame_result.columns) == {
        "anomaly_flag",
        "anomaly_score",
        "confidence_score",
        "model_name",
        "model_version",
    }
    assert len(frame_result) == 2


def test_backend_anomaly_service_logs_predictions_and_performance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "telemetry_training.json"
    artifacts_dir = tmp_path / "artifacts"
    logs_path = tmp_path / "logs" / "predictions.jsonl"
    metrics_path = tmp_path / "monitoring" / "performance.json"
    _write_training_dataset(data_path)

    results = train_models(
        data_path=data_path,
        output_dir=artifacts_dir,
        file_format="json",
        target_column="label",
        models=["zscore"],
        test_size=0.2,
        random_state=21,
        stratify=True,
    )
    artifact_path = results["zscore"]["artifact_path"]

    monkeypatch.setenv("AI_MODEL_ENABLED", "true")
    monkeypatch.setenv("AI_MODEL_PATH", str(artifact_path))
    monkeypatch.setenv("AI_PREDICTION_LOG_PATH", str(logs_path))
    monkeypatch.setenv("AI_MONITORING_METRICS_PATH", str(metrics_path))
    _clear_anomaly_service_caches()

    result = infer_telemetry_record(
        {
            "device_id": 101,
            "device_identifier": "DEV-LOAD-101",
            "device_type": "patient_monitor",
            "location": "ward-a",
            "recorded_at": "2026-01-01T03:00:00Z",
            "metric_name": "heart_rate",
            "metric_type": "vital_sign",
            "value_numeric": 180.0,
            "unit": "bpm",
            "payload": {"source": "backend-integration-test"},
        }
    )

    assert result is not None
    assert logs_path.exists()
    assert metrics_path.exists()

    log_lines = [line for line in logs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(log_lines) == 1
    log_payload = json.loads(log_lines[0])
    assert log_payload["prediction"]["model_name"] == "zscore"

    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert len(metrics_payload) == 1
    key = next(iter(metrics_payload.keys()))
    assert key.startswith("zscore:")
    assert metrics_payload[key]["total_predictions"] == 1

    monkeypatch.setenv("AI_MODEL_ENABLED", "false")
    _clear_anomaly_service_caches()
