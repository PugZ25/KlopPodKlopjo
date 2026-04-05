from __future__ import annotations

import math


def regression_metrics(targets: list[float], predictions: list[float]) -> dict[str, float]:
    if not targets:
        raise ValueError("Regression metrics require at least one target value.")

    residuals = [target - prediction for target, prediction in zip(targets, predictions)]
    squared_errors = [residual * residual for residual in residuals]
    absolute_errors = [abs(residual) for residual in residuals]
    mean_target = sum(targets) / len(targets)
    total_variance = sum((target - mean_target) ** 2 for target in targets)
    explained_error = sum(squared_errors)

    r2 = 1.0
    if total_variance > 0:
        r2 = 1.0 - (explained_error / total_variance)

    return {
        "rmse": math.sqrt(sum(squared_errors) / len(squared_errors)),
        "mae": sum(absolute_errors) / len(absolute_errors),
        "mean_target": mean_target,
        "r2": r2,
    }


def binary_classification_metrics(
    targets: list[int],
    probabilities: list[float],
    threshold: float = 0.5,
) -> dict[str, float]:
    if not targets:
        raise ValueError("Classification metrics require at least one target value.")

    predicted_labels = [1 if probability >= threshold else 0 for probability in probabilities]
    true_positive = sum(
        1 for target, label in zip(targets, predicted_labels) if target == 1 and label == 1
    )
    true_negative = sum(
        1 for target, label in zip(targets, predicted_labels) if target == 0 and label == 0
    )
    false_positive = sum(
        1 for target, label in zip(targets, predicted_labels) if target == 0 and label == 1
    )
    false_negative = sum(
        1 for target, label in zip(targets, predicted_labels) if target == 1 and label == 0
    )

    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1 = _safe_divide(2 * precision * recall, precision + recall)

    return {
        "accuracy": _safe_divide(true_positive + true_negative, len(targets)),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "positive_rate": sum(targets) / len(targets),
    }


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
