from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime

from .config import TrainConfig


class DatasetValidationError(ValueError):
    """Raised when the training dataset does not match the expected schema."""


@dataclass(frozen=True)
class PreparedDataset:
    rows: list[dict[str, str]]
    timestamps: list[datetime]
    targets: list[float | int]
    features: list[list[object]]
    sample_weights: list[float] | None
    feature_columns: list[str]
    categorical_columns: list[str]
    cat_feature_indices: list[int]

    @property
    def row_count(self) -> int:
        return len(self.rows)


def prepare_dataset(config: TrainConfig, max_rows: int | None = None) -> PreparedDataset:
    with config.dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetValidationError("Dataset is missing a header row.")

        fieldnames = [name.strip() for name in reader.fieldnames]
        required_columns = {
            config.target_column,
            config.time_column,
            *config.categorical_columns,
            *config.id_columns,
            *config.ignore_columns,
            *config.feature_columns,
        }
        if config.sample_weight is not None:
            required_columns.add(config.sample_weight.column)
        missing_columns = sorted(column for column in required_columns if column not in fieldnames)
        if missing_columns:
            raise DatasetValidationError(
                f"Dataset is missing required columns: {', '.join(missing_columns)}"
            )

        feature_columns = _resolve_feature_columns(fieldnames, config)
        categorical_columns = list(config.categorical_columns)
        cat_feature_indices = [
            feature_columns.index(column) for column in categorical_columns if column in feature_columns
        ]

        rows: list[dict[str, str]] = []
        timestamps: list[datetime] = []
        targets: list[float | int] = []
        features: list[list[object]] = []
        raw_sample_weights: list[float] | None = (
            [] if config.sample_weight is not None else None
        )

        for row_number, row in enumerate(reader, start=2):
            if max_rows is not None and len(rows) >= max_rows:
                break
            normalized_row = {key.strip(): value.strip() for key, value in row.items() if key is not None}
            raw_target = normalized_row.get(config.target_column, "")
            if config.skip_missing_target_rows and _is_missing_value(raw_target):
                continue
            timestamp = _parse_timestamp(normalized_row.get(config.time_column, ""), row_number)
            target = _parse_target(
                raw_target,
                problem_type=config.problem_type,
                row_number=row_number,
            )
            feature_vector = [
                _coerce_feature_value(
                    normalized_row.get(column, ""),
                    is_categorical=column in categorical_columns,
                    row_number=row_number,
                    column=column,
                )
                for column in feature_columns
            ]
            if raw_sample_weights is not None:
                raw_sample_weights.append(
                    _parse_sample_weight_source_value(
                        normalized_row.get(config.sample_weight.column, ""),
                        row_number=row_number,
                        column=config.sample_weight.column,
                    )
                )

            rows.append(normalized_row)
            timestamps.append(timestamp)
            targets.append(target)
            features.append(feature_vector)

    if not rows:
        raise DatasetValidationError("Dataset has no data rows.")

    return PreparedDataset(
        rows=rows,
        timestamps=timestamps,
        targets=targets,
        features=features,
        sample_weights=_build_sample_weights(raw_sample_weights, config),
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        cat_feature_indices=cat_feature_indices,
    )


def _resolve_feature_columns(fieldnames: list[str], config: TrainConfig) -> list[str]:
    if config.feature_columns:
        feature_columns = list(config.feature_columns)
    else:
        excluded = {
            config.target_column,
            config.time_column,
            *config.ignore_columns,
        }
        feature_columns = [column for column in fieldnames if column not in excluded]

    if not feature_columns:
        raise DatasetValidationError("No feature columns were selected for training.")

    unknown_categorical = [
        column for column in config.categorical_columns if column not in feature_columns
    ]
    if unknown_categorical:
        raise DatasetValidationError(
            "Categorical columns must also be present in feature_columns: "
            + ", ".join(unknown_categorical)
        )

    return feature_columns


def _parse_timestamp(value: str, row_number: int) -> datetime:
    if not value:
        raise DatasetValidationError(f"Missing timestamp in row {row_number}.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetValidationError(
            f"Invalid timestamp '{value}' in row {row_number}."
        ) from exc


def _parse_target(value: str, problem_type: str, row_number: int) -> float | int:
    if _is_missing_value(value):
        raise DatasetValidationError(f"Missing target value in row {row_number}.")

    if problem_type == "regression":
        try:
            return float(value)
        except ValueError as exc:
            raise DatasetValidationError(
                f"Target must be numeric in row {row_number}, got '{value}'."
            ) from exc

    if value not in {"0", "1"}:
        raise DatasetValidationError(
            f"Binary classification targets must be 0 or 1 in row {row_number}, got '{value}'."
        )
    return int(value)


def _coerce_feature_value(
    value: str,
    *,
    is_categorical: bool,
    row_number: int,
    column: str,
) -> object:
    if is_categorical:
        return value if value else "__MISSING__"
    if value == "":
        return math.nan
    try:
        return float(value)
    except ValueError as exc:
        raise DatasetValidationError(
            f"Feature '{column}' must be numeric in row {row_number}, got '{value}'."
        ) from exc


def _parse_sample_weight_source_value(value: str, *, row_number: int, column: str) -> float:
    if _is_missing_value(value):
        raise DatasetValidationError(
            f"Sample weight source column '{column}' is missing in row {row_number}."
        )
    try:
        parsed_value = float(value)
    except ValueError as exc:
        raise DatasetValidationError(
            f"Sample weight source column '{column}' must be numeric in row {row_number}, got '{value}'."
        ) from exc
    if not math.isfinite(parsed_value):
        raise DatasetValidationError(
            f"Sample weight source column '{column}' must be finite in row {row_number}."
        )
    return parsed_value


def _build_sample_weights(
    raw_values: list[float] | None,
    config: TrainConfig,
) -> list[float] | None:
    if raw_values is None or config.sample_weight is None:
        return None

    transformed_weights = [
        _transform_sample_weight(
            value,
            transform=config.sample_weight.transform,
            column=config.sample_weight.column,
        )
        for value in raw_values
    ]

    if config.sample_weight.normalize == "mean":
        mean_weight = sum(transformed_weights) / len(transformed_weights)
        if mean_weight <= 0 or not math.isfinite(mean_weight):
            raise DatasetValidationError("Sample weights must have a positive finite mean.")
        transformed_weights = [value / mean_weight for value in transformed_weights]

    return transformed_weights


def _transform_sample_weight(value: float, *, transform: str, column: str) -> float:
    if transform == "identity":
        transformed = value
    elif transform == "log1p":
        if value < 0:
            raise DatasetValidationError(
                f"Sample weight column '{column}' must be >= 0 for log1p transform."
            )
        transformed = math.log1p(value)
    elif transform == "expm1":
        transformed = math.expm1(value)
    else:
        raise DatasetValidationError(f"Unsupported sample weight transform '{transform}'.")

    if transformed <= 0 or not math.isfinite(transformed):
        raise DatasetValidationError(
            f"Sample weight derived from column '{column}' must be positive and finite."
        )
    return transformed


def _is_missing_value(value: str) -> bool:
    return value.strip().lower() in {"", "nan", "na", "null", "none"}
