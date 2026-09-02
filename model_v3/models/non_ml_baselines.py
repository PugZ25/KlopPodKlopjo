from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from model_v3.validation.rolling_origin import (
    MANIFEST_COLUMNS,
    RollingOriginFold,
    TargetWindowRow,
    generate_rolling_origin_folds,
    load_config as load_validation_config,
    read_target_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_non_ml_baselines.json"
)

BASELINE_A = "baseline_a_overall_history"
BASELINE_B = "baseline_b_municipality_history"
BASELINE_C = "baseline_c_seasonal_history"
BASELINE_D = "baseline_d_municipality_seasonal_history"
BASELINE_E = "baseline_e_four_week_persistence"
BASELINE_IDS = (BASELINE_A, BASELINE_B, BASELINE_C, BASELINE_D, BASELINE_E)

PREDICTION_COLUMNS = (
    "fold_id",
    "baseline_id",
    "baseline_name",
    "municipality_code",
    "issue_week",
    "iso_week",
    "target_window_start",
    "target_window_end",
    "actual_target_lyme_cases_next_4w",
    "predicted_target_lyme_cases_next_4w",
    "prediction_status",
    "prediction_source",
    "n_historical_rows_used",
    "fit_target_end_max",
    "observed_case_window_start",
    "observed_case_window_end",
    "latest_information_week_used",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)

FOLD_METRIC_COLUMNS = (
    "fold_id",
    "baseline_id",
    "baseline_name",
    "n_expected_predictions",
    "n_available_predictions",
    "n_missing_predictions",
    "prediction_metric_status",
    "mae",
    "rmse",
    "mean_poisson_deviance",
    "poisson_deviance_status",
    "n_poisson_valid",
    "n_poisson_invalid",
)

AGGREGATE_METRIC_COLUMNS = (
    "baseline_id",
    "baseline_name",
    "n_folds",
    "n_expected_predictions",
    "n_available_predictions",
    "n_missing_predictions",
    "prediction_metric_status",
    "pooled_mae",
    "mean_fold_mae",
    "pooled_rmse",
    "mean_fold_rmse",
    "pooled_mean_poisson_deviance",
    "poisson_deviance_status",
    "n_poisson_valid",
    "n_poisson_invalid",
)


class BaselineValidationError(ValueError):
    """Raised when baseline inputs, predictions, or metrics violate their contract."""


@dataclass(frozen=True)
class HistoricalPrediction:
    value: float
    source: str
    n_historical_rows: int


@dataclass(frozen=True)
class HistoricalExpectations:
    overall: HistoricalPrediction
    municipality: Mapping[str, HistoricalPrediction]
    seasonal: Mapping[int, HistoricalPrediction]
    municipality_seasonal: Mapping[tuple[str, int], HistoricalPrediction]
    latest_target_end: date


