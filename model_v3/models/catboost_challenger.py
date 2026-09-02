from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
import statsmodels
import statsmodels.api as sm
from catboost import CatBoostRegressor, Pool

from model_v3.models.non_ml_baselines import (
    AGGREGATE_METRIC_COLUMNS as BASELINE_AGGREGATE_COLUMNS,
    BASELINE_IDS,
    FOLD_METRIC_COLUMNS as BASELINE_FOLD_COLUMNS,
    csv_value,
    file_record,
    poisson_deviance_contribution,
    read_development_weekly_cases,
    resolve_repo_path,
    summarize_prediction_metrics,
    validate_manifest_matches_folds,
    write_csv_rows,
)
from model_v3.models.seasonal_count_models import (
    AGGREGATE_METRIC_COLUMNS as STATISTICAL_AGGREGATE_COLUMNS,
    FOLD_METRIC_COLUMNS as STATISTICAL_FOLD_COLUMNS,
    MODEL_IDS,
    MODEL_S3,
    DesignSpec,
    ModelRow as Phase9ModelRow,
    PastIncidence,
    build_design_matrix as build_s3_design_matrix,
    load_config as load_statistical_config,
    make_design_spec,
    mean_present,
    prepare_model_rows,
    read_development_population,
    read_development_target_metadata,
    read_selected_development_target_values,
)
from model_v3.models.weather_ablation import (
    AGGREGATE_METRIC_COLUMNS as WEATHER_AGGREGATE_COLUMNS,
    CANDIDATE_IDS as WEATHER_CANDIDATE_IDS,
    IssueWeather,
    WEATHER_FEATURE_COLUMNS,
    WeatherScaler,
    fit_weather_scaler,
    issue_weather_features,
    read_weekly_weather,
)
from model_v3.validation.rolling_origin import (
    RollingOriginFold,
    generate_rolling_origin_folds,
    load_config as load_validation_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_catboost_challenger.json"
)

REFERENCE_ID = "model_s3_weather_offset_matched"
CHALLENGER_ID = "catboost_poisson_s3_weather_offset"
BASE_FEATURE_COLUMNS = (
    "municipality_code",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_4w_lyme_incidence_per_100000",
)
SCALED_WEATHER_COLUMNS = tuple(f"z_{name}" for name in WEATHER_FEATURE_COLUMNS)
FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + SCALED_WEATHER_COLUMNS
CATEGORICAL_FEATURES = ("municipality_code",)

PREDICTION_COLUMNS = (
    "fold_id",
    "system_type",
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
    "population_reference_date",
    "population_exposure_per_100000",
    "offset_log_population_per_100000",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_4w_lyme_cases",
    "past_4w_lyme_incidence_per_100000",
    "past_case_window_start",
    "past_case_window_end",
    "latest_past_case_week_used",
    "weather_window_start",
    "latest_weather_week_used",
    "latest_weather_week_end",
    "fit_target_end_max",
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

COMPARISON_COLUMNS = (
    "system_type",
    "candidate_id",
    "candidate_name",
    "training_support",
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

FOLD_DIFFERENCE_COLUMNS = (
    "fold_id",
    "validation_year",
    "n_validation",
    "reference_model_id",
    "reference_mae",
    "catboost_mae",
    "catboost_minus_reference_mae",
    "mae_result",
    "reference_rmse",
    "catboost_rmse",
    "catboost_minus_reference_rmse",
    "rmse_result",
    "reference_mean_poisson_deviance",
    "catboost_mean_poisson_deviance",
    "catboost_minus_reference_mean_poisson_deviance",
    "poisson_deviance_result",
)

STABILITY_COLUMNS = (
    "metric",
    "n_folds",
    "n_improved_folds",
    "n_no_change_folds",
    "n_deteriorated_folds",
    "proportion_improved_folds",
    "mean_fold_difference",
    "median_fold_difference",
    "minimum_fold_difference",
    "maximum_fold_difference",
    "aggregate_reference_value",
    "aggregate_catboost_value",
    "aggregate_catboost_minus_reference",
    "aggregate_relative_change_percent",
    "aggregate_result",
)

REFERENCE_DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "model_id",
    "n_original_train",
    "n_common_train",
    "n_train_excluded_incomplete_weather",
    "n_validation",
    "n_parameters",
    "design_matrix_rank",
    "municipality_reference",
    "municipality_levels",
    "offset",
    "population_as_ordinary_feature",
    "weather_scaling_fit_scope",
    "weather_scaling_means",
    "weather_scaling_standard_deviations",
    "train_target_end_max",
    "validation_start",
    "latest_training_case_information",
    "latest_validation_case_information",
    "latest_training_weather_week_end",
    "latest_validation_weather_week_end",
    "converged",
    "iterations",
    "warning_count",
    "warning_messages",
    "deviance",
    "pearson_chi2",
)

REFERENCE_COEFFICIENT_COLUMNS = (
    "fold_id",
    "model_id",
    "feature",
    "coefficient",
    "standard_error",
)

CHALLENGER_DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "challenger_id",
    "n_original_train",
    "n_common_train",
    "n_train_excluded_incomplete_weather",
    "n_validation",
    "train_issue_start",
    "train_issue_end",
    "train_target_end_max",
    "validation_start",
    "validation_end",
    "feature_columns",
    "categorical_features",
    "municipality_encoding",
    "municipality_categories_train",
    "municipality_categories_validation",
    "one_hot_max_size",
    "target_derived_ctr_allowed",
    "offset",
    "population_as_ordinary_feature",
    "weather_scaling_fit_scope",
    "weather_scaling_means",
    "weather_scaling_standard_deviations",
    "latest_training_case_information",
    "latest_validation_case_information",
    "latest_training_weather_week_end",
    "latest_validation_weather_week_end",
    "tree_count",
    "best_iteration",
    "random_seed",
    "validation_labels_passed_to_fit",
)

FEATURE_IMPORTANCE_COLUMNS = (
    "fold_id",
    "challenger_id",
    "feature",
    "feature_importance",
)


class CatBoostChallengerError(ValueError):
    """Raised when the Phase 13 matched challenger violates its contract."""


