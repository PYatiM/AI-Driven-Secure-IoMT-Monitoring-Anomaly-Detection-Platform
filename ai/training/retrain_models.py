from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.training.train_models import MODEL_BUILDERS, train_models
from ai.versioning import ModelRegistry


def retrain_models(
    data_path: str | Path,
    output_dir: str | Path,
    registry_path: str | Path | None = None,
    models: list[str] | None = None,
    file_format: str = "csv",
    target_column: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    stratify: bool = False,
) -> dict[str, dict[str, object]]:
    selected_models = models or list(MODEL_BUILDERS.keys())
    registry = ModelRegistry(registry_path or Path(output_dir) / "model_registry.json")

    return train_models(
        data_path=data_path,
        output_dir=output_dir,
        file_format=file_format,
        target_column=target_column,
        models=selected_models,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
        registry_path=registry.path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retrain anomaly detection models.")
    parser.add_argument("--data", required=True, help="Path to the training dataset.")
    parser.add_argument(
        "--output-dir",
        default="ai/artifacts",
        help="Directory where retrained model artifacts will be saved.",
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
        help="Models to retrain.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--stratify", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    results = retrain_models(
        data_path=args.data,
        output_dir=args.output_dir,
        registry_path=args.registry_path,
        models=args.models,
        file_format=args.file_format,
        target_column=args.target_column,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=args.stratify,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
