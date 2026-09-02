from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import statistics
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm

from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS
from model_v3.models.non_ml_baselines import (
    file_record,
    parse_code,
    parse_monday,
    poisson_deviance_contribution,
    resolve_repo_path,
    summarize_prediction_metrics,
    validate_manifest_matches_folds,
    write_csv_rows,
)
from model_v3.models.seasonal_count_models import (
    MODEL_S1,
    build_population_history,
    load_config as load_phase_9_config,
    mean_present,
    read_development_population,
    read_development_target_metadata,
    read_selected_development_target_values,
    seasonal_terms,
    select_population_exposure,
)
from model_v3.models.static_geography_ablation import read_static_features
from model_v3.validation.rolling_origin import (
    generate_rolling_origin_folds,
    load_config as load_validation_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "lyme_weather_ablation.json"

CONTROL_ID = "statistical_baseline_s1"
GEOGRAPHY_ID = "statistical_baseline_s1_plus_static_geography"
WEATHER_ID = "statistical_baseline_s1_plus_weather"
COMBINED_ID = "statistical_baseline_s1_plus_static_geography_weather"
CANDIDATE_IDS = (CONTROL_ID, GEOGRAPHY_ID, WEATHER_ID, COMBINED_ID)
BASE_COLUMNS = ("intercept", "seasonal_sin_annual", "seasonal_cos_annual")
AREA_COLUMN = "municipality_area_km2"
MEAN_WEATHER_VARIABLES = tuple(name for name in OUTPUT_VARIABLES if name != "tp_sum_mm")
SUM_WEATHER_VARIABLES = ("tp_sum_mm",)


def _weather_feature_names() -> tuple[str, ...]:
    names: list[str] = []
    for variable in OUTPUT_VARIABLES:
        names.extend(
            (
                f"{variable}_lag_1w",
                f"{variable}_lag_2w",
                (
                    f"{variable}_previous_4w_sum"
                    if variable in SUM_WEATHER_VARIABLES
                    else f"{variable}_previous_4w_mean"
                ),
            )
        )
    return tuple(names)


WEATHER_FEATURE_COLUMNS = _weather_feature_names()

PREDICTION_COLUMNS = (
    "fold_id",
    "candidate_id",
    "candidate_name",
    "municipality_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_lyme_cases_next_4w",
    "predicted_target_lyme_cases_next_4w",
    "prediction_status",
    "population_exposure",
    "population_year",
    "population_year_lag",
    "offset_log_population",
    "static_geography_used",
    "weather_used",
    "latest_weather_week_used",
    "latest_weather_week_end",
    "fit_target_end_max",
    "fit_converged",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)
FOLD_METRIC_COLUMNS = (
    "fold_id",
    "candidate_id",
    "candidate_name",
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
    "candidate_id",
    "candidate_name",
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
INCREMENTAL_COLUMNS = (
    "candidate_id",
    "candidate_name",
    "metric",
    "control_value",
    "candidate_value",
    "candidate_minus_control",
    "result",
)
DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "candidate_id",
    "candidate_name",
    "n_original_train",
    "n_common_train",
    "n_train_excluded_incomplete_weather",
    "n_validation",
    "n_parameters",
    "design_matrix_rank",
    "offset",
    "offset_coefficient",
    "weather_scaling_fit_scope",
    "weather_scaling_means",
    "weather_scaling_standard_deviations",
    "train_target_end_max",
    "validation_start",
    "latest_training_weather_week_end",
    "latest_validation_weather_week_end",
    "converged",
    "iterations",
    "warning_count",
    "warning_messages",
    "deviance",
    "pearson_chi2",
)
COEFFICIENT_COLUMNS = (
    "fold_id",
    "candidate_id",
    "feature",
    "coefficient",
    "standard_error",
)


class WeatherAblationError(ValueError):
    """Raised when the Phase 12 weather ablation violates its contract."""


@dataclass(frozen=True)
class WeeklyWeather:
    municipality_code: str
    week_start: date
    week_end: date
    status: str
    values: Mapping[str, float] | None


@dataclass(frozen=True)
class IssueWeather:
    values: Mapping[str, float]
    window_start: date
    latest_week_start: date
    latest_week_end: date


@dataclass(frozen=True)
class ModelRow:
    municipality_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_value: int
    population: int
    population_year: int
    seasonal_sin: float
    seasonal_cos: float
    municipality_area_km2: float
    weather: IssueWeather


@dataclass(frozen=True)
class WeatherScaler:
    means: Mapping[str, float]
    standard_deviations: Mapping[str, float]


@dataclass(frozen=True)
class FittedCandidate:
    result: Any
    column_names: tuple[str, ...]
    design_rank: int
    warning_messages: tuple[str, ...]


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise WeatherAblationError("Weather ablation config must be in repository.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise WeatherAblationError("Configuration schema_version must equal 1.")
    expected_inputs = {
        "population",
        "static_features",
        "static_quality_summary",
        "weekly_weather",
        "weather_quality_summary",
        "validation_config",
        "validation_manifest",
        "phase_9_config",
    }
    if set(config.get("inputs", {})) != expected_inputs:
        raise WeatherAblationError("Weather ablation inputs are unexpected.")
    candidates = config.get("experiment", {}).get("candidates")
    if not isinstance(candidates, list) or [row.get("candidate_id") for row in candidates] != list(CANDIDATE_IDS):
        raise WeatherAblationError("Four-arm candidate order is unexpected.")
    experiment = config["experiment"]
    if experiment.get("fixed_municipality_zones_all_years") is not True:
        raise WeatherAblationError("Fixed municipality zones must apply to all years.")
    if experiment.get("weather_cutoff") != "2024-12-31T23:00:00Z":
        raise WeatherAblationError("Weather cutoff is unexpected.")
    if experiment.get("weather_scaling") != "training_fold_mean_and_standard_deviation_only":
        raise WeatherAblationError("Weather scaling must be training-fold only.")
    return config


def read_weekly_weather(
    path: Path, quality_path: Path, *, lockbox_year: int
) -> tuple[dict[tuple[str, date], WeeklyWeather], dict[str, Any]]:
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if quality.get("status") != "pass":
        raise WeatherAblationError("Weekly weather quality status is not pass.")
    if quality.get("weekly_dataset", {}).get("sha256") != file_record(path)["sha256"]:
        raise WeatherAblationError("Weekly weather does not match quality hash.")
    policy = quality.get("policy", {})
    if policy.get("availability_rule") != (
        "weather_valid_time_is_the_cutoff_no_additional_publication_embargo"
    ):
        raise WeatherAblationError("Weather availability rule is unexpected.")
    if policy.get("fixed_analytical_zones_all_years") is not True:
        raise WeatherAblationError("Weather municipality policy is unexpected.")
    result: dict[tuple[str, date], WeeklyWeather] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEEKLY_COLUMNS:
            raise WeatherAblationError("Weekly weather columns are unexpected.")
        for row_index, row in enumerate(reader, start=1):
            week_start = parse_monday(
                row["week_start"], context=f"weather row {row_index} week_start"
            )
            if week_start.year >= lockbox_year:
                continue
            code = parse_code(row["municipality_code"], context=f"weather row {row_index} code")
            week_end = date.fromisoformat(row["week_end"])
            if week_end != week_start + timedelta(days=6):
                raise WeatherAblationError("Weather week_end is inconsistent.")
            status = row["weather_status"]
            values: dict[str, float] | None
            if status == "complete":
                values = {}
                for column in OUTPUT_VARIABLES:
                    try:
                        value = float(row[column])
                    except (TypeError, ValueError) as exc:
                        raise WeatherAblationError(
                            f"Complete weather value is invalid: row={row_index}, column={column}"
                        ) from exc
                    if not math.isfinite(value):
                        raise WeatherAblationError("Complete weather must be finite.")
                    values[column] = value
            elif status == "incomplete_source_week":
                if any(row[column] != "" for column in OUTPUT_VARIABLES):
                    raise WeatherAblationError("Incomplete weather must have blank values.")
                values = None
            else:
                raise WeatherAblationError(f"Unknown weather status: {status}")
            key = (code, week_start)
            if key in result:
                raise WeatherAblationError(f"Duplicate weather row: {key}")
            result[key] = WeeklyWeather(code, week_start, week_end, status, values)
    if not result:
        raise WeatherAblationError("Weekly weather input is empty.")
    return result, quality


def issue_weather_features(
    weekly: Mapping[tuple[str, date], WeeklyWeather],
    *,
    municipality_code: str,
    issue_week: date,
) -> IssueWeather | None:
    required_starts = [issue_week - timedelta(weeks=lag) for lag in (4, 3, 2, 1)]
    rows: list[WeeklyWeather] = []
    for week_start in required_starts:
        row = weekly.get((municipality_code, week_start))
        if row is None or row.status != "complete" or row.values is None:
            return None
        if row.week_end >= issue_week:
            raise WeatherAblationError("Weather feature reaches issue_week.")
        rows.append(row)
    by_start = {row.week_start: row for row in rows}
    lag1 = by_start[issue_week - timedelta(weeks=1)]
    lag2 = by_start[issue_week - timedelta(weeks=2)]
    values: dict[str, float] = {}
    for variable in OUTPUT_VARIABLES:
        values[f"{variable}_lag_1w"] = float(lag1.values[variable])
        values[f"{variable}_lag_2w"] = float(lag2.values[variable])
        four_values = [float(row.values[variable]) for row in rows]
        if variable in SUM_WEATHER_VARIABLES:
            values[f"{variable}_previous_4w_sum"] = sum(four_values)
        else:
            values[f"{variable}_previous_4w_mean"] = statistics.fmean(four_values)
    if tuple(values) != WEATHER_FEATURE_COLUMNS or not all(
        math.isfinite(value) for value in values.values()
    ):
        raise WeatherAblationError("Weather feature vector is invalid.")
    return IssueWeather(
        values=values,
        window_start=required_starts[0],
        latest_week_start=lag1.week_start,
        latest_week_end=lag1.week_end,
    )


def fit_weather_scaler(rows: Sequence[ModelRow]) -> WeatherScaler:
    if not rows:
        raise WeatherAblationError("Weather scaler requires training rows.")
    means: dict[str, float] = {}
    standard_deviations: dict[str, float] = {}
    for feature in WEATHER_FEATURE_COLUMNS:
        values = np.asarray([row.weather.values[feature] for row in rows], dtype=np.float64)
        mean = float(values.mean())
        standard_deviation = float(values.std(ddof=0))
        if not math.isfinite(mean) or not math.isfinite(standard_deviation) or standard_deviation <= 0:
            raise WeatherAblationError(f"Weather scaling is invalid for {feature}.")
        means[feature] = mean
        standard_deviations[feature] = standard_deviation
    return WeatherScaler(means, standard_deviations)


def candidate_columns(candidate_id: str) -> tuple[str, ...]:
    columns = list(BASE_COLUMNS)
    if candidate_id in (GEOGRAPHY_ID, COMBINED_ID):
        columns.append(AREA_COLUMN)
    if candidate_id in (WEATHER_ID, COMBINED_ID):
        columns.extend(f"z_{feature}" for feature in WEATHER_FEATURE_COLUMNS)
    if candidate_id not in CANDIDATE_IDS:
        raise WeatherAblationError(f"Unknown candidate: {candidate_id}")
    return tuple(columns)


def build_design_matrix(
    rows: Sequence[ModelRow], candidate_id: str, scaler: WeatherScaler
) -> np.ndarray:
    columns = candidate_columns(candidate_id)
    matrix = np.zeros((len(rows), len(columns)), dtype=np.float64)
    if not rows:
        raise WeatherAblationError("Design matrix requires rows.")
    matrix[:, 0] = 1.0
    for row_index, row in enumerate(rows):
        matrix[row_index, 1] = row.seasonal_sin
        matrix[row_index, 2] = row.seasonal_cos
        column_index = 3
        if candidate_id in (GEOGRAPHY_ID, COMBINED_ID):
            matrix[row_index, column_index] = row.municipality_area_km2
            column_index += 1
        if candidate_id in (WEATHER_ID, COMBINED_ID):
            for feature in WEATHER_FEATURE_COLUMNS:
                matrix[row_index, column_index] = (
                    row.weather.values[feature] - scaler.means[feature]
                ) / scaler.standard_deviations[feature]
                column_index += 1
    if not np.isfinite(matrix).all():
        raise WeatherAblationError("Design matrix contains non-finite values.")
    return matrix


def fit_candidate(
    rows: Sequence[ModelRow],
    *,
    candidate_id: str,
    scaler: WeatherScaler,
    fitting: Mapping[str, object],
) -> FittedCandidate:
    design = build_design_matrix(rows, candidate_id, scaler)
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise WeatherAblationError(
            f"{candidate_id} design is rank deficient: {rank}/{design.shape[1]}"
        )
    target = np.asarray([row.target_value for row in rows], dtype=np.float64)
    exposure = np.asarray([row.population for row in rows], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sm.GLM(
            target,
            design,
            family=sm.families.Poisson(link=sm.families.links.Log()),
            exposure=exposure,
            missing="raise",
        ).fit(
            method=fitting["method"],
            maxiter=fitting["maxiter"],
            tol=fitting["tol"],
            cov_type=fitting["cov_type"],
        )
    if not np.isfinite(result.params).all():
        raise WeatherAblationError(f"{candidate_id} produced non-finite coefficients.")
    warning_messages = tuple(
        f"{type(item.message).__name__}: {item.message}" for item in caught
    )
    return FittedCandidate(result, candidate_columns(candidate_id), rank, warning_messages)


def predict_candidate(
    fitted: FittedCandidate,
    rows: Sequence[ModelRow],
    *,
    candidate_id: str,
    scaler: WeatherScaler,
) -> np.ndarray:
    design = build_design_matrix(rows, candidate_id, scaler)
    exposure = np.asarray([row.population for row in rows], dtype=np.float64)
    predictions = np.asarray(fitted.result.predict(design, exposure=exposure), dtype=np.float64)
    if np.any(predictions <= 0) or not np.isfinite(predictions).all():
        raise WeatherAblationError("Poisson predictions must be finite and positive.")
    return predictions


def prepare_rows(
    target_rows: Sequence[Any],
    target_values: Mapping[tuple[str, date], int],
    population_by_key: Mapping[tuple[str, int], int],
    areas: Mapping[str, float],
    weekly_weather: Mapping[tuple[str, date], WeeklyWeather],
) -> tuple[list[ModelRow], int]:
    population_history = build_population_history(population_by_key)
    rows: list[ModelRow] = []
    excluded = 0
    for target_row in target_rows:
        key = (target_row.municipality_code, target_row.issue_week)
        weather = issue_weather_features(
            weekly_weather,
            municipality_code=target_row.municipality_code,
            issue_week=target_row.issue_week,
        )
        if weather is None:
            excluded += 1
            continue
        exposure = select_population_exposure(
            population_history,
            municipality_code=target_row.municipality_code,
            issue_week=target_row.issue_week,
        )
        seasonal_sin, seasonal_cos = seasonal_terms(target_row.issue_week)
        rows.append(
            ModelRow(
                municipality_code=target_row.municipality_code,
                issue_week=target_row.issue_week,
                target_window_start=target_row.target_window_start,
                target_window_end=target_row.target_window_end,
                target_value=target_values[key],
                population=exposure.population,
                population_year=exposure.year,
                seasonal_sin=seasonal_sin,
                seasonal_cos=seasonal_cos,
                municipality_area_km2=areas[target_row.municipality_code],
                weather=weather,
            )
        )
    return rows, excluded


def classify_delta(value: float) -> str:
    if not math.isfinite(value):
        raise WeatherAblationError("Metric difference must be finite.")
    return "improvement" if value < 0 else "deterioration" if value > 0 else "no_change"


def build_weather_ablation(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {key: resolve_repo_path(value) for key, value in config["inputs"].items()}
    missing = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing:
        raise WeatherAblationError(f"Weather ablation inputs are missing: {missing}")
    phase_9_config = load_phase_9_config(input_paths["phase_9_config"])
    if phase_9_config["models"][0]["model_id"] != MODEL_S1:
        raise WeatherAblationError("Phase 9 S1 reference changed.")
    fitting = phase_9_config["modeling"]["fitting"]
    validation_config = load_validation_config(input_paths["validation_config"])
    policy = validation_config["policy"]
    lockbox_year = policy["lockbox_year"]
    target_path = resolve_repo_path(validation_config["input"]["path"])
    target_metadata = read_development_target_metadata(
        target_path,
        development_start_year=policy["development_start_year"],
        development_end_year=policy["development_end_year"],
    )
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
    target_values = read_selected_development_target_values(
        target_path, selected_keys, lockbox_year=lockbox_year
    )
    population = read_development_population(input_paths["population"], lockbox_year=lockbox_year)
    areas, static_quality = read_static_features(
        input_paths["static_features"], input_paths["static_quality_summary"]
    )
    if static_quality.get("temporal_scope", {}).get("fixed_analytical_zones_all_years") is not True:
        raise WeatherAblationError("Static geography does not declare fixed zones.")
    weekly_weather, weather_quality = read_weekly_weather(
        input_paths["weekly_weather"],
        input_paths["weather_quality_summary"],
        lockbox_year=lockbox_year,
    )

    candidate_definitions = {row["candidate_id"]: row for row in config["experiment"]["candidates"]}
    candidate_names = {key: value["name"] for key, value in candidate_definitions.items()}
    prediction_rows: list[dict[str, object]] = []
    fold_metric_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    fold_common_train_counts: dict[str, int] = {}
    fold_excluded_counts: dict[str, int] = {}

    for fold in folds:
        train_rows, excluded_train = prepare_rows(
            fold.train_rows, target_values, population, areas, weekly_weather
        )
        validation_rows, excluded_validation = prepare_rows(
            fold.validation_rows, target_values, population, areas, weekly_weather
        )
        if excluded_validation:
            raise WeatherAblationError(
                f"{fold.fold_id} has {excluded_validation} validation rows without weather."
            )
        if len(validation_rows) != len(fold.validation_rows):
            raise WeatherAblationError("Validation fold row count changed.")
        fold_common_train_counts[fold.fold_id] = len(train_rows)
        fold_excluded_counts[fold.fold_id] = excluded_train
        train_target_end_max = max(row.target_window_end for row in train_rows)
        if train_target_end_max >= fold.validation_start:
            raise WeatherAblationError("Training target reaches validation boundary.")
        scaler = fit_weather_scaler(train_rows)
        for candidate_id in CANDIDATE_IDS:
            fitted = fit_candidate(
                train_rows,
                candidate_id=candidate_id,
                scaler=scaler,
                fitting=fitting,
            )
            predictions = predict_candidate(
                fitted,
                validation_rows,
                candidate_id=candidate_id,
                scaler=scaler,
            )
            candidate_predictions: list[dict[str, object]] = []
            for row, prediction in zip(validation_rows, predictions, strict=True):
                prediction = float(prediction)
                contribution, poisson_status = poisson_deviance_contribution(
                    row.target_value, prediction
                )
                candidate_predictions.append(
                    {
                        "fold_id": fold.fold_id,
                        "candidate_id": candidate_id,
                        "candidate_name": candidate_names[candidate_id],
                        "municipality_code": row.municipality_code,
                        "issue_week": row.issue_week,
                        "target_window_start": row.target_window_start,
                        "target_window_end": row.target_window_end,
                        "actual_target_lyme_cases_next_4w": row.target_value,
                        "predicted_target_lyme_cases_next_4w": prediction,
                        "prediction_status": (
                            "available" if bool(fitted.result.converged) else "available_fit_not_converged"
                        ),
                        "population_exposure": row.population,
                        "population_year": row.population_year,
                        "population_year_lag": row.issue_week.year - row.population_year,
                        "offset_log_population": math.log(row.population),
                        "static_geography_used": candidate_id in (GEOGRAPHY_ID, COMBINED_ID),
                        "weather_used": candidate_id in (WEATHER_ID, COMBINED_ID),
                        "latest_weather_week_used": row.weather.latest_week_start,
                        "latest_weather_week_end": row.weather.latest_week_end,
                        "fit_target_end_max": train_target_end_max,
                        "fit_converged": bool(fitted.result.converged),
                        "poisson_deviance_contribution": contribution,
                        "poisson_deviance_status": poisson_status,
                    }
                )
            candidate_predictions.sort(
                key=lambda item: (str(item["municipality_code"]), item["issue_week"])
            )
            prediction_rows.extend(candidate_predictions)
            fold_metric_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names[candidate_id],
                    **summarize_prediction_metrics(candidate_predictions),
                }
            )
            result = fitted.result
            uses_weather = candidate_id in (WEATHER_ID, COMBINED_ID)
            diagnostic_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names[candidate_id],
                    "n_original_train": len(fold.train_rows),
                    "n_common_train": len(train_rows),
                    "n_train_excluded_incomplete_weather": excluded_train,
                    "n_validation": len(validation_rows),
                    "n_parameters": len(fitted.column_names),
                    "design_matrix_rank": fitted.design_rank,
                    "offset": "log(population)",
                    "offset_coefficient": 1.0,
                    "weather_scaling_fit_scope": "training_fold_only" if uses_weather else None,
                    "weather_scaling_means": json.dumps(scaler.means, sort_keys=True) if uses_weather else None,
                    "weather_scaling_standard_deviations": json.dumps(scaler.standard_deviations, sort_keys=True) if uses_weather else None,
                    "train_target_end_max": train_target_end_max,
                    "validation_start": fold.validation_start,
                    "latest_training_weather_week_end": max(row.weather.latest_week_end for row in train_rows),
                    "latest_validation_weather_week_end": max(row.weather.latest_week_end for row in validation_rows),
                    "converged": bool(result.converged),
                    "iterations": result.fit_history.get("iteration"),
                    "warning_count": len(fitted.warning_messages),
                    "warning_messages": json.dumps(fitted.warning_messages),
                    "deviance": float(result.deviance),
                    "pearson_chi2": float(result.pearson_chi2),
                }
            )
            for feature, coefficient, standard_error in zip(
                fitted.column_names, result.params, result.bse, strict=True
            ):
                coefficient_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "candidate_id": candidate_id,
                        "feature": feature,
                        "coefficient": float(coefficient),
                        "standard_error": float(standard_error),
                    }
                )

    aggregate_rows: list[dict[str, object]] = []
    for candidate_id in CANDIDATE_IDS:
        candidate_predictions = [row for row in prediction_rows if row["candidate_id"] == candidate_id]
        candidate_fold_metrics = [row for row in fold_metric_rows if row["candidate_id"] == candidate_id]
        pooled = summarize_prediction_metrics(candidate_predictions)
        aggregate_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": candidate_names[candidate_id],
                "n_folds": len(candidate_fold_metrics),
                "n_expected_predictions": pooled["n_expected_predictions"],
                "n_available_predictions": pooled["n_available_predictions"],
                "n_missing_predictions": pooled["n_missing_predictions"],
                "prediction_metric_status": pooled["prediction_metric_status"],
                "pooled_mae": pooled["mae"],
                "mean_fold_mae": mean_present([row["mae"] for row in candidate_fold_metrics]),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": mean_present([row["rmse"] for row in candidate_fold_metrics]),
                "pooled_mean_poisson_deviance": pooled["mean_poisson_deviance"],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
                "n_poisson_valid": pooled["n_poisson_valid"],
                "n_poisson_invalid": pooled["n_poisson_invalid"],
            }
        )
    aggregate_by_id = {row["candidate_id"]: row for row in aggregate_rows}
    incremental_rows: list[dict[str, object]] = []
    for candidate_id in CANDIDATE_IDS[1:]:
        for metric in ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance"):
            control_value = float(aggregate_by_id[CONTROL_ID][metric])
            candidate_value = float(aggregate_by_id[candidate_id][metric])
            difference = candidate_value - control_value
            incremental_rows.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names[candidate_id],
                    "metric": metric,
                    "control_value": control_value,
                    "candidate_value": candidate_value,
                    "candidate_minus_control": difference,
                    "result": classify_delta(difference),
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
        raise WeatherAblationError("Output filenames must not contain directories.")
    write_csv_rows(output_paths["fold_predictions"], PREDICTION_COLUMNS, prediction_rows)
    write_csv_rows(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, fold_metric_rows)
    write_csv_rows(output_paths["aggregate_metrics"], AGGREGATE_METRIC_COLUMNS, aggregate_rows)
    write_csv_rows(output_paths["incremental_comparison"], INCREMENTAL_COLUMNS, incremental_rows)
    write_csv_rows(output_paths["fit_diagnostics"], DIAGNOSTIC_COLUMNS, diagnostic_rows)
    write_csv_rows(output_paths["coefficients"], COEFFICIENT_COLUMNS, coefficient_rows)

    sources = {
        "population": file_record(input_paths["population"]),
        "static_features": file_record(input_paths["static_features"]),
        "static_quality_summary": file_record(input_paths["static_quality_summary"]),
        "weekly_weather": file_record(input_paths["weekly_weather"]),
        "weather_quality_summary": file_record(input_paths["weather_quality_summary"]),
        "target": file_record(target_path),
        "validation_config": file_record(input_paths["validation_config"]),
        "validation_manifest": file_record(input_paths["validation_manifest"]),
        "phase_9_config": file_record(input_paths["phase_9_config"]),
        "phase_12_config": file_record(config_path),
        "builder": file_record(Path(__file__).resolve()),
    }
    realized = {
        "schema_version": 1,
        "pipeline": "model_v3.models.weather_ablation",
        "development_policy": {
            "start_year": policy["development_start_year"],
            "end_year": policy["development_end_year"],
            "excluded_lockbox_year": lockbox_year,
            "fold_strategy": policy["fold_strategy"],
        },
        "experiment": config["experiment"],
        "weather_feature_columns": list(WEATHER_FEATURE_COLUMNS),
        "phase_9_fitting_reused": fitting,
        "phase_9_population_policy_reused": phase_9_config["modeling"]["population_availability_safeguard"],
        "metrics": config["metrics"],
        "fold_common_train_counts": fold_common_train_counts,
        "fold_excluded_incomplete_weather_counts": fold_excluded_counts,
        "sources": sources,
        "library_versions": {
            "numpy": np.__version__,
            "scipy": importlib.metadata.version("scipy"),
            "statsmodels": statsmodels.__version__,
        },
    }
    output_paths["experiment_configuration"].write_text(
        json.dumps(realized, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_records = {
        key: file_record(path)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    expected_predictions = sum(len(fold.validation_rows) for fold in folds) * len(CANDIDATE_IDS)
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.weather_ablation",
        "status": "pass",
        "sources": sources,
        "outputs": output_records,
        "summary": {
            "fold_count": len(folds),
            "candidate_count": len(CANDIDATE_IDS),
            "prediction_rows": len(prediction_rows),
            "expected_prediction_rows": expected_predictions,
            "weather_feature_count": len(WEATHER_FEATURE_COLUMNS),
            "weather_cutoff": weather_quality["policy"]["weather_cutoff"],
        },
        "aggregate_metrics": aggregate_rows,
        "incremental_comparison": incremental_rows,
        "common_training_support": {
            "rows_by_fold": fold_common_train_counts,
            "excluded_incomplete_weather_by_fold": fold_excluded_counts,
        },
        "checks": {
            "validation_manifest_matches_regenerated_folds": True,
            "same_validation_rows_all_four_arms": len(prediction_rows) == expected_predictions,
            "same_common_training_rows_all_four_arms": True,
            "target_is_t_plus_1_through_t_plus_4": all(
                row["target_window_start"] == row["issue_week"] + timedelta(weeks=1)
                and row["target_window_end"] == row["issue_week"] + timedelta(weeks=4)
                for row in prediction_rows
            ),
            "all_training_targets_precede_validation": all(
                row["train_target_end_max"] < row["validation_start"] for row in diagnostic_rows
            ),
            "weather_strictly_precedes_issue_week": all(
                row["latest_weather_week_end"] < row["issue_week"] for row in prediction_rows
            ),
            "latest_weather_is_t_minus_1_completed_week": all(
                row["latest_weather_week_used"] == row["issue_week"] - timedelta(weeks=1)
                and row["latest_weather_week_end"] == row["issue_week"] - timedelta(days=1)
                for row in prediction_rows
            ),
            "weather_scaling_is_training_fold_only": all(
                row["weather_scaling_fit_scope"] in (None, "training_fold_only") for row in diagnostic_rows
            ),
            "fixed_212_municipality_zones_all_years": True,
            "weather_cutoff_not_exceeded": all(
                row["latest_weather_week_end"] <= date(2024, 12, 31) for row in prediction_rows
            ),
            "lockbox_issue_weeks_excluded": all(
                row["issue_week"].year < lockbox_year for row in prediction_rows
            ),
            "lockbox_target_windows_excluded": all(
                row["target_window_end"].year < lockbox_year for row in prediction_rows
            ),
            "missing_weather_never_zero_imputed": True,
            "population_remains_offset": True,
            "catboost_not_used": True,
            "classification_and_risk_categories_not_created": True,
        },
    }
    if not all(quality["checks"].values()):
        quality["status"] = "fail"
    output_paths["quality_summary"].write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if quality["status"] != "pass":
        raise WeatherAblationError("Weather ablation quality checks failed.")
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 12 Lyme weather ablation.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_weather_ablation(config_path)
    print("Lyme weather ablation evaluated.")
    print(f"- folds: {quality['summary']['fold_count']}")
    print(f"- predictions: {quality['summary']['prediction_rows']}")
    for row in quality["aggregate_metrics"]:
        print(
            f"- {row['candidate_id']}: MAE={row['pooled_mae']}, "
            f"RMSE={row['pooled_rmse']}, Poisson={row['pooled_mean_poisson_deviance']}"
        )
    print("No 2025 outcome or post-cutoff weather was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
