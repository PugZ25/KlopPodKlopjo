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

        for row_number, row in enumerate(reader, start=2):
            if max_rows is not None and len(rows) >= max_rows:
                break
            normalized_row = {key.strip(): value.strip() for key, value in row.items() if key is not None}
            timestamp = _parse_timestamp(normalized_row.get(config.time_column, ""), row_number)
            target = _parse_target(
                normalized_row.get(config.target_column, ""),
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
    if value == "":
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
