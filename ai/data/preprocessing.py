from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_DATETIME_CANDIDATES = {
    "timestamp",
    "recorded_at",
    "created_at",
    "updated_at",
    "triggered_at",
    "event_time",
}


@dataclass
class DataPreprocessor:
    normalize_numeric: bool = True
    drop_duplicates: bool = True
    datetime_columns: list[str] | None = None

    numeric_columns_: list[str] = field(default_factory=list, init=False)
    categorical_columns_: list[str] = field(default_factory=list, init=False)
    datetime_columns_: list[str] = field(default_factory=list, init=False)
    numeric_fill_values_: dict[str, float] = field(default_factory=dict, init=False)
    categorical_fill_values_: dict[str, str] = field(default_factory=dict, init=False)
    numeric_means_: dict[str, float] = field(default_factory=dict, init=False)
    numeric_stds_: dict[str, float] = field(default_factory=dict, init=False)
    is_fitted_: bool = field(default=False, init=False)

    @staticmethod
    def normalize_column_name(column_name: str) -> str:
        normalized = str(column_name).strip().lower()
        normalized = normalized.replace(" ", "_").replace("-", "_")
        return normalized

    def clean_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        frame = dataframe.copy()
        frame.columns = [self.normalize_column_name(column) for column in frame.columns]

        if self.drop_duplicates:
            frame = frame.drop_duplicates().reset_index(drop=True)

        frame = frame.replace([np.inf, -np.inf], np.nan)

        for column in frame.select_dtypes(include=["object", "string"]).columns:
            frame[column] = frame[column].apply(
                lambda value: value.strip() if isinstance(value, str) else value
            )

        datetime_columns = self.datetime_columns or []
        inferred_datetime_columns = [
            column
            for column in frame.columns
            if column in DEFAULT_DATETIME_CANDIDATES or column.endswith("_time")
        ]
        for column in sorted(set(datetime_columns + inferred_datetime_columns)):
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True)

        return frame

    def fit(self, dataframe: pd.DataFrame, target_column: str | None = None) -> "DataPreprocessor":
        frame = self.clean_dataframe(dataframe)
        target_name = self.normalize_column_name(target_column) if target_column else None

        excluded_columns = {target_name} if target_name else set()
        self.datetime_columns_ = [
            column for column in frame.columns if pd.api.types.is_datetime64_any_dtype(frame[column])
        ]
        self.numeric_columns_ = [
            column
            for column in frame.select_dtypes(include=[np.number, "bool"]).columns
            if column not in excluded_columns
        ]
        self.categorical_columns_ = [
            column
            for column in frame.columns
            if column not in excluded_columns
            and column not in self.numeric_columns_
            and column not in self.datetime_columns_
        ]

        for column in self.numeric_columns_:
            series = pd.to_numeric(frame[column], errors="coerce")
            median = float(series.median()) if series.notna().any() else 0.0
            mean = float(series.mean()) if series.notna().any() else 0.0
            std = float(series.std(ddof=0)) if series.notna().any() else 1.0
            if std == 0.0 or np.isnan(std):
                std = 1.0
            self.numeric_fill_values_[column] = median
            self.numeric_means_[column] = mean
            self.numeric_stds_[column] = std

        for column in self.categorical_columns_:
            series = frame[column].dropna().astype("string")
            if series.empty:
                fill_value = "unknown"
            else:
                fill_value = str(series.mode().iloc[0])
            self.categorical_fill_values_[column] = fill_value

        self.is_fitted_ = True
        return self

    def transform(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        if not self.is_fitted_:
            raise RuntimeError("DataPreprocessor must be fitted before calling transform().")

        frame = self.clean_dataframe(dataframe)

        for column in self.numeric_columns_ + self.categorical_columns_ + self.datetime_columns_:
            if column not in frame.columns:
                frame[column] = np.nan

        for column in self.numeric_columns_:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame[column] = frame[column].fillna(self.numeric_fill_values_[column])
            if self.normalize_numeric:
                frame[column] = (frame[column] - self.numeric_means_[column]) / self.numeric_stds_[column]

        for column in self.categorical_columns_:
            frame[column] = frame[column].astype("string")
            frame[column] = frame[column].fillna(self.categorical_fill_values_[column])

        return frame

    def fit_transform(self, dataframe: pd.DataFrame, target_column: str | None = None) -> pd.DataFrame:
        return self.fit(dataframe, target_column=target_column).transform(dataframe)
