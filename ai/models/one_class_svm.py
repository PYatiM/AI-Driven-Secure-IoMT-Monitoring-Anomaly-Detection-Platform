from __future__ import annotations

import numpy as np
from sklearn.svm import OneClassSVM

from ai.models.base import BaseAnomalyDetector


class OneClassSVMDetector(BaseAnomalyDetector):
    def __init__(
        self,
        kernel: str = "rbf",
        nu: float = 0.05,
        gamma: str | float = "scale",
    ) -> None:
        self.model = OneClassSVM(kernel=kernel, nu=nu, gamma=gamma)
        self.feature_names_: list[str] = []

    def fit(self, features, labels=None) -> "OneClassSVMDetector":
        frame = self._ensure_frame(features)
        self.feature_names_ = list(frame.columns)
        self.model.fit(frame.to_numpy(dtype=float))
        return self

    def decision_function(self, features) -> np.ndarray:
        frame = self._align_frame(features)
        return -self.model.decision_function(frame.to_numpy(dtype=float)).ravel()

    def predict(self, features) -> np.ndarray:
        frame = self._align_frame(features)
        raw_predictions = self.model.predict(frame.to_numpy(dtype=float))
        return (raw_predictions == -1).astype(int)
