from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class FeatureExtractionPipeline:
    timestamp_columns: list[str] | None = None
    payload_column: str = "payload"

    feature_columns_: list[str] = field(default_factory=list, init=False)
    is_fitted_: bool = field(default=False, init=False)

    @staticmethod
    def _normalize_name(name: str) -> str:
        return str(name).strip().lower().replace(" ", "_").replace("-", "_")

    def _flatten_payload(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.payload_column not in frame.columns:
            return frame

        payload_series = frame[self.payload_column].apply(
            lambda value: value if isinstance(value, dict) else {}
        )
        payload_frame = pd.json_normalize(payload_series)
        if payload_frame.empty:
            frame = frame.drop(columns=[self.payload_column])
            return frame

        payload_frame.columns = [
            f"{self.payload_column}_{self._normalize_name(column)}"
            for column in payload_frame.columns
        ]
        payload_frame = payload_frame.reindex(frame.index)
        frame = frame.drop(columns=[self.payload_column])
        return pd.concat([frame, payload_frame], axis=1)

    def _add_time_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        candidate_columns = set(self.timestamp_columns or [])
        candidate_columns.update(
            column
            for column in frame.columns
            if pd.api.types.is_datetime64_any_dtype(frame[column])
        )

        for column in sorted(candidate_columns):
            if column not in frame.columns:
                continue

            timestamp = pd.to_datetime(frame[column], errors="coerce", utc=True)
            frame[f"{column}_hour"] = timestamp.dt.hour.fillna(-1).astype(float)
            frame[f"{column}_day_of_week"] = timestamp.dt.dayofweek.fillna(-1).astype(float)
            frame[f"{column}_day_of_month"] = timestamp.dt.day.fillna(-1).astype(float)
            frame[f"{column}_is_weekend"] = timestamp.dt.dayofweek.isin([5, 6]).astype(float)
            elapsed = (timestamp - timestamp.min()).dt.total_seconds()
            frame[f"{column}_elapsed_seconds"] = elapsed.fillna(0.0)
            frame = frame.drop(columns=[column])

        return frame

    def _transform_frame(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        frame = dataframe.copy()
        frame.columns = [self._normalize_name(column) for column in frame.columns]
        frame = self._flatten_payload(frame)
        frame = self._add_time_features(frame)

        object_columns = frame.select_dtypes(include=["object", "string", "category"]).columns
        frame = pd.get_dummies(frame, columns=list(object_columns), dummy_na=True, dtype=float)

        for column in frame.select_dtypes(include=["bool"]).columns:
            frame[column] = frame[column].astype(float)

        frame = frame.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        return frame

    def fit(self, dataframe: pd.DataFrame) -> "FeatureExtractionPipeline":
        transformed = self._transform_frame(dataframe)
        self.feature_columns_ = list(transformed.columns)
        self.is_fitted_ = True
        return self

    def transform(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        transformed = self._transform_frame(dataframe)
        if not self.is_fitted_:
            return transformed

        for column in self.feature_columns_:
            if column not in transformed.columns:
                transformed[column] = 0.0

        transformed = transformed.reindex(columns=self.feature_columns_, fill_value=0.0)
        return transformed

    def fit_transform(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        self.fit(dataframe)
        return self.transform(dataframe)