@dataclass(frozen=True)
class ChallengerRow:
    municipality_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_value: int
    population: int
    population_year: int
    seasonal_sin: float
    seasonal_cos: float
    past_incidence: PastIncidence
    weather: IssueWeather


@dataclass(frozen=True)
class FittedReference:
    result: Any
    design_spec: DesignSpec
    column_names: tuple[str, ...]
    design_rank: int
    warning_messages: tuple[str, ...]


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise CatBoostChallengerError("Phase 13 config must be inside repository.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 2:
        raise CatBoostChallengerError("Configuration schema_version must equal 2.")
    expected_inputs = {
        "population",
        "weekly_cases",
        "weekly_weather",
        "weather_quality_summary",
        "weather_contract",
        "validation_config",
        "validation_manifest",
        "baseline_fold_metrics",
        "baseline_aggregate_metrics",
        "statistical_config",
        "statistical_fold_metrics",
        "statistical_aggregate_metrics",
        "weather_ablation_aggregate_metrics",
    }
    if set(config.get("inputs", {})) != expected_inputs:
        raise CatBoostChallengerError("Phase 13 input keys are unexpected.")
    if any(
        not isinstance(value, str) or not value
        for value in config["inputs"].values()
    ):
        raise CatBoostChallengerError("Every Phase 13 input path is required.")

    reference = config.get("reference", {})
    if reference.get("model_id") != REFERENCE_ID:
        raise CatBoostChallengerError("Matched reference ID is unexpected.")
    if reference.get("target") != "target_lyme_cases_next_4w":
        raise CatBoostChallengerError("Matched reference target is unexpected.")
    if reference.get("target_window") != "t_plus_1_through_t_plus_4":
        raise CatBoostChallengerError("Matched reference target window is unexpected.")
    if reference.get("weather_features_allowed") is not True:
        raise CatBoostChallengerError("Weather must be included in the matched reference.")
    if reference.get("static_geography_allowed") is not False:
        raise CatBoostChallengerError("Static area must remain outside matched S3.")
    if reference.get("weather_scaling") != (
        "training_fold_mean_and_standard_deviation_only"
    ):
        raise CatBoostChallengerError("Weather scaling must be training-fold only.")

    challenger = config.get("challenger", {})
    if challenger.get("challenger_id") != CHALLENGER_ID:
        raise CatBoostChallengerError("Challenger ID is unexpected.")
    if challenger.get("loss_function") != "Poisson":
        raise CatBoostChallengerError("Challenger loss must be Poisson.")
    if challenger.get("feature_columns") != list(FEATURE_COLUMNS):
        raise CatBoostChallengerError("Challenger feature columns changed.")
    if challenger.get("categorical_features") != list(CATEGORICAL_FEATURES):
        raise CatBoostChallengerError("Categorical feature contract changed.")
    expected_parameters = {
        "iterations": 200,
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 3.0,
        "random_seed": 0,
        "random_strength": 1.0,
        "one_hot_max_size": 255,
        "thread_count": 1,
        "allow_writing_files": False,
        "task_type": "CPU",
        "verbose": False,
    }
    if challenger.get("parameters") != expected_parameters:
        raise CatBoostChallengerError("Conservative CatBoost parameters changed.")
    if challenger.get("validation_labels_passed_to_fit") is not False:
        raise CatBoostChallengerError("Validation labels must not be passed to fit.")

    expected_outputs = {
        "directory",
        "challenger_configuration",
        "reference_fold_predictions",
        "reference_fold_metrics",
        "reference_aggregate_metrics",
        "reference_fit_diagnostics",
        "reference_coefficients",
        "fold_predictions",
        "fold_metrics",
        "aggregate_metrics",
        "development_comparison",
        "fold_differences",
        "stability_summary",
        "fit_diagnostics",
        "feature_importance",
        "quality_summary",
    }
    if set(config.get("outputs", {})) != expected_outputs:
        raise CatBoostChallengerError("Phase 13 output keys are unexpected.")
    return config


def ordered_rows(rows: Sequence[ChallengerRow]) -> list[ChallengerRow]:
    return sorted(rows, key=lambda row: (row.issue_week, row.municipality_code))


def attach_weather(
    rows: Sequence[Phase9ModelRow],
    weekly_weather: Mapping[tuple[str, date], Any],
) -> tuple[list[ChallengerRow], int]:
    attached: list[ChallengerRow] = []
    excluded = 0
    for row in rows:
        weather = issue_weather_features(
            weekly_weather,
            municipality_code=row.municipality_code,
            issue_week=row.issue_week,
        )
        if weather is None:
            excluded += 1
            continue
        attached.append(
            ChallengerRow(
                municipality_code=row.municipality_code,
                issue_week=row.issue_week,
                target_window_start=row.target_window_start,
                target_window_end=row.target_window_end,
                target_value=row.target_value,
                population=row.population,
                population_year=row.population_year,
                seasonal_sin=row.seasonal_sin,
                seasonal_cos=row.seasonal_cos,
                past_incidence=row.past_incidence,
                weather=weather,
            )
        )
    return ordered_rows(attached), excluded


def validate_feature_availability(rows: Sequence[ChallengerRow]) -> None:
    if not rows:
        raise CatBoostChallengerError("Phase 13 feature rows are empty.")
    for row in rows:
        past = row.past_incidence
        if past.case_count is None or past.incidence_per_100000 is None:
            raise CatBoostChallengerError("Past incidence is missing.")
        if past.latest_information_week >= row.issue_week:
            raise CatBoostChallengerError("Past case information reaches issue time.")
        expected_incidence = past.case_count / row.population * 100000.0
        if not math.isclose(
            past.incidence_per_100000,
            expected_incidence,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise CatBoostChallengerError(
                "Past incidence denominator differs from population exposure."
            )
        if row.population_year >= row.issue_week.year:
            raise CatBoostChallengerError(
                "Population exposure year must precede issue year."
            )
        if row.weather.window_start != row.issue_week - timedelta(weeks=4):
            raise CatBoostChallengerError("Weather window does not start at t-4.")
        if row.weather.latest_week_start != row.issue_week - timedelta(weeks=1):
            raise CatBoostChallengerError("Latest weather week is not t-1.")
        if row.weather.latest_week_end >= row.issue_week:
            raise CatBoostChallengerError("Weather information reaches issue time.")
        if tuple(row.weather.values) != WEATHER_FEATURE_COLUMNS:
            raise CatBoostChallengerError("Weather feature order changed.")
        if not all(math.isfinite(value) for value in row.weather.values.values()):
            raise CatBoostChallengerError("Weather feature is non-finite.")


def standardized_weather_values(
    row: ChallengerRow, scaler: WeatherScaler
) -> tuple[float, ...]:
    values = tuple(
        (row.weather.values[name] - scaler.means[name])
        / scaler.standard_deviations[name]
        for name in WEATHER_FEATURE_COLUMNS
    )
    if not all(math.isfinite(value) for value in values):
        raise CatBoostChallengerError("Standardized weather is non-finite.")
    return values


def feature_matrix(
    rows: Sequence[ChallengerRow], scaler: WeatherScaler
) -> list[list[object]]:
    validate_feature_availability(rows)
    return [
        [
            row.municipality_code,
            row.seasonal_sin,
            row.seasonal_cos,
            row.past_incidence.incidence_per_100000,
            *standardized_weather_values(row, scaler),
        ]
        for row in rows
    ]


def exposure_baseline(rows: Sequence[ChallengerRow]) -> np.ndarray:
    values = np.asarray(
        [math.log(row.population / 100000.0) for row in rows], dtype=np.float64
    )
    if not np.isfinite(values).all():
        raise CatBoostChallengerError("Population exposure baseline is non-finite.")
    return values


def validate_municipality_one_hot_contract(
    train_rows: Sequence[ChallengerRow],
    validation_rows: Sequence[ChallengerRow],
    *,
    one_hot_max_size: int,
) -> tuple[int, int]:
    if isinstance(one_hot_max_size, bool) or not isinstance(one_hot_max_size, int):
        raise CatBoostChallengerError("one_hot_max_size must be an integer.")
    train_categories = {row.municipality_code for row in train_rows}
    validation_categories = {row.municipality_code for row in validation_rows}
    if len(train_categories) > one_hot_max_size:
        raise CatBoostChallengerError(
            "Municipality cardinality exceeds one_hot_max_size."
        )
    unseen = sorted(validation_categories - train_categories)
    if unseen:
        raise CatBoostChallengerError(
            f"Validation municipalities absent from training: {unseen}"
        )
    return len(train_categories), len(validation_categories)


def build_pool(
    rows: Sequence[ChallengerRow],
    scaler: WeatherScaler,
    *,
    include_labels: bool,
) -> Pool:
    ordered = ordered_rows(rows)
    labels = [row.target_value for row in ordered] if include_labels else None
    return Pool(
        data=feature_matrix(ordered, scaler),
        label=labels,
        cat_features=[FEATURE_COLUMNS.index("municipality_code")],
        feature_names=list(FEATURE_COLUMNS),
        baseline=exposure_baseline(ordered),
        timestamp=[row.issue_week.toordinal() for row in ordered],
    )


def build_reference_design(
    rows: Sequence[ChallengerRow],
    spec: DesignSpec,
    scaler: WeatherScaler,
) -> np.ndarray:
    base = build_s3_design_matrix(rows, spec)
    weather = np.asarray(
        [standardized_weather_values(row, scaler) for row in rows],
        dtype=np.float64,
    )
    design = np.column_stack((base, weather))
    if not np.isfinite(design).all():
        raise CatBoostChallengerError("Matched reference design is non-finite.")
    return design


def fit_reference(
    rows: Sequence[ChallengerRow],
    scaler: WeatherScaler,
    fitting: Mapping[str, object],
) -> FittedReference:
    spec = make_design_spec(MODEL_S3, rows)
    design = build_reference_design(rows, spec, scaler)
    column_names = spec.column_names + SCALED_WEATHER_COLUMNS
    if design.shape[1] != len(column_names):
        raise CatBoostChallengerError("Matched reference column count changed.")
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise CatBoostChallengerError(
            f"Matched reference is rank deficient: {rank}/{design.shape[1]}."
        )
    target = np.asarray([row.target_value for row in rows], dtype=np.float64)
    exposure = np.asarray(
        [row.population / 100000.0 for row in rows], dtype=np.float64
    )
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
        raise CatBoostChallengerError("Matched reference coefficients are invalid.")
    warning_messages = tuple(
        f"{type(item.message).__name__}: {item.message}" for item in caught
    )
    return FittedReference(result, spec, column_names, rank, warning_messages)


def predict_reference(
    fitted: FittedReference,
    rows: Sequence[ChallengerRow],
    scaler: WeatherScaler,
) -> np.ndarray:
    design = build_reference_design(rows, fitted.design_spec, scaler)
    exposure = np.asarray(
        [row.population / 100000.0 for row in rows], dtype=np.float64
    )
    predictions = np.asarray(
        fitted.result.predict(design, exposure=exposure), dtype=np.float64
    )
    if np.any(predictions <= 0) or not np.isfinite(predictions).all():
        raise CatBoostChallengerError("Matched reference predictions are invalid.")
    return predictions


def classify_difference(value: float) -> str:
    if not math.isfinite(value):
        raise CatBoostChallengerError("Metric difference must be finite.")
    return "improvement" if value < 0 else "deterioration" if value > 0 else "no_change"


def read_fold_metrics(
    path: Path,
    *,
    id_column: str,
    expected_ids: Sequence[str],
    expected_columns: Sequence[str],
    folds: Sequence[RollingOriginFold],
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(expected_columns):
            raise CatBoostChallengerError(f"Unexpected metric columns: {path}")
        rows = list(reader)
    expected = {
        (fold.fold_id, candidate_id): len(fold.validation_rows)
        for fold in folds
        for candidate_id in expected_ids
    }
    observed = {
        (row["fold_id"], row[id_column]): int(row["n_expected_predictions"])
        for row in rows
    }
    if observed != expected or len(observed) != len(rows):
        raise CatBoostChallengerError(f"Fold metrics do not match folds: {path}")
    return rows


def read_aggregate_metrics(
    path: Path,
    *,
    id_column: str,
    expected_ids: Sequence[str],
    expected_columns: Sequence[str],
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(expected_columns):
            raise CatBoostChallengerError(f"Unexpected aggregate columns: {path}")
        rows = list(reader)
    if [row[id_column] for row in rows] != list(expected_ids):
        raise CatBoostChallengerError(f"Unexpected aggregate IDs: {path}")
    return rows


def aggregate_metric_row(
    candidate_id: str,
    candidate_name: str,
    predictions: Sequence[Mapping[str, object]],
    fold_metrics: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    pooled = summarize_prediction_metrics(predictions)
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "n_folds": len(fold_metrics),
        "n_expected_predictions": pooled["n_expected_predictions"],
        "n_available_predictions": pooled["n_available_predictions"],
        "n_missing_predictions": pooled["n_missing_predictions"],
        "prediction_metric_status": pooled["prediction_metric_status"],
        "pooled_mae": pooled["mae"],
        "mean_fold_mae": mean_present([row["mae"] for row in fold_metrics]),
        "pooled_rmse": pooled["rmse"],
        "mean_fold_rmse": mean_present([row["rmse"] for row in fold_metrics]),
        "pooled_mean_poisson_deviance": pooled["mean_poisson_deviance"],
        "poisson_deviance_status": pooled["poisson_deviance_status"],
        "n_poisson_valid": pooled["n_poisson_valid"],
        "n_poisson_invalid": pooled["n_poisson_invalid"],
    }


def prediction_record(
    row: ChallengerRow,
    prediction: float,
    *,
    fold_id: str,
    system_type: str,
    candidate_id: str,
    candidate_name: str,
    fit_target_end_max: date,
    prediction_status: str,
) -> dict[str, object]:
    contribution, poisson_status = poisson_deviance_contribution(
        row.target_value, prediction
    )
    return {
        "fold_id": fold_id,
        "system_type": system_type,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "municipality_code": row.municipality_code,
        "issue_week": row.issue_week,
        "target_window_start": row.target_window_start,
        "target_window_end": row.target_window_end,
        "actual_target_lyme_cases_next_4w": row.target_value,
        "predicted_target_lyme_cases_next_4w": prediction,
        "prediction_status": prediction_status,
        "population_exposure": row.population,
        "population_year": row.population_year,
        "population_year_lag": row.issue_week.year - row.population_year,
        "population_reference_date": date(row.population_year, 1, 1),
        "population_exposure_per_100000": row.population / 100000.0,
        "offset_log_population_per_100000": math.log(row.population / 100000.0),
        "seasonal_sin_annual": row.seasonal_sin,
        "seasonal_cos_annual": row.seasonal_cos,
        "past_4w_lyme_cases": row.past_incidence.case_count,
        "past_4w_lyme_incidence_per_100000": (
            row.past_incidence.incidence_per_100000
        ),
        "past_case_window_start": row.past_incidence.window_start,
        "past_case_window_end": row.past_incidence.window_end,
        "latest_past_case_week_used": row.past_incidence.latest_information_week,
        "weather_window_start": row.weather.window_start,
        "latest_weather_week_used": row.weather.latest_week_start,
        "latest_weather_week_end": row.weather.latest_week_end,
        "fit_target_end_max": fit_target_end_max,
        "poisson_deviance_contribution": contribution,
        "poisson_deviance_status": poisson_status,
    }


def comparison_rows(
    baseline_rows: Sequence[Mapping[str, object]],
    statistical_rows: Sequence[Mapping[str, object]],
    weather_rows: Sequence[Mapping[str, object]],
    reference_row: Mapping[str, object],
    challenger_row: Mapping[str, object],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    groups = (
        (
            "epidemiological_baseline",
            baseline_rows,
            "baseline_id",
            "baseline_name",
            "original_phase_8_development_support",
        ),
        (
            "phase_9_statistical_model",
            statistical_rows,
            "model_id",
            "model_name",
            "original_phase_9_development_support",
        ),
        (
            "phase_12_weather_ablation",
            weather_rows,
            "candidate_id",
            "candidate_name",
            "common_complete_weather_training_support",
        ),
    )
    for system_type, rows, id_column, name_column, support in groups:
        for row in rows:
            output.append(
                {
                    "system_type": system_type,
                    "candidate_id": row[id_column],
                    "candidate_name": row[name_column],
                    "training_support": support,
                    **{
                        column: row[column]
                        for column in COMPARISON_COLUMNS
                        if column
                        not in {
                            "system_type",
                            "candidate_id",
                            "candidate_name",
                            "training_support",
                        }
                    },
                }
            )
    for system_type, row in (
        ("matched_statistical_reference", reference_row),
        ("ml_challenger", challenger_row),
    ):
        output.append(
            {
                "system_type": system_type,
                "candidate_id": row["candidate_id"],
                "candidate_name": row["candidate_name"],
                "training_support": "common_complete_weather_training_support",
                **{
                    column: row[column]
                    for column in COMPARISON_COLUMNS
                    if column
                    not in {
                        "system_type",
                        "candidate_id",
                        "candidate_name",
                        "training_support",
                    }
                },
            }
        )
    return output


def build_catboost_challenger(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {
        key: resolve_repo_path(value) for key, value in config["inputs"].items()
    }
    missing = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing:
        raise CatBoostChallengerError(f"Phase 13 inputs are missing: {missing}")

    weather_contract = json.loads(
        input_paths["weather_contract"].read_text(encoding="utf-8")
    )
    if weather_contract.get("status") != (
        "implemented_for_retrospective_development_through_verified_weather_cutoff"
    ):
        raise CatBoostChallengerError("Weather contract is not implemented.")
    gate_checks = weather_contract.get("gate_checks", {})
    if gate_checks.get("model_ablation_authorized") is not True:
        raise CatBoostChallengerError("Weather model ablation is not authorized.")
    if gate_checks.get("post_cutoff_operational_inference_authorized") is not False:
        raise CatBoostChallengerError("Post-cutoff inference must remain blocked.")

    statistical_config = load_statistical_config(input_paths["statistical_config"])
    if statistical_config["models"][-1]["model_id"] != MODEL_S3:
        raise CatBoostChallengerError("Phase 9 S3 definition changed.")
    fitting = statistical_config["modeling"]["fitting"]

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

    baseline_fold_metrics = read_fold_metrics(
        input_paths["baseline_fold_metrics"],
        id_column="baseline_id",
        expected_ids=BASELINE_IDS,
        expected_columns=BASELINE_FOLD_COLUMNS,
        folds=folds,
    )
    baseline_aggregate_metrics = read_aggregate_metrics(
        input_paths["baseline_aggregate_metrics"],
        id_column="baseline_id",
        expected_ids=BASELINE_IDS,
        expected_columns=BASELINE_AGGREGATE_COLUMNS,
    )
    statistical_fold_metrics = read_fold_metrics(
        input_paths["statistical_fold_metrics"],
        id_column="model_id",
        expected_ids=MODEL_IDS,
        expected_columns=STATISTICAL_FOLD_COLUMNS,
        folds=folds,
    )
    statistical_aggregate_metrics = read_aggregate_metrics(
        input_paths["statistical_aggregate_metrics"],
        id_column="model_id",
        expected_ids=MODEL_IDS,
        expected_columns=STATISTICAL_AGGREGATE_COLUMNS,
    )
    weather_aggregate_metrics = read_aggregate_metrics(
        input_paths["weather_ablation_aggregate_metrics"],
        id_column="candidate_id",
        expected_ids=WEATHER_CANDIDATE_IDS,
        expected_columns=WEATHER_AGGREGATE_COLUMNS,
    )

    selected_keys = {
        (row.municipality_code, row.issue_week)
        for fold in folds
        for row in fold.train_rows + fold.validation_rows
    }
    target_values = read_selected_development_target_values(
        target_path, selected_keys, lockbox_year=lockbox_year
    )
    population = read_development_population(
        input_paths["population"], lockbox_year=lockbox_year
    )
    weekly_cases = read_development_weekly_cases(
        input_paths["weekly_cases"], lockbox_year=lockbox_year
    )
    weekly_weather, weather_quality = read_weekly_weather(
        input_paths["weekly_weather"],
        input_paths["weather_quality_summary"],
        lockbox_year=lockbox_year,
    )
    if weather_quality.get("policy", {}).get(
        "fixed_analytical_zones_all_years"
    ) is not True:
        raise CatBoostChallengerError("Fixed municipality weather zones changed.")

    reference_name = config["reference"]["name"]
    challenger = config["challenger"]
    challenger_name = challenger["name"]
    reference_predictions: list[dict[str, object]] = []
    challenger_predictions: list[dict[str, object]] = []
    reference_fold_metrics: list[dict[str, object]] = []
    challenger_fold_metrics: list[dict[str, object]] = []
    reference_diagnostics: list[dict[str, object]] = []
    reference_coefficients: list[dict[str, object]] = []
    challenger_diagnostics: list[dict[str, object]] = []
    importance_rows: list[dict[str, object]] = []
    excluded_training_rows: dict[str, int] = {}

    for fold in folds:
        phase9_train = prepare_model_rows(
            fold.train_rows, target_values, population, weekly_cases
        )
        phase9_validation = prepare_model_rows(
            fold.validation_rows, target_values, population, weekly_cases
        )
        train_rows, excluded_train = attach_weather(phase9_train, weekly_weather)
        validation_rows, excluded_validation = attach_weather(
            phase9_validation, weekly_weather
        )
        if excluded_validation or len(validation_rows) != len(fold.validation_rows):
            raise CatBoostChallengerError(
                f"{fold.fold_id} validation weather support is incomplete."
            )
        excluded_training_rows[fold.fold_id] = excluded_train
        validate_feature_availability(train_rows)
        validate_feature_availability(validation_rows)
        scaler = fit_weather_scaler(train_rows)
        parameters = challenger["parameters"]
        n_train_municipalities, n_validation_municipalities = (
            validate_municipality_one_hot_contract(
                train_rows,
                validation_rows,
                one_hot_max_size=parameters["one_hot_max_size"],
            )
        )
        train_target_end_max = max(row.target_window_end for row in train_rows)
        if train_target_end_max >= fold.validation_start:
            raise CatBoostChallengerError("Training target reaches validation.")

        fitted_reference = fit_reference(train_rows, scaler, fitting)
        reference_values = predict_reference(
            fitted_reference, validation_rows, scaler
        )
        fold_reference_predictions = [
            prediction_record(
                row,
                float(prediction),
                fold_id=fold.fold_id,
                system_type="matched_statistical_reference",
                candidate_id=REFERENCE_ID,
                candidate_name=reference_name,
                fit_target_end_max=train_target_end_max,
                prediction_status=(
                    "available"
                    if bool(fitted_reference.result.converged)
                    else "available_fit_not_converged"
                ),
            )
            for row, prediction in zip(
                validation_rows, reference_values, strict=True
            )
        ]
        reference_predictions.extend(fold_reference_predictions)
        reference_fold_metrics.append(
            {
                "fold_id": fold.fold_id,
                "candidate_id": REFERENCE_ID,
                "candidate_name": reference_name,
                **summarize_prediction_metrics(fold_reference_predictions),
            }
        )
        reference_diagnostics.append(
            {
                "fold_id": fold.fold_id,
                "model_id": REFERENCE_ID,
                "n_original_train": len(fold.train_rows),
                "n_common_train": len(train_rows),
                "n_train_excluded_incomplete_weather": excluded_train,
                "n_validation": len(validation_rows),
                "n_parameters": len(fitted_reference.column_names),
                "design_matrix_rank": fitted_reference.design_rank,
                "municipality_reference": (
                    fitted_reference.design_spec.municipality_reference
                ),
                "municipality_levels": len(
                    fitted_reference.design_spec.municipality_levels
                ),
                "offset": "log(population_exposure_per_100000)",
                "population_as_ordinary_feature": False,
                "weather_scaling_fit_scope": "training_fold_only",
                "weather_scaling_means": json.dumps(
                    scaler.means, sort_keys=True
                ),
                "weather_scaling_standard_deviations": json.dumps(
                    scaler.standard_deviations, sort_keys=True
                ),
                "train_target_end_max": train_target_end_max,
                "validation_start": fold.validation_start,
                "latest_training_case_information": max(
                    row.past_incidence.latest_information_week for row in train_rows
                ),
                "latest_validation_case_information": max(
                    row.past_incidence.latest_information_week
                    for row in validation_rows
                ),
                "latest_training_weather_week_end": max(
                    row.weather.latest_week_end for row in train_rows
                ),
                "latest_validation_weather_week_end": max(
                    row.weather.latest_week_end for row in validation_rows
                ),
                "converged": bool(fitted_reference.result.converged),
                "iterations": fitted_reference.result.fit_history.get("iteration"),
                "warning_count": len(fitted_reference.warning_messages),
                "warning_messages": json.dumps(fitted_reference.warning_messages),
                "deviance": float(fitted_reference.result.deviance),
                "pearson_chi2": float(fitted_reference.result.pearson_chi2),
            }
        )
        for feature, coefficient, standard_error in zip(
            fitted_reference.column_names,
            fitted_reference.result.params,
            fitted_reference.result.bse,
            strict=True,
        ):
            reference_coefficients.append(
                {
                    "fold_id": fold.fold_id,
                    "model_id": REFERENCE_ID,
                    "feature": feature,
                    "coefficient": float(coefficient),
                    "standard_error": float(standard_error),
                }
            )

        train_pool = build_pool(train_rows, scaler, include_labels=True)
        validation_pool = build_pool(
            validation_rows, scaler, include_labels=False
        )
        model = CatBoostRegressor(
            loss_function=challenger["loss_function"],
            eval_metric=challenger["loss_function"],
            has_time=challenger["ordering"]["has_time"],
            **parameters,
        )
        model.fit(train_pool)
        catboost_values = np.asarray(
            model.predict(
                validation_pool,
                prediction_type=challenger["prediction_type"],
            ),
            dtype=np.float64,
        )
        if len(catboost_values) != len(validation_rows):
            raise CatBoostChallengerError("CatBoost prediction count changed.")
        if np.any(catboost_values <= 0) or not np.isfinite(catboost_values).all():
            raise CatBoostChallengerError("CatBoost predictions are invalid.")
        fold_challenger_predictions = [
            prediction_record(
                row,
                float(prediction),
                fold_id=fold.fold_id,
                system_type="ml_challenger",
                candidate_id=CHALLENGER_ID,
                candidate_name=challenger_name,
                fit_target_end_max=train_target_end_max,
                prediction_status="available",
            )
            for row, prediction in zip(
                validation_rows, catboost_values, strict=True
            )
        ]
        challenger_predictions.extend(fold_challenger_predictions)
        challenger_fold_metrics.append(
            {
                "fold_id": fold.fold_id,
                "candidate_id": CHALLENGER_ID,
                "candidate_name": challenger_name,
                **summarize_prediction_metrics(fold_challenger_predictions),
            }
        )
        challenger_diagnostics.append(
            {
                "fold_id": fold.fold_id,
                "challenger_id": CHALLENGER_ID,
                "n_original_train": len(fold.train_rows),
                "n_common_train": len(train_rows),
                "n_train_excluded_incomplete_weather": excluded_train,
                "n_validation": len(validation_rows),
                "train_issue_start": min(row.issue_week for row in train_rows),
                "train_issue_end": max(row.issue_week for row in train_rows),
                "train_target_end_max": train_target_end_max,
                "validation_start": fold.validation_start,
                "validation_end": fold.validation_end,
                "feature_columns": json.dumps(FEATURE_COLUMNS),
                "categorical_features": json.dumps(CATEGORICAL_FEATURES),
                "municipality_encoding": "catboost_internal_one_hot",
                "municipality_categories_train": n_train_municipalities,
                "municipality_categories_validation": n_validation_municipalities,
                "one_hot_max_size": parameters["one_hot_max_size"],
                "target_derived_ctr_allowed": False,
                "offset": "log(population_exposure_per_100000)",
                "population_as_ordinary_feature": False,
                "weather_scaling_fit_scope": "training_fold_only",
                "weather_scaling_means": json.dumps(
                    scaler.means, sort_keys=True
                ),
                "weather_scaling_standard_deviations": json.dumps(
                    scaler.standard_deviations, sort_keys=True
                ),
                "latest_training_case_information": max(
                    row.past_incidence.latest_information_week for row in train_rows
                ),
                "latest_validation_case_information": max(
                    row.past_incidence.latest_information_week
                    for row in validation_rows
                ),
                "latest_training_weather_week_end": max(
                    row.weather.latest_week_end for row in train_rows
                ),
                "latest_validation_weather_week_end": max(
                    row.weather.latest_week_end for row in validation_rows
                ),
                "tree_count": model.tree_count_,
                "best_iteration": model.get_best_iteration(),
                "random_seed": model.random_seed_,
                "validation_labels_passed_to_fit": False,
            }
        )
        importances = model.get_feature_importance(train_pool)
        for feature, importance in zip(FEATURE_COLUMNS, importances, strict=True):
            importance_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "challenger_id": CHALLENGER_ID,
                    "feature": feature,
                    "feature_importance": float(importance),
                }
            )

    reference_aggregate = aggregate_metric_row(
        REFERENCE_ID,
        reference_name,
        reference_predictions,
        reference_fold_metrics,
    )
    challenger_aggregate = aggregate_metric_row(
        CHALLENGER_ID,
        challenger_name,
        challenger_predictions,
        challenger_fold_metrics,
    )

    reference_by_fold = {row["fold_id"]: row for row in reference_fold_metrics}
    challenger_by_fold = {row["fold_id"]: row for row in challenger_fold_metrics}
    metric_names = ("mae", "rmse", "mean_poisson_deviance")
    differences_by_metric: dict[str, list[float]] = {
        metric: [] for metric in metric_names
    }
    fold_differences: list[dict[str, object]] = []
    for fold in folds:
        reference = reference_by_fold[fold.fold_id]
        challenger_row = challenger_by_fold[fold.fold_id]
        differences = {
            metric: float(challenger_row[metric]) - float(reference[metric])
            for metric in metric_names
        }
        for metric, difference in differences.items():
            differences_by_metric[metric].append(difference)
        fold_differences.append(
            {
                "fold_id": fold.fold_id,
                "validation_year": fold.validation_start.year,
                "n_validation": len(fold.validation_rows),
                "reference_model_id": REFERENCE_ID,
                "reference_mae": reference["mae"],
                "catboost_mae": challenger_row["mae"],
                "catboost_minus_reference_mae": differences["mae"],
                "mae_result": classify_difference(differences["mae"]),
                "reference_rmse": reference["rmse"],
                "catboost_rmse": challenger_row["rmse"],
                "catboost_minus_reference_rmse": differences["rmse"],
                "rmse_result": classify_difference(differences["rmse"]),
                "reference_mean_poisson_deviance": reference[
                    "mean_poisson_deviance"
                ],
                "catboost_mean_poisson_deviance": challenger_row[
                    "mean_poisson_deviance"
                ],
                "catboost_minus_reference_mean_poisson_deviance": differences[
                    "mean_poisson_deviance"
                ],
                "poisson_deviance_result": classify_difference(
                    differences["mean_poisson_deviance"]
                ),
            }
        )

    aggregate_metric_names = {
        "mae": "pooled_mae",
        "rmse": "pooled_rmse",
        "mean_poisson_deviance": "pooled_mean_poisson_deviance",
    }
    stability_rows: list[dict[str, object]] = []
    for metric, aggregate_metric in aggregate_metric_names.items():
        differences = differences_by_metric[metric]
        reference_value = float(reference_aggregate[aggregate_metric])
        challenger_value = float(challenger_aggregate[aggregate_metric])
        aggregate_difference = challenger_value - reference_value
        stability_rows.append(
            {
                "metric": metric,
                "n_folds": len(differences),
                "n_improved_folds": sum(value < 0 for value in differences),
                "n_no_change_folds": sum(value == 0 for value in differences),
                "n_deteriorated_folds": sum(value > 0 for value in differences),
                "proportion_improved_folds": (
                    sum(value < 0 for value in differences) / len(differences)
                ),
                "mean_fold_difference": statistics.fmean(differences),
                "median_fold_difference": statistics.median(differences),
                "minimum_fold_difference": min(differences),
                "maximum_fold_difference": max(differences),
                "aggregate_reference_value": reference_value,
                "aggregate_catboost_value": challenger_value,
                "aggregate_catboost_minus_reference": aggregate_difference,
                "aggregate_relative_change_percent": (
                    aggregate_difference / reference_value * 100.0
                ),
                "aggregate_result": classify_difference(aggregate_difference),
            }
        )

    development_comparison = comparison_rows(
        baseline_aggregate_metrics,
        statistical_aggregate_metrics,
        weather_aggregate_metrics,
        reference_aggregate,
        challenger_aggregate,
    )

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key != "directory"
    }
    if any(path.parent != output_directory for path in output_paths.values()):
        raise CatBoostChallengerError("Output filenames must not contain paths.")
    write_csv_rows(
        output_paths["reference_fold_predictions"],
        PREDICTION_COLUMNS,
        reference_predictions,
    )
    write_csv_rows(
        output_paths["reference_fold_metrics"],
        FOLD_METRIC_COLUMNS,
        reference_fold_metrics,
    )
    write_csv_rows(
        output_paths["reference_aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        [reference_aggregate],
    )
    write_csv_rows(
        output_paths["reference_fit_diagnostics"],
        REFERENCE_DIAGNOSTIC_COLUMNS,
        reference_diagnostics,
    )
    write_csv_rows(
        output_paths["reference_coefficients"],
        REFERENCE_COEFFICIENT_COLUMNS,
        reference_coefficients,
    )
    write_csv_rows(
        output_paths["fold_predictions"],
        PREDICTION_COLUMNS,
        challenger_predictions,
    )
    write_csv_rows(
        output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, challenger_fold_metrics
    )
    write_csv_rows(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        [challenger_aggregate],
    )
    write_csv_rows(
        output_paths["development_comparison"],
        COMPARISON_COLUMNS,
        development_comparison,
    )
    write_csv_rows(
        output_paths["fold_differences"],
        FOLD_DIFFERENCE_COLUMNS,
        fold_differences,
    )
    write_csv_rows(
        output_paths["stability_summary"], STABILITY_COLUMNS, stability_rows
    )
    write_csv_rows(
        output_paths["fit_diagnostics"],
        CHALLENGER_DIAGNOSTIC_COLUMNS,
        challenger_diagnostics,
    )
    write_csv_rows(
        output_paths["feature_importance"],
        FEATURE_IMPORTANCE_COLUMNS,
        importance_rows,
    )

    source_records = {
        **{key: file_record(path) for key, path in input_paths.items()},
        "target": file_record(target_path),
        "phase_13_config": file_record(config_path),
        "builder": file_record(Path(__file__).resolve()),
    }
    realized_configuration = {
        "schema_version": 2,
        "pipeline": "model_v3.models.catboost_challenger",
        "library_versions": {
            "catboost": catboost.__version__,
            "numpy": np.__version__,
            "statsmodels": statsmodels.__version__,
        },
        "development_policy": {
            "start_year": policy["development_start_year"],
            "end_year": policy["development_end_year"],
            "excluded_lockbox_year": lockbox_year,
            "fold_strategy": policy["fold_strategy"],
        },
        "feature_columns": list(FEATURE_COLUMNS),
        "weather_feature_columns": list(WEATHER_FEATURE_COLUMNS),
        "reference": config["reference"],
        "challenger": challenger,
        "metrics": config["metrics"],
        "decision": config["decision"],
        "excluded_training_rows_incomplete_weather": excluded_training_rows,
        "folds": [
            {key: csv_value(value) for key, value in fold.manifest_record().items()}
            for fold in folds
        ],
        "sources": source_records,
    }
    output_paths["challenger_configuration"].write_text(
        json.dumps(
            realized_configuration,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    expected_predictions = sum(len(fold.validation_rows) for fold in folds)
    reference_keys = [
        (row["fold_id"], row["municipality_code"], row["issue_week"])
        for row in reference_predictions
    ]
    challenger_keys = [
        (row["fold_id"], row["municipality_code"], row["issue_week"])
        for row in challenger_predictions
    ]
    output_records = {
        key: file_record(path)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    aggregate_all_improved = all(
        row["aggregate_result"] == "improvement" for row in stability_rows
    )
    every_metric_improves_in_every_fold = all(
        row["n_improved_folds"] == row["n_folds"] for row in stability_rows
    )
    checks = {
        "validation_manifest_matches_regenerated_folds": True,
        "baseline_metrics_match_same_folds": bool(baseline_fold_metrics),
        "phase_9_metrics_match_same_folds": bool(statistical_fold_metrics),
        "same_rows_reference_and_challenger": reference_keys == challenger_keys,
        "reference_prediction_count_matches_folds": (
            len(reference_predictions) == expected_predictions
        ),
        "challenger_prediction_count_matches_folds": (
            len(challenger_predictions) == expected_predictions
        ),
        "matched_training_support": all(
            reference_diagnostics[index]["n_common_train"]
            == challenger_diagnostics[index]["n_common_train"]
            for index in range(len(folds))
        ),
        "matched_training_fold_weather_scaling": all(
            reference_diagnostics[index]["weather_scaling_means"]
            == challenger_diagnostics[index]["weather_scaling_means"]
            and reference_diagnostics[index]["weather_scaling_standard_deviations"]
            == challenger_diagnostics[index][
                "weather_scaling_standard_deviations"
            ]
            for index in range(len(folds))
        ),
        "weather_features_included": all(
            column in FEATURE_COLUMNS for column in SCALED_WEATHER_COLUMNS
        ),
        "weather_strictly_precedes_issue_week": all(
            row["latest_weather_week_end"] < row["issue_week"]
            for row in challenger_predictions
        ),
        "past_cases_strictly_precede_issue_week": all(
            row["latest_past_case_week_used"] < row["issue_week"]
            for row in challenger_predictions
        ),
        "target_is_exactly_t_plus_1_through_t_plus_4": all(
            row["target_window_start"] == row["issue_week"] + timedelta(weeks=1)
            and row["target_window_end"] == row["issue_week"] + timedelta(weeks=4)
            for row in challenger_predictions
        ),
        "all_fit_targets_precede_validation": all(
            row["train_target_end_max"] < row["validation_start"]
            for row in challenger_diagnostics
        ),
        "population_year_precedes_issue_year": all(
            row["population_year"] < row["issue_week"].year
            for row in challenger_predictions
        ),
        "population_is_offset_not_feature": (
            "population" not in FEATURE_COLUMNS
            and "population_exposure" not in FEATURE_COLUMNS
        ),
        "municipality_one_hot_without_target_ctr": all(
            row["municipality_categories_train"] <= row["one_hot_max_size"]
            and row["target_derived_ctr_allowed"] is False
            for row in challenger_diagnostics
        ),
        "validation_labels_excluded_from_fit": all(
            row["validation_labels_passed_to_fit"] is False
            for row in challenger_diagnostics
        ),
        "matched_reference_converged": all(
            row["converged"] is True for row in reference_diagnostics
        ),
        "single_configuration_no_search": True,
        "static_area_excluded_from_both_matched_models": (
            "municipality_area_km2" not in FEATURE_COLUMNS
            and all(
                "municipality_area_km2" not in row["feature_columns"]
                for row in challenger_diagnostics
            )
        ),
        "classification_metrics_excluded": True,
        "risk_categories_not_created": True,
        "personal_risk_not_computed": True,
        "generated_predictions_not_features": True,
        "legacy_inputs_excluded": True,
        "lockbox_issue_weeks_excluded": all(
            row["issue_week"].year < lockbox_year for row in challenger_predictions
        ),
        "lockbox_target_windows_excluded": all(
            row["target_window_end"].year < lockbox_year
            for row in challenger_predictions
        ),
        "lockbox_performance_not_computed": True,
    }
    quality: dict[str, object] = {
        "schema_version": 2,
        "pipeline": "model_v3.models.catboost_challenger",
        "status": "pass" if all(checks.values()) else "fail",
        "sources": source_records,
        "outputs": output_records,
        "summary": {
            "fold_count": len(folds),
            "reference_prediction_rows": len(reference_predictions),
            "challenger_prediction_rows": len(challenger_predictions),
            "expected_prediction_rows_per_model": expected_predictions,
            "reference_fit_count": len(reference_diagnostics),
            "challenger_fit_count": len(challenger_diagnostics),
            "allowed_feature_count": len(FEATURE_COLUMNS),
            "weather_feature_count": len(SCALED_WEATHER_COLUMNS),
            "aggregate_all_metrics_improved": aggregate_all_improved,
            "every_metric_improves_in_every_fold": (
                every_metric_improves_in_every_fold
            ),
        },
        "checks": checks,
        "reference_aggregate_metrics": {
            key: csv_value(value) for key, value in reference_aggregate.items()
        },
        "challenger_aggregate_metrics": {
            key: csv_value(value) for key, value in challenger_aggregate.items()
        },
        "stability": [
            {key: csv_value(value) for key, value in row.items()}
            for row in stability_rows
        ],
        "decision": {
            "materiality_threshold": "not_prespecified",
            "automatic_promotion": False,
            "promotion_status": "not_promoted_challenger_only",
            "aggregate_all_metrics_improved": aggregate_all_improved,
            "every_metric_improves_in_every_fold": (
                every_metric_improves_in_every_fold
            ),
        },
    }
    output_paths["quality_summary"].write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if quality["status"] != "pass":
        raise CatBoostChallengerError("Phase 13 quality checks failed.")
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the matched weather-aware CatBoost challenger."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    quality = build_catboost_challenger(args.config)
    reference = quality["reference_aggregate_metrics"]
    challenger = quality["challenger_aggregate_metrics"]
    print("Weather-aware matched Phase 13 evaluated.")
    print(f"- folds: {quality['summary']['fold_count']}")
    print(f"- features: {quality['summary']['allowed_feature_count']}")
    print(
        "- matched statistical reference: "
        f"MAE={reference['pooled_mae']}, RMSE={reference['pooled_rmse']}, "
        f"Poisson={reference['pooled_mean_poisson_deviance']}"
    )
    print(
        "- CatBoost challenger: "
        f"MAE={challenger['pooled_mae']}, RMSE={challenger['pooled_rmse']}, "
        f"Poisson={challenger['pooled_mean_poisson_deviance']}"
    )
    for row in quality["stability"]:
        print(
            f"- {row['metric']}: {row['aggregate_result']}; "
            f"improved folds {row['n_improved_folds']}/{row['n_folds']}"
        )
    print("CatBoost remains an unpromoted challenger; 2025 was not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