@dataclass(frozen=True)
class PersistencePrediction:
    value: int | None
    status: str
    n_observed_weeks: int
    information_window_start: date
    information_window_end: date
    latest_information_week: date


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise BaselineValidationError(
            f"Configured path must be a non-empty string: {raw_path!r}"
        )
    relative = Path(raw_path)
    if relative.is_absolute():
        raise BaselineValidationError(
            f"Configured path must be repository-relative: {raw_path}"
        )
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise BaselineValidationError(
            f"Configured path leaves repository root: {raw_path}"
        )
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise BaselineValidationError(
            f"Baseline configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise BaselineValidationError(
            "Baseline configuration schema_version must equal 1."
        )
    inputs = config.get("inputs")
    baselines = config.get("baselines")
    persistence = config.get("persistence")
    metrics = config.get("metrics")
    outputs = config.get("outputs")
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        raise BaselineValidationError("Baseline inputs and outputs are required.")
    if not isinstance(baselines, list) or not isinstance(persistence, dict):
        raise BaselineValidationError(
            "Baseline definitions and persistence configuration are required."
        )
    if not isinstance(metrics, dict):
        raise BaselineValidationError("Baseline metric configuration is required.")

    expected_input_keys = {
        "weekly_cases",
        "calendar",
        "validation_config",
        "validation_manifest",
    }
    if set(inputs) != expected_input_keys:
        raise BaselineValidationError(
            "Baseline input keys do not match the required contract."
        )
    for key, value in inputs.items():
        if not isinstance(value, str) or not value:
            raise BaselineValidationError(
                f"Baseline input {key} must be a non-empty path."
            )

    observed_baseline_ids = [definition.get("baseline_id") for definition in baselines]
    if observed_baseline_ids != list(BASELINE_IDS):
        raise BaselineValidationError(
            f"Baseline IDs must equal {list(BASELINE_IDS)} in order."
        )
    for definition in baselines:
        for key in ("name", "definition", "availability"):
            if not isinstance(definition.get(key), str) or not definition[key]:
                raise BaselineValidationError(
                    f"Baseline {definition.get('baseline_id')} requires {key}."
                )

    if persistence.get("prior_week_offsets") != [4, 3, 2, 1]:
        raise BaselineValidationError(
            "Persistence must use exactly prior-week offsets [4, 3, 2, 1]."
        )
    if persistence.get("missing_prior_week_rule") != "prediction_missing":
        raise BaselineValidationError(
            "Missing persistence weeks must produce a missing prediction."
        )
    expected_metrics = {
        "mae": "mean_absolute_error",
        "rmse": "root_mean_squared_error",
        "poisson_deviance": (
            "mean_poisson_deviance_only_when_all_prediction_observation_pairs_are_mathematically_valid"
        ),
        "poisson_zero_prediction_rule": (
            "mu_zero_y_zero_has_zero_contribution_mu_zero_y_positive_is_invalid"
        ),
    }
    if metrics != expected_metrics:
        raise BaselineValidationError(
            "Baseline metric configuration does not match the required contract."
        )

    expected_output_keys = {
        "directory",
        "baseline_configuration",
        "fold_predictions",
        "fold_metrics",
        "aggregate_metrics",
        "quality_summary",
    }
    if set(outputs) != expected_output_keys:
        raise BaselineValidationError(
            "Baseline output keys do not match the required contract."
        )
    for key, value in outputs.items():
        if not isinstance(value, str) or not value:
            raise BaselineValidationError(
                f"Baseline output {key} must be a non-empty string."
            )
    return config


def parse_code(value: object, *, context: str) -> str:
    code = str(value).strip() if value is not None else ""
    if not re.fullmatch(r"\d{3}", code):
        raise BaselineValidationError(
            f"{context} must be a three-digit municipality code: {value!r}"
        )
    return code


def parse_monday(value: object, *, context: str) -> date:
    if isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise BaselineValidationError(
                f"{context} is not an ISO date: {value!r}"
            ) from exc
    else:
        raise BaselineValidationError(f"{context} is not a date: {value!r}")
    if result.weekday() != 0:
        raise BaselineValidationError(
            f"{context} must be a Monday: {result.isoformat()}"
        )
    return result


def parse_nonnegative_integer(value: object, *, context: str) -> int:
    if isinstance(value, bool):
        raise BaselineValidationError(f"{context} must not be boolean.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value):
        result = int(value)
    else:
        raise BaselineValidationError(
            f"{context} must be a present non-negative integer: {value!r}"
        )
    if result < 0:
        raise BaselineValidationError(f"{context} must not be negative.")
    return result


def read_development_weekly_cases(
    path: Path, *, lockbox_year: int
) -> dict[tuple[str, date], int]:
    required = {"municipality_code", "issue_week", "lyme_cases"}
    lockbox_start = date(lockbox_year, 1, 1)
    values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(required - set(reader.fieldnames or []))
        if missing_columns:
            raise BaselineValidationError(
                f"Canonical weekly cases are missing columns: {missing_columns}"
            )
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"weekly row {row_index} issue_week"
            )
            if issue_week >= lockbox_start:
                continue
            code = parse_code(
                row["municipality_code"], context=f"weekly row {row_index} code"
            )
            value = parse_nonnegative_integer(
                row["lyme_cases"], context=f"weekly[{code}, {issue_week}] Lyme cases"
            )
            key = (code, issue_week)
            if key in values:
                raise BaselineValidationError(
                    f"Canonical weekly cases contain duplicate key {key}."
                )
            values[key] = value
    if not values:
        raise BaselineValidationError("Development weekly Lyme input is empty.")
    return values


