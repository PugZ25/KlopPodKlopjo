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
        "roc_auc": roc_auc_score(targets, probabilities),
        "pr_auc": average_precision_score(targets, probabilities),
    }


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def roc_auc_score(targets: list[int], scores: list[float]) -> float:
    if len(targets) != len(scores):
        raise ValueError("targets and scores must have the same length.")

    paired = sorted(zip(scores, targets), key=lambda item: item[0])
    positive_count = sum(targets)
    negative_count = len(targets) - positive_count
    if positive_count == 0 or negative_count == 0:
        return 0.0

    rank_sum_for_positives = 0.0
    index = 0
    while index < len(paired):
        group_end = index + 1
        while group_end < len(paired) and paired[group_end][0] == paired[index][0]:
            group_end += 1

        average_rank = (index + 1 + group_end) / 2.0
        positive_in_group = sum(target for _, target in paired[index:group_end])
        rank_sum_for_positives += average_rank * positive_in_group
        index = group_end

    return _safe_divide(
        rank_sum_for_positives - (positive_count * (positive_count + 1) / 2.0),
        positive_count * negative_count,
    )


def average_precision_score(targets: list[int], scores: list[float]) -> float:
    if len(targets) != len(scores):
        raise ValueError("targets and scores must have the same length.")

    positive_count = sum(targets)
    if positive_count == 0:
        return 0.0

    paired = sorted(zip(scores, targets), key=lambda item: item[0], reverse=True)
    true_positive = 0
    precision_sum = 0.0

    for rank, (_, target) in enumerate(paired, start=1):
        if target != 1:
            continue
        true_positive += 1
        precision_sum += true_positive / rank

    return precision_sum / positive_count
