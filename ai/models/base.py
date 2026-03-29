from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseAnomalyDetector(ABC):
    def _ensure_frame(self, features) -> pd.DataFrame:
        if isinstance(features, pd.DataFrame):
            frame = features.copy()
        else:
            frame = pd.DataFrame(features)
        return frame

    def _align_frame(self, features) -> pd.DataFrame:
        frame = self._ensure_frame(features)
        if hasattr(self, "feature_names_"):
            for column in self.feature_names_:
                if column not in frame.columns:
                    frame[column] = 0.0
            frame = frame.reindex(columns=self.feature_names_, fill_value=0.0)
        return frame

    @abstractmethod
    def fit(self, features, labels=None):
        raise NotImplementedError

    @abstractmethod
    def predict(self, features):
        raise NotImplementedError

    @abstractmethod
    def decision_function(self, features):
        raise NotImplementedError

    def fit_predict(self, features, labels=None):
        self.fit(features, labels=labels)
        return self.predict(features)