def read_development_iso_weeks(
    path: Path, *, lockbox_year: int
) -> dict[date, int]:
    required = {"issue_week", "year", "iso_week"}
    lockbox_start = date(lockbox_year, 1, 1)
    values: dict[date, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(required - set(reader.fieldnames or []))
        if missing_columns:
            raise BaselineValidationError(
                f"Canonical calendar is missing columns: {missing_columns}"
            )
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"calendar row {row_index} issue_week"
            )
            if issue_week >= lockbox_start:
                continue
            iso_year = parse_nonnegative_integer(
                row["year"], context=f"calendar row {row_index} ISO year"
            )
            iso_week = parse_nonnegative_integer(
                row["iso_week"], context=f"calendar row {row_index} ISO week"
            )
            actual_iso = issue_week.isocalendar()
            if (iso_year, iso_week) != (actual_iso.year, actual_iso.week):
                raise BaselineValidationError(
                    f"Calendar row {row_index} disagrees with its issue week."
                )
            if issue_week in values:
                raise BaselineValidationError(
                    f"Canonical calendar contains duplicate date {issue_week}."
                )
            values[issue_week] = iso_week
    return values


def read_selected_target_values(
    path: Path, selected_keys: set[tuple[str, date]]
) -> dict[tuple[str, date], int]:
    required = {
        "municipality_code",
        "issue_week",
        "target_lyme_cases_next_4w",
    }
    values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(required - set(reader.fieldnames or []))
        if missing_columns:
            raise BaselineValidationError(
                f"Lyme target input is missing columns: {missing_columns}"
            )
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"target row {row_index} issue_week"
            )
            code = parse_code(
                row["municipality_code"], context=f"target row {row_index} code"
            )
            key = (code, issue_week)
            if key not in selected_keys:
                continue
            if key in values:
                raise BaselineValidationError(
                    f"Lyme target input contains duplicate selected key {key}."
                )
            values[key] = parse_nonnegative_integer(
                row["target_lyme_cases_next_4w"],
                context=f"target[{code}, {issue_week}] value",
            )
    missing_keys = sorted(selected_keys - set(values))
    if missing_keys:
        raise BaselineValidationError(
            f"Selected fold targets are missing values: {missing_keys[:20]}"
        )
    return values


def mean_prediction(total: int, count: int, *, source: str) -> HistoricalPrediction:
    if count <= 0:
        raise BaselineValidationError(f"Cannot calculate empty expectation for {source}.")
    return HistoricalPrediction(total / count, source, count)


