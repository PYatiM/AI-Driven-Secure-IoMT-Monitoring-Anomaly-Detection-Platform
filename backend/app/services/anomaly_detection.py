import logging
from functools import lru_cache
from pathlib import Path

from ai.inference.pipeline import AnomalyInferenceResult, RealtimeAnomalyInferencePipeline
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

    return RealtimeAnomalyInferencePipeline.from_path(model_path)


def infer_telemetry_record(record: dict) -> AnomalyInferenceResult | None:
    pipeline = get_inference_pipeline()
    if pipeline is None:
        return None

    try:
        return pipeline.infer(record)
    except Exception:
        logger.exception("Failed to run anomaly inference for telemetry record.")
        return None
