import logging
from functools import lru_cache
from pathlib import Path

from ai.inference.pipeline import AnomalyInferenceResult, RealtimeAnomalyInferencePipeline
from ai.monitoring.performance import ModelPerformanceMonitor
from ai.monitoring.prediction_logging import PredictionLogger
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_inference_pipeline() -> RealtimeAnomalyInferencePipeline | None:
    settings = get_settings()
    if not settings.ai_model_enabled or not settings.ai_model_path:
        return None

    model_path = Path(settings.ai_model_path)
    if not model_path.exists():
        logger.warning("Configured AI model path does not exist: %s", model_path)
        return None

    try:
        return RealtimeAnomalyInferencePipeline.from_path(model_path)
    except Exception:
        logger.exception("Failed to load anomaly inference pipeline from %s", model_path)
        return None


@lru_cache
def get_prediction_logger() -> PredictionLogger | None:
    settings = get_settings()
    if not settings.ai_model_enabled:
        return None

    return PredictionLogger(settings.ai_prediction_log_path)


@lru_cache
def get_performance_monitor() -> ModelPerformanceMonitor | None:
    settings = get_settings()
    if not settings.ai_model_enabled:
        return None

    return ModelPerformanceMonitor(settings.ai_monitoring_metrics_path)


def infer_telemetry_record(record: dict) -> AnomalyInferenceResult | None:
    pipeline = get_inference_pipeline()
    if pipeline is None:
        return None

    try:
        result = pipeline.infer(record)
    except Exception:
        logger.exception("Failed to run anomaly inference for telemetry record.")
        return None

    prediction_logger = get_prediction_logger()
    if prediction_logger is not None:
        try:
            prediction_logger.log(record, result)
        except Exception:
            logger.exception("Failed to log model prediction.")

    performance_monitor = get_performance_monitor()
    if performance_monitor is not None:
        try:
            performance_monitor.record_prediction(result)
        except Exception:
            logger.exception("Failed to update model performance metrics.")

    return result