def fit_historical_expectations(
    train_rows: Sequence[TargetWindowRow],
    target_values: Mapping[tuple[str, date], int],
    iso_week_by_date: Mapping[date, int],
) -> HistoricalExpectations:
    if not train_rows:
        raise BaselineValidationError("Historical baselines require training rows.")
    overall_total = 0
    municipality_totals: Counter[str] = Counter()
    municipality_counts: Counter[str] = Counter()
    seasonal_totals: Counter[int] = Counter()
    seasonal_counts: Counter[int] = Counter()
    cell_totals: Counter[tuple[str, int]] = Counter()
    cell_counts: Counter[tuple[str, int]] = Counter()
    for row in train_rows:
        key = (row.municipality_code, row.issue_week)
        if key not in target_values:
            raise BaselineValidationError(f"Training target value is missing for {key}.")
        if row.issue_week not in iso_week_by_date:
            raise BaselineValidationError(
                f"Training ISO week is missing for {row.issue_week}."
            )
        value = target_values[key]
        iso_week = iso_week_by_date[row.issue_week]
        overall_total += value
        municipality_totals[row.municipality_code] += value
        municipality_counts[row.municipality_code] += 1
        seasonal_totals[iso_week] += value
        seasonal_counts[iso_week] += 1
        cell = (row.municipality_code, iso_week)
        cell_totals[cell] += value
        cell_counts[cell] += 1
    return HistoricalExpectations(
        overall=mean_prediction(
            overall_total, len(train_rows), source="overall_training_mean"
        ),
        municipality={
            code: mean_prediction(
                municipality_totals[code],
                count,
                source="municipality_training_mean",
            )
            for code, count in municipality_counts.items()
        },
        seasonal={
            iso_week: mean_prediction(
                seasonal_totals[iso_week], count, source="iso_week_training_mean"
            )
            for iso_week, count in seasonal_counts.items()
        },
        municipality_seasonal={
            cell: mean_prediction(
                cell_totals[cell], count, source="municipality_iso_week_training_mean"
            )
            for cell, count in cell_counts.items()
        },
        latest_target_end=max(row.target_window_end for row in train_rows),
    )


def predict_historical_baselines(
    expectations: HistoricalExpectations,
    *,
    municipality_code: str,
    iso_week: int,
) -> dict[str, HistoricalPrediction]:
    overall = expectations.overall
    municipality = expectations.municipality.get(municipality_code)
    if municipality is None:
        municipality = HistoricalPrediction(
            overall.value,
            "fallback_overall_training_mean",
            overall.n_historical_rows,
        )
    seasonal = expectations.seasonal.get(iso_week)
    if seasonal is None:
        seasonal = HistoricalPrediction(
            overall.value,
            "fallback_overall_training_mean",
            overall.n_historical_rows,
        )
    municipality_seasonal = expectations.municipality_seasonal.get(
        (municipality_code, iso_week)
    )
    if municipality_seasonal is None:
        if municipality_code in expectations.municipality:
            source_prediction = expectations.municipality[municipality_code]
            municipality_seasonal = HistoricalPrediction(
                source_prediction.value,
                "fallback_municipality_training_mean",
                source_prediction.n_historical_rows,
            )
        elif iso_week in expectations.seasonal:
            source_prediction = expectations.seasonal[iso_week]
            municipality_seasonal = HistoricalPrediction(
                source_prediction.value,
                "fallback_iso_week_training_mean",
                source_prediction.n_historical_rows,
            )
        else:
            municipality_seasonal = HistoricalPrediction(
                overall.value,
                "fallback_overall_training_mean",
                overall.n_historical_rows,
            )
    return {
        BASELINE_A: overall,
        BASELINE_B: municipality,
        BASELINE_C: seasonal,
        BASELINE_D: municipality_seasonal,
    }


def calculate_persistence_prediction(
    weekly_cases: Mapping[tuple[str, date], int],
    *,
    municipality_code: str,
    issue_week: date,
    prior_week_offsets: Sequence[int] = (4, 3, 2, 1),
) -> PersistencePrediction:
    if tuple(prior_week_offsets) != (4, 3, 2, 1):
        raise BaselineValidationError(
            "Persistence requires exactly offsets (4, 3, 2, 1)."
        )
    required_weeks = [
        issue_week - timedelta(weeks=offset) for offset in prior_week_offsets
    ]
    observed_values = [
        weekly_cases[(municipality_code, week)]
        for week in required_weeks
        if (municipality_code, week) in weekly_cases
    ]
    status = "available" if len(observed_values) == 4 else "missing_prior_week"
    value = sum(observed_values) if status == "available" else None
    return PersistencePrediction(
        value=value,
        status=status,
        n_observed_weeks=len(observed_values),
        information_window_start=required_weeks[0],
        information_window_end=required_weeks[-1],
        latest_information_week=required_weeks[-1],
    )


