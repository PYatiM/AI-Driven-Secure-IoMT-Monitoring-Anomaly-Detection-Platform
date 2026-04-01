from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from ai.data.features import FeatureExtractionPipeline
from ai.data.preprocessing import DataPreprocessor


@dataclass
class ModelArtifact:
    model_name: str
    version: str
    detector: Any
    preprocessor: DataPreprocessor
    feature_pipeline: FeatureExtractionPipeline
    parent_version: str | None = None
    calibration: dict[str, float] = field(default_factory=dict)
    training_metrics: dict[str, float | int | None] | None = None
    feature_names: list[str] = field(default_factory=list)
    training_data_fingerprint: str | None = None
    trained_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def save_model_artifact(artifact: ModelArtifact, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    return output_path


def load_model_artifact(path: str | Path) -> ModelArtifact:
    artifact = joblib.load(Path(path))
    if not isinstance(artifact, ModelArtifact):
        raise TypeError("Loaded artifact is not a ModelArtifact instance.")
    return artifact
