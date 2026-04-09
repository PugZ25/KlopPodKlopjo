from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TrainConfig
from .dataset import PreparedDataset
from .metrics import binary_classification_metrics, regression_metrics
from .splits import DatasetSplit


@dataclass(frozen=True)
class TrainingArtifacts:
    model_path: Path
    metadata_path: Path
    predictions_path: Path
    metrics: dict[str, dict[str, float]]


def train_catboost_model(
    config: TrainConfig,
    dataset: PreparedDataset,
    splits: dict[str, DatasetSplit],
) -> TrainingArtifacts:
    try:
        from catboost import CatBoostClassifier, CatBoostRegressor, Pool
    except ImportError as exc:
        module_name = exc.name or "catboost"
        raise SystemExit(
            "Missing dependency: "
            f"{module_name}. Install with:\n"
            "python3 -m pip install -r ml/training/requirements.txt"
        ) from exc

    config.output_dir.mkdir(parents=True, exist_ok=True)

    train_split = splits["train"]
    validation_split = splits["validation"]
    test_split = splits["test"]

    train_pool = _build_pool(dataset, train_split, Pool)
    validation_pool = _build_pool(dataset, validation_split, Pool)
    test_pool = _build_pool(dataset, test_split, Pool)

    common_params = {
        "iterations": config.catboost.iterations,
        "learning_rate": config.catboost.learning_rate,
        "depth": config.catboost.depth,
        "l2_leaf_reg": config.catboost.l2_leaf_reg,
        "thread_count": _resolve_thread_count(config),
        "random_seed": config.catboost.random_seed,
        "verbose": config.catboost.verbose,
        "loss_function": config.catboost.resolved_loss_function(config.problem_type),
        "allow_writing_files": False,
    }
    if config.catboost.eval_metric:
        common_params["eval_metric"] = config.catboost.eval_metric

    if config.problem_type == "regression":
        model = CatBoostRegressor(**common_params)
    else:
        model = CatBoostClassifier(**common_params)

    model.fit(
        train_pool,
        eval_set=validation_pool,
        use_best_model=True,
        early_stopping_rounds=config.catboost.early_stopping_rounds,
    )

    metrics = _compute_split_metrics(
        model=model,
        dataset=dataset,
        splits=splits,
        problem_type=config.problem_type,
        test_pool=test_pool,
        train_pool=train_pool,
        validation_pool=validation_pool,
    )

    model_path = config.output_dir / "model.cbm"
    metadata_path = config.output_dir / "metadata.json"
    predictions_path = config.output_dir / "holdout_predictions.csv"

    model.save_model(str(model_path))
    _write_predictions(
        path=predictions_path,
        config=config,
        dataset=dataset,
        splits=splits,
        model=model,
        Pool=Pool,
    )
    _write_metadata(
        path=metadata_path,
        config=config,
        dataset=dataset,
        splits=splits,
        metrics=metrics,
        model=model,
    )

    return TrainingArtifacts(
        model_path=model_path,
        metadata_path=metadata_path,
        predictions_path=predictions_path,
        metrics=metrics,
    )


def _build_pool(dataset: PreparedDataset, split: DatasetSplit, Pool: Any) -> Any:
    rows = [dataset.features[index] for index in split.row_indices]
    targets = [dataset.targets[index] for index in split.row_indices]
    return Pool(
        data=rows,
        label=targets,
        cat_features=dataset.cat_feature_indices,
        feature_names=dataset.feature_columns,
    )


def _resolve_thread_count(config: TrainConfig) -> int | None:
    if config.catboost.thread_count is not None:
        return config.catboost.thread_count

    for variable_name in ("SLURM_CPUS_PER_TASK", "OMP_NUM_THREADS"):
        raw_value = os.environ.get(variable_name, "").strip()
        if not raw_value:
            continue
        try:
            value = int(raw_value)
        except ValueError:
            continue
        if value >= 1:
            return value

    return None