def poisson_deviance_contribution(
    observed: int, prediction: float
) -> tuple[float | None, str]:
    if observed < 0 or prediction < 0:
        raise BaselineValidationError(
            "Poisson deviance requires non-negative observations and predictions."
        )
    if prediction == 0:
        if observed == 0:
            return 0.0, "valid_zero_limit"
        return None, "invalid_zero_prediction_positive_observation"
    if observed == 0:
        return 2 * prediction, "valid"
    contribution = 2 * (
        observed * math.log(observed / prediction) - (observed - prediction)
    )
    return contribution, "valid"


def summarize_prediction_metrics(
    predictions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not predictions:
        raise BaselineValidationError("Metric calculation requires predictions.")
    available = [
        row
        for row in predictions
        if row["predicted_target_lyme_cases_next_4w"] is not None
    ]
    if not available:
        return {
            "n_expected_predictions": len(predictions),
            "n_available_predictions": 0,
            "n_missing_predictions": len(predictions),
            "prediction_metric_status": "no_available_predictions",
            "mae": None,
            "rmse": None,
            "mean_poisson_deviance": None,
            "poisson_deviance_status": "not_available",
            "n_poisson_valid": 0,
            "n_poisson_invalid": 0,
        }
    absolute_errors = [
        abs(
            int(row["actual_target_lyme_cases_next_4w"])
            - float(row["predicted_target_lyme_cases_next_4w"])
        )
        for row in available
    ]
    squared_errors = [value * value for value in absolute_errors]
    poisson_valid = [
        float(row["poisson_deviance_contribution"])
        for row in available
        if row["poisson_deviance_contribution"] is not None
    ]
    poisson_invalid = len(available) - len(poisson_valid)
    missing = len(predictions) - len(available)
    if poisson_invalid:
        mean_poisson: float | None = None
        poisson_status = "invalid_zero_prediction_positive_observation_present"
    else:
        mean_poisson = sum(poisson_valid) / len(poisson_valid)
        poisson_status = "valid"
    return {
        "n_expected_predictions": len(predictions),
        "n_available_predictions": len(available),
        "n_missing_predictions": missing,
        "prediction_metric_status": "complete" if missing == 0 else "partial",
        "mae": sum(absolute_errors) / len(absolute_errors),
        "rmse": math.sqrt(sum(squared_errors) / len(squared_errors)),
        "mean_poisson_deviance": mean_poisson,
        "poisson_deviance_status": poisson_status,
        "n_poisson_valid": len(poisson_valid),
        "n_poisson_invalid": poisson_invalid,
    }


def csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.15g}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv_rows(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row[column]) for column in columns})


def validate_manifest_matches_folds(
    manifest_path: Path, folds: Sequence[RollingOriginFold]
) -> None:
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
            raise BaselineValidationError(
                "Validation manifest columns do not match the Phase 6 contract."
            )
        observed = list(reader)
    expected = [
        {column: str(csv_value(fold.manifest_record()[column])) for column in MANIFEST_COLUMNS}
        for fold in folds
    ]
    if observed != expected:
        raise BaselineValidationError(
            "Validation manifest does not match regenerated Phase 6 folds."
        )


