from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from ai.data.features import FeatureExtractionPipeline
from ai.data.preprocessing import DataPreprocessor


@dataclass
class DatasetBundle:
    features: pd.DataFrame
    labels: pd.Series | None
    feature_names: list[str]


@dataclass
class DatasetSplit:
    train: DatasetBundle
    test: DatasetBundle


class TelemetryDatasetLoader:
    def __init__(
        self,
        preprocessor: DataPreprocessor | None = None,
        feature_pipeline: FeatureExtractionPipeline | None = None,
    ) -> None:
        self.preprocessor = preprocessor or DataPreprocessor()
        self.feature_pipeline = feature_pipeline or FeatureExtractionPipeline()

    @staticmethod
    def load_csv(path: str | Path, **kwargs) -> pd.DataFrame:
        return pd.read_csv(path, **kwargs)

    @staticmethod
    def load_json(path: str | Path, **kwargs) -> pd.DataFrame:
        return pd.read_json(path, **kwargs)

    def _split_target(
        self,
        dataframe: pd.DataFrame,
        target_column: str | None,
    ) -> tuple[pd.DataFrame, pd.Series | None]:
        if not target_column:
            return dataframe.copy(), None

        normalized_target = self.preprocessor.normalize_column_name(target_column)
        frame = dataframe.copy()
        frame.columns = [self.preprocessor.normalize_column_name(column) for column in frame.columns]
        labels = frame[normalized_target].copy() if normalized_target in frame.columns else None
        features = frame.drop(columns=[normalized_target], errors="ignore")
        return features, labels

    def prepare_dataframe(
        self,
        dataframe: pd.DataFrame,
        target_column: str | None = None,
        fit: bool = True,
    ) -> DatasetBundle:
        features, labels = self._split_target(dataframe, target_column)

        if fit:
            cleaned = self.preprocessor.fit_transform(features)
            extracted = self.feature_pipeline.fit_transform(cleaned)
        else:
            cleaned = self.preprocessor.transform(features)
            extracted = self.feature_pipeline.transform(cleaned)

        labels = labels.reset_index(drop=True) if labels is not None else None
        extracted = extracted.reset_index(drop=True)
        return DatasetBundle(
            features=extracted,
            labels=labels,
            feature_names=list(extracted.columns),
        )

    def load_for_training(
        self,
        path: str | Path,
        file_format: str = "csv",
        target_column: str | None = None,
        **kwargs,
    ) -> DatasetBundle:
        file_format = file_format.lower()
        if file_format == "csv":
            dataframe = self.load_csv(path, **kwargs)
        elif file_format == "json":
            dataframe = self.load_json(path, **kwargs)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

        return self.prepare_dataframe(dataframe, target_column=target_column, fit=True)

    def train_test_split(
        self,
        dataframe: pd.DataFrame,
        target_column: str | None,
        test_size: float = 0.2,
        random_state: int = 42,
        stratify: bool = False,
    ) -> DatasetSplit:
        features, labels = self._split_target(dataframe, target_column)
        stratify_labels = labels if stratify and labels is not None else None

        train_features, test_features, train_labels, test_labels = train_test_split(
            features,
            labels,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify_labels,
        )

        train_frame = train_features.reset_index(drop=True)
        test_frame = test_features.reset_index(drop=True)

        if train_labels is not None:
            train_frame[target_column] = train_labels.reset_index(drop=True)
            test_frame[target_column] = test_labels.reset_index(drop=True)

        train_bundle = self.prepare_dataframe(train_frame, target_column=target_column, fit=True)
        test_bundle = self.prepare_dataframe(test_frame, target_column=target_column, fit=False)
        return DatasetSplit(train=train_bundle, test=test_bundle)
