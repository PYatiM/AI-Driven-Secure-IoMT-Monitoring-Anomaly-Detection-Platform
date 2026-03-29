from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from ai.models.base import BaseAnomalyDetector


class IsolationForestDetector(BaseAnomalyDetector):
    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
        )
        self.feature_names_: list[str] = []

    def fit(self, features, labels=None) -> "IsolationForestDetector":
        frame = self._ensure_frame(features)
        self.feature_names_ = list(frame.columns)
        self.model.fit(frame.to_numpy(dtype=float))
        return self

    def decision_function(self, features) -> np.ndarray:
        frame = self._align_frame(features)
        return -self.model.score_samples(frame.to_numpy(dtype=float))

    def predict(self, features) -> np.ndarray:
        frame = self._align_frame(features)
        raw_predictions = self.model.predict(frame.to_numpy(dtype=float))
        return (raw_predictions == -1).astype(int)
