from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _normalize_binary_labels(values: Any) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype == bool:
        return array.astype(int)

    unique_values = set(np.unique(array))
    if unique_values.issubset({0, 1}):
        return array.astype(int)
    if unique_values.issubset({-1, 1}):
        return np.where(array == -1, 1, 0).astype(int)

    return (array.astype(float) > 0).astype(int)


def evaluate_anomaly_detection(y_true, y_pred, scores=None) -> dict[str, float | int | None]:
    true_labels = _normalize_binary_labels(y_true)
    predicted_labels = _normalize_binary_labels(y_pred)

    tn, fp, fn, tp = confusion_matrix(true_labels, predicted_labels, labels=[0, 1]).ravel()
    metrics: dict[str, float | int | None] = {
        "accuracy": float(accuracy_score(true_labels, predicted_labels)),
        "precision": float(precision_score(true_labels, predicted_labels, zero_division=0)),
        "recall": float(recall_score(true_labels, predicted_labels, zero_division=0)),
        "f1_score": float(f1_score(true_labels, predicted_labels, zero_division=0)),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "roc_auc": None,
        "average_precision": None,
    }

    if scores is not None and len(np.unique(true_labels)) > 1:
        score_values = np.asarray(scores, dtype=float)
        metrics["roc_auc"] = float(roc_auc_score(true_labels, score_values))
        metrics["average_precision"] = float(
            average_precision_score(true_labels, score_values)
        )

    return metrics


def evaluate_detector(detector, features, labels) -> dict[str, float | int | None]:
    predictions = detector.predict(features)
    scores = detector.decision_function(features)
    return evaluate_anomaly_detection(labels, predictions, scores=scores)
