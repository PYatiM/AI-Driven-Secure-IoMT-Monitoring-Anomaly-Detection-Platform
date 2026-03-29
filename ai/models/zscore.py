from __future__ import annotations

import numpy as np

from ai.models.base import BaseAnomalyDetector


class ZScoreAnomalyDetector(BaseAnomalyDetector):
    def __init__(self, threshold: float = 3.0, min_std: float = 1e-8) -> None:
        self.threshold = threshold
        self.min_std = min_std
        self.feature_names_: list[str] = []
        self.means_ = None
        self.stds_ = None

    def fit(self, features, labels=None) -> "ZScoreAnomalyDetector":
        frame = self._ensure_frame(features)
        self.feature_names_ = list(frame.columns)
        self.means_ = frame.mean(axis=0)
        stds = frame.std(axis=0, ddof=0).replace(0.0, self.min_std).fillna(self.min_std)
        self.stds_ = stds.clip(lower=self.min_std)
        return self

    def decision_function(self, features) -> np.ndarray:
        frame = self._align_frame(features)
        z_scores = ((frame - self.means_) / self.stds_).abs()
        return z_scores.max(axis=1).to_numpy(dtype=float)

    def predict(self, features) -> np.ndarray:
        scores = self.decision_function(features)
        return (scores >= self.threshold).astype(int)