def _compute_split_metrics(
    *,
    model: Any,
    dataset: PreparedDataset,
    splits: dict[str, DatasetSplit],
    problem_type: str,
    train_pool: Any,
    validation_pool: Any,
    test_pool: Any,
) -> dict[str, dict[str, float]]:
    pool_by_name = {
        "train": train_pool,
        "validation": validation_pool,
        "test": test_pool,
    }
    metrics: dict[str, dict[str, float]] = {}

    for split_name, split in splits.items():
        targets = [dataset.targets[index] for index in split.row_indices]
        pool = pool_by_name[split_name]
        if problem_type == "regression":
            predictions = _flatten_predictions(model.predict(pool))
            metrics[split_name] = regression_metrics(
                [float(target) for target in targets],
                predictions,
            )
            continue

        probabilities = _positive_class_probabilities(model.predict_proba(pool))
        metrics[split_name] = binary_classification_metrics(
            [int(target) for target in targets],
            probabilities,
        )

    return metrics


def _write_predictions(
    *,
    path: Path,
    config: TrainConfig,
    dataset: PreparedDataset,
    splits: dict[str, DatasetSplit],
    model: Any,
    Pool: Any,
) -> None:
    fieldnames = ["split", config.time_column, *config.id_columns, config.target_column]
    if config.problem_type == "regression":
        fieldnames.append("prediction")
    else:
        fieldnames.extend(["prediction_probability", "predicted_label"])

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for split_name in ("validation", "test"):
            split = splits[split_name]
            pool = _build_pool(dataset, split, Pool)
            if config.problem_type == "regression":
                predictions = _flatten_predictions(model.predict(pool))
                for row_index, prediction in zip(split.row_indices, predictions):
                    writer.writerow(
                        {
                            "split": split_name,
                            config.time_column: dataset.rows[row_index][config.time_column],
                            **{
                                column: dataset.rows[row_index].get(column, "")
                                for column in config.id_columns
                            },
                            config.target_column: dataset.rows[row_index][config.target_column],
                            "prediction": f"{prediction:.10g}",
                        }
                    )
                continue

            probabilities = _positive_class_probabilities(model.predict_proba(pool))
            for row_index, probability in zip(split.row_indices, probabilities):
                writer.writerow(
                    {
                        "split": split_name,
                        config.time_column: dataset.rows[row_index][config.time_column],
                        **{
                            column: dataset.rows[row_index].get(column, "")
                            for column in config.id_columns
                        },
                        config.target_column: dataset.rows[row_index][config.target_column],
                        "prediction_probability": f"{probability:.10g}",
                        "predicted_label": 1 if probability >= 0.5 else 0,
                    }
                )


def _write_metadata(
    *,
    path: Path,
    config: TrainConfig,
    dataset: PreparedDataset,
    splits: dict[str, DatasetSplit],
    metrics: dict[str, dict[str, float]],
    model: Any,
) -> None:
    feature_importances = model.get_feature_importance()
    feature_ranking = sorted(
        (
            {
                "feature": feature_name,
                "importance": float(importance),
            }
            for feature_name, importance in zip(dataset.feature_columns, feature_importances)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config.config_path),
        "dataset_path": str(config.dataset_path),
        "output_dir": str(config.output_dir),
        "problem_type": config.problem_type,
        "feature_columns": dataset.feature_columns,
        "categorical_columns": dataset.categorical_columns,
        "cat_feature_indices": dataset.cat_feature_indices,
        "row_count": dataset.row_count,
        "split_summary": {
            split_name: {
                "row_count": split.row_count,
                "unique_time_count": split.unique_time_count,
                "start_time": split.start_time,
                "end_time": split.end_time,
            }
            for split_name, split in splits.items()
        },
        "catboost": {
            **asdict(config.catboost),
            "resolved_loss_function": config.catboost.resolved_loss_function(
                config.problem_type
            ),
            "best_iteration": model.get_best_iteration(),
        },
        "metrics": metrics,
        "feature_importances": feature_ranking,
    }

    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _flatten_predictions(values: Any) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    flattened: list[float] = []
    for value in values:
        if isinstance(value, list):
            flattened.append(float(value[0]))
        else:
            flattened.append(float(value))
    return flattened


def _positive_class_probabilities(values: Any) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    probabilities: list[float] = []
    for row in values:
        if isinstance(row, list):
            probabilities.append(float(row[-1]))
        else:
            probabilities.append(float(row))
    return probabilities