def build_non_ml_baselines(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {
        key: resolve_repo_path(value) for key, value in config["inputs"].items()
    }
    missing_inputs = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing_inputs:
        raise BaselineValidationError(f"Baseline inputs do not exist: {missing_inputs}")

    validation_config = load_validation_config(input_paths["validation_config"])
    policy = validation_config["policy"]
    lockbox_year = policy["lockbox_year"]
    target_path = resolve_repo_path(validation_config["input"]["path"])
    target_metadata = read_target_metadata(target_path)
    folds = generate_rolling_origin_folds(
        target_metadata,
        development_start_year=policy["development_start_year"],
        development_end_year=policy["development_end_year"],
        lockbox_year=lockbox_year,
    )
    validate_manifest_matches_folds(input_paths["validation_manifest"], folds)

    selected_keys = {
        (row.municipality_code, row.issue_week)
        for fold in folds
        for row in fold.train_rows + fold.validation_rows
    }
    target_values = read_selected_target_values(target_path, selected_keys)
    weekly_cases = read_development_weekly_cases(
        input_paths["weekly_cases"], lockbox_year=lockbox_year
    )
    iso_week_by_date = read_development_iso_weeks(
        input_paths["calendar"], lockbox_year=lockbox_year
    )
    required_issue_dates = {
        row.issue_week
        for fold in folds
        for row in fold.train_rows + fold.validation_rows
    }
    missing_iso_dates = sorted(required_issue_dates - set(iso_week_by_date))
    if missing_iso_dates:
        raise BaselineValidationError(
            f"Fold issue weeks are missing from the calendar: {missing_iso_dates[:20]}"
        )

    baseline_names = {
        definition["baseline_id"]: definition["name"]
        for definition in config["baselines"]
    }
    prior_offsets = tuple(config["persistence"]["prior_week_offsets"])
    prediction_rows: list[dict[str, object]] = []
    fold_metric_rows: list[dict[str, object]] = []

    for fold in folds:
        expectations = fit_historical_expectations(
            fold.train_rows, target_values, iso_week_by_date
        )
        if expectations.latest_target_end >= fold.validation_start:
            raise BaselineValidationError(
                f"{fold.fold_id} historical fit reaches validation."
            )
        fold_predictions: list[dict[str, object]] = []
        for validation_row in fold.validation_rows:
            key = (validation_row.municipality_code, validation_row.issue_week)
            actual_target = target_values[key]
            iso_week = iso_week_by_date[validation_row.issue_week]
            historical_predictions = predict_historical_baselines(
                expectations,
                municipality_code=validation_row.municipality_code,
                iso_week=iso_week,
            )
            for baseline_id in BASELINE_IDS[:4]:
                prediction = historical_predictions[baseline_id]
                contribution, poisson_status = poisson_deviance_contribution(
                    actual_target, prediction.value
                )
                fold_predictions.append(
                    {
                        "fold_id": fold.fold_id,
                        "baseline_id": baseline_id,
                        "baseline_name": baseline_names[baseline_id],
                        "municipality_code": validation_row.municipality_code,
                        "issue_week": validation_row.issue_week,
                        "iso_week": iso_week,
                        "target_window_start": validation_row.target_window_start,
                        "target_window_end": validation_row.target_window_end,
                        "actual_target_lyme_cases_next_4w": actual_target,
                        "predicted_target_lyme_cases_next_4w": prediction.value,
                        "prediction_status": "available",
                        "prediction_source": prediction.source,
                        "n_historical_rows_used": prediction.n_historical_rows,
                        "fit_target_end_max": expectations.latest_target_end,
                        "observed_case_window_start": None,
                        "observed_case_window_end": None,
                        "latest_information_week_used": expectations.latest_target_end,
                        "poisson_deviance_contribution": contribution,
                        "poisson_deviance_status": poisson_status,
                    }
                )

            persistence = calculate_persistence_prediction(
                weekly_cases,
                municipality_code=validation_row.municipality_code,
                issue_week=validation_row.issue_week,
                prior_week_offsets=prior_offsets,
            )
            if persistence.value is None:
                contribution = None
                poisson_status = "prediction_missing"
            else:
                contribution, poisson_status = poisson_deviance_contribution(
                    actual_target, float(persistence.value)
                )
            fold_predictions.append(
                {
                    "fold_id": fold.fold_id,
                    "baseline_id": BASELINE_E,
                    "baseline_name": baseline_names[BASELINE_E],
                    "municipality_code": validation_row.municipality_code,
                    "issue_week": validation_row.issue_week,
                    "iso_week": iso_week,
                    "target_window_start": validation_row.target_window_start,
                    "target_window_end": validation_row.target_window_end,
                    "actual_target_lyme_cases_next_4w": actual_target,
                    "predicted_target_lyme_cases_next_4w": persistence.value,
                    "prediction_status": persistence.status,
                    "prediction_source": "observed_lyme_cases_t_minus_4_through_t_minus_1",
                    "n_historical_rows_used": persistence.n_observed_weeks,
                    "fit_target_end_max": None,
                    "observed_case_window_start": persistence.information_window_start,
                    "observed_case_window_end": persistence.information_window_end,
                    "latest_information_week_used": persistence.latest_information_week,
                    "poisson_deviance_contribution": contribution,
                    "poisson_deviance_status": poisson_status,
                }
            )

        fold_predictions.sort(
            key=lambda row: (
                BASELINE_IDS.index(str(row["baseline_id"])),
                str(row["municipality_code"]),
                row["issue_week"],
            )
        )
        prediction_rows.extend(fold_predictions)
        for baseline_id in BASELINE_IDS:
            baseline_predictions = [
                row for row in fold_predictions if row["baseline_id"] == baseline_id
            ]
            summary = summarize_prediction_metrics(baseline_predictions)
            fold_metric_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "baseline_id": baseline_id,
                    "baseline_name": baseline_names[baseline_id],
                    **summary,
                }
            )

    aggregate_metric_rows: list[dict[str, object]] = []
    for baseline_id in BASELINE_IDS:
        baseline_predictions = [
            row for row in prediction_rows if row["baseline_id"] == baseline_id
        ]
        pooled = summarize_prediction_metrics(baseline_predictions)
        baseline_fold_metrics = [
            row for row in fold_metric_rows if row["baseline_id"] == baseline_id
        ]
        aggregate_metric_rows.append(
            {
                "baseline_id": baseline_id,
                "baseline_name": baseline_names[baseline_id],
                "n_folds": len(baseline_fold_metrics),
                "n_expected_predictions": pooled["n_expected_predictions"],
                "n_available_predictions": pooled["n_available_predictions"],
                "n_missing_predictions": pooled["n_missing_predictions"],
                "prediction_metric_status": pooled["prediction_metric_status"],
                "pooled_mae": pooled["mae"],
                "mean_fold_mae": sum(
                    float(row["mae"]) for row in baseline_fold_metrics
                )
                / len(baseline_fold_metrics),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": sum(
                    float(row["rmse"]) for row in baseline_fold_metrics
                )
                / len(baseline_fold_metrics),
                "pooled_mean_poisson_deviance": pooled[
                    "mean_poisson_deviance"
                ],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
                "n_poisson_valid": pooled["n_poisson_valid"],
                "n_poisson_invalid": pooled["n_poisson_invalid"],
            }
        )

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key != "directory"
    }
    if any(path.parent != output_directory for path in output_paths.values()):
        raise BaselineValidationError(
            "Baseline output filenames must not contain subdirectories."
        )

    write_csv_rows(
        output_paths["fold_predictions"], PREDICTION_COLUMNS, prediction_rows
    )
    write_csv_rows(
        output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, fold_metric_rows
    )
    write_csv_rows(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        aggregate_metric_rows,
    )

    source_records = {
        "weekly_cases": file_record(input_paths["weekly_cases"]),
        "calendar": file_record(input_paths["calendar"]),
        "target": file_record(target_path),
        "validation_config": file_record(input_paths["validation_config"]),
        "validation_manifest": file_record(input_paths["validation_manifest"]),
        "baseline_input_config": file_record(config_path),
        "builder": file_record(Path(__file__).resolve()),
    }
    realized_configuration: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.non_ml_baselines",
        "development_policy": {
            "start_year": policy["development_start_year"],
            "end_year": policy["development_end_year"],
            "excluded_lockbox_year": lockbox_year,
            "fold_strategy": policy["fold_strategy"],
        },
        "target": {
            "column": "target_lyme_cases_next_4w",
            "unit": "municipality_x_issue_week",
            "forecast_window": "t_plus_1_through_t_plus_4",
        },
        "baselines": config["baselines"],
        "persistence": config["persistence"],
        "metrics": config["metrics"],
        "folds": [
            {key: csv_value(value) for key, value in fold.manifest_record().items()}
            for fold in folds
        ],
        "sources": source_records,
    }
    output_paths["baseline_configuration"].write_text(
        json.dumps(realized_configuration, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    lockbox_start = date(lockbox_year, 1, 1)
    historical_rows = [
        row for row in prediction_rows if row["baseline_id"] != BASELINE_E
    ]
    persistence_rows = [
        row for row in prediction_rows if row["baseline_id"] == BASELINE_E
    ]
    expected_prediction_count = sum(len(fold.validation_rows) for fold in folds) * len(
        BASELINE_IDS
    )
    selected_fold_rows = [
        row
        for fold in folds
        for row in fold.train_rows + fold.validation_rows
    ]
    lockbox_target_values_used = sum(
        row.target_window_end >= lockbox_start for row in selected_fold_rows
    )
    lockbox_weekly_case_values_used = sum(
        issue_week >= lockbox_start for _, issue_week in weekly_cases
    )
    output_records = {
        key: file_record(path)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.non_ml_baselines",
        "status": "pass",
        "sources": source_records,
        "outputs": output_records,
        "summary": {
            "fold_count": len(folds),
            "baseline_count": len(BASELINE_IDS),
            "validation_municipality_week_rows": sum(
                len(fold.validation_rows) for fold in folds
            ),
            "prediction_rows": len(prediction_rows),
            "fold_metric_rows": len(fold_metric_rows),
            "aggregate_metric_rows": len(aggregate_metric_rows),
            "selected_target_values_used": len(target_values),
            "persistence_missing_predictions": sum(
                row["predicted_target_lyme_cases_next_4w"] is None
                for row in persistence_rows
            ),
        },
        "checks": {
            "validation_manifest_matches_regenerated_folds": True,
            "prediction_row_count_matches_fold_contract": len(prediction_rows)
            == expected_prediction_count,
            "all_prediction_issue_weeks_precede_lockbox": all(
                row["issue_week"] < lockbox_start for row in prediction_rows
            ),
            "all_prediction_target_windows_precede_lockbox": all(
                row["target_window_end"] < lockbox_start for row in prediction_rows
            ),
            "all_historical_fit_targets_precede_validation": all(
                row["fit_target_end_max"] < next(
                    fold.validation_start
                    for fold in folds
                    if fold.fold_id == row["fold_id"]
                )
                for row in historical_rows
            ),
            "all_persistence_information_precedes_issue_week": all(
                row["latest_information_week_used"] < row["issue_week"]
                for row in persistence_rows
            ),
            "persistence_current_week_used": False,
            "persistence_future_week_used": False,
            "centered_rolling_window_used": False,
            "lockbox_target_values_used": lockbox_target_values_used,
            "lockbox_weekly_case_values_used": lockbox_weekly_case_values_used,
            "weather_features_used": False,
            "environmental_features_used": False,
            "machine_learning_model_trained": False,
            "catboost_used": False,
            "classification_auc_computed": False,
            "lockbox_performance_computed": False,
        },
        "aggregate_metrics": [
            {key: csv_value(value) for key, value in row.items()}
            for row in aggregate_metric_rows
        ],
    }
    output_paths["quality_summary"].write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate non-ML Lyme count baselines on development folds."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the non-ML baseline configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_non_ml_baselines(config_path)
    summary = quality["summary"]
    print("Non-ML Lyme development baselines evaluated.")
    print(f"- folds: {summary['fold_count']}")
    print(f"- baselines: {summary['baseline_count']}")
    print(f"- validation municipality-week rows: {summary['validation_municipality_week_rows']}")
    print(f"- fold prediction rows: {summary['prediction_rows']}")
    print(f"- persistence missing predictions: {summary['persistence_missing_predictions']}")
    print("Aggregate development metrics:")
    for row in quality["aggregate_metrics"]:
        print(
            f"- {row['baseline_id']}: MAE={row['pooled_mae']}, "
            f"RMSE={row['pooled_rmse']}, "
            f"Poisson={row['pooled_mean_poisson_deviance'] or 'not valid'}"
        )
    print("The 2025 lockbox was not opened or evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
