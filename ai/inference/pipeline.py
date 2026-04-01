from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ai.persistence import ModelArtifact, load_model_artifact


@dataclass
class AnomalyInferenceResult:
    model_name: str
    model_version: str
    is_anomaly: bool
    anomaly_score: float
    confidence_score: float
    predicted_at: str


class RealtimeAnomalyInferencePipeline:
    def __init__(self, artifact: ModelArtifact) -> None:
        self.artifact = artifact

    @classmethod
    def from_path(cls, path: str | Path) -> "RealtimeAnomalyInferencePipeline":
        return cls(load_model_artifact(path))

    def _prepare_features(self, record: dict) -> pd.DataFrame:
        frame = pd.DataFrame([record])
        cleaned = self.artifact.preprocessor.transform(frame)
        return self.artifact.feature_pipeline.transform(cleaned)

    def _calculate_confidence(self, anomaly_score: float) -> float:
        score_min = self.artifact.calibration.get("score_min")
        score_max = self.artifact.calibration.get("score_max")
        if score_min is not None and score_max is not None and score_max > score_min:
            normalized = (anomaly_score - score_min) / (score_max - score_min)
            return float(np.clip(normalized, 0.0, 1.0))

        logistic = 1.0 / (1.0 + np.exp(-anomaly_score))
        return float(np.clip(logistic, 0.0, 1.0))

    def infer(self, record: dict) -> AnomalyInferenceResult:
        features = self._prepare_features(record)
        anomaly_score = float(self.artifact.detector.decision_function(features)[0])
        is_anomaly = bool(self.artifact.detector.predict(features)[0])
        confidence_score = self._calculate_confidence(anomaly_score)
        return AnomalyInferenceResult(
            model_name=self.artifact.model_name,
            model_version=self.artifact.version,
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence_score=confidence_score,
            predicted_at=datetime.now(timezone.utc).isoformat(),
        )

    def infer_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = self.artifact.preprocessor.transform(dataframe)
        features = self.artifact.feature_pipeline.transform(cleaned)
        anomaly_scores = self.artifact.detector.decision_function(features)
        anomaly_flags = self.artifact.detector.predict(features)
        confidence_scores = [
            self._calculate_confidence(float(score)) for score in anomaly_scores
        ]
        return pd.DataFrame(
            {
                "anomaly_flag": anomaly_flags.astype(int),
                "anomaly_score": anomaly_scores.astype(float),
                "confidence_score": confidence_scores,
                "model_name": self.artifact.model_name,
                "model_version": self.artifact.version,
            }
        )
