from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ai.data.loader import TelemetryDatasetLoader
from ai.evaluation.metrics import evaluate_detector
from ai.models.isolation_forest import IsolationForestDetector
from ai.models.one_class_svm import OneClassSVMDetector
from ai.models.zscore import ZScoreAnomalyDetector
from ai.persistence import ModelArtifact, save_model_artifact
from ai.versioning import (
    ModelRegistry,
    ModelVersionRecord,
    compute_file_fingerprint,
    create_version_tag,
)

MODEL_BUILDERS = {
    "zscore": ZScoreAnomalyDetector,
    "isolation_forest": IsolationForestDetector,
    "one_class_svm": OneClassSVMDetector,
}


def train_models(
    data_path: str | Path,
    output_dir: str | Path,
    file_format: str = "csv",
    target_column: str | None = None,
    models: list[str] | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    stratify: bool = False,
    registry_path: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    selected_models = models or list(MODEL_BUILDERS.keys())
    output_path = Path(output_dir)
    registry = ModelRegistry(registry_path or output_path / "model_registry.json")
    loader = TelemetryDatasetLoader()
    data_fingerprint = compute_file_fingerprint(data_path)

    if file_format.lower() == "csv":
        dataframe = loader.load_csv(data_path)
    elif file_format.lower() == "json":
        dataframe = loader.load_json(data_path)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

    if target_column:
        dataset_split = loader.train_test_split(
            dataframe,
            target_column=target_column,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )
        train_bundle = dataset_split.train
        evaluation_bundle = dataset_split.test
    else:
        train_bundle = loader.prepare_dataframe(dataframe, target_column=None, fit=True)
        evaluation_bundle = None

    results: dict[str, dict[str, object]] = {}
    for model_name in selected_models:
        if model_name not in MODEL_BUILDERS:
            raise ValueError(f"Unsupported model: {model_name}")

        previous_record = registry.get_latest(model_name)
        version = create_version_tag()

        detector = MODEL_BUILDERS[model_name]()
        detector.fit(train_bundle.features, labels=train_bundle.labels)
        training_scores = detector.decision_function(train_bundle.features)

        metrics = None
        if evaluation_bundle is not None and evaluation_bundle.labels is not None:
            metrics = evaluate_detector(
                detector,
                evaluation_bundle.features,
                evaluation_bundle.labels,
            )

        artifact = ModelArtifact(
            model_name=model_name,
            version=version,
            detector=detector,
            preprocessor=loader.preprocessor,
            feature_pipeline=loader.feature_pipeline,
            parent_version=previous_record.version if previous_record else None,
            calibration={
                "score_min": float(np.min(training_scores)),
                "score_max": float(np.max(training_scores)),
                "score_mean": float(np.mean(training_scores)),
                "score_std": float(np.std(training_scores)),
            },
            training_metrics=metrics,
            feature_names=train_bundle.feature_names,
            training_data_fingerprint=data_fingerprint,
        )

        artifact_path = save_model_artifact(
            artifact,
            output_path / f"{model_name}_{version}.joblib",
        )
        registry.register(
            ModelVersionRecord(
                model_name=model_name,
                version=version,
                artifact_path=str(artifact_path),
                created_at=artifact.trained_at,
                parent_version=artifact.parent_version,
                training_data_path=str(data_path),
                training_data_fingerprint=data_fingerprint,
                metrics=metrics,
            )
        )

        results[model_name] = {
            "version": version,
            "artifact_path": str(artifact_path),
            "parent_version": artifact.parent_version,
            "metrics": metrics,
            "feature_count": len(train_bundle.feature_names),
        }

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train anomaly detection models.")
    parser.add_argument("--data", required=True, help="Path to the training dataset.")
    parser.add_argument(
        "--output-dir",
        default="ai/artifacts",
        help="Directory where trained model artifacts will be saved.",
    )
    parser.add_argument(
        "--registry-path",
        default=None,
        help="Optional path to the model registry JSON file.",
    )
    parser.add_argument(
        "--file-format",
        default="csv",
        choices=["csv", "json"],
        help="Dataset file format.",
    )
    parser.add_argument(
        "--target-column",
        default=None,
        help="Optional target column for evaluation metrics.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_BUILDERS.keys()),
        choices=list(MODEL_BUILDERS.keys()),
        help="Models to train.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--stratify", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    results = train_models(
        data_path=args.data,
        output_dir=args.output_dir,
        file_format=args.file_format,
        target_column=args.target_column,
        models=args.models,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=args.stratify,
        registry_path=args.registry_path,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
