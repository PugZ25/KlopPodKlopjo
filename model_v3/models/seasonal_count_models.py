from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm
from scipy.stats import poisson

from model_v3.models.non_ml_baselines import (
    BASELINE_IDS,
    csv_value,
    file_record,
    parse_code,
    parse_monday,
    parse_nonnegative_integer,
    poisson_deviance_contribution,
    read_development_weekly_cases,
    resolve_repo_path,
    summarize_prediction_metrics,
    validate_manifest_matches_folds,
    write_csv_rows,
)
from model_v3.validation.rolling_origin import (
    RollingOriginFold,
    TargetWindowRow,
    generate_rolling_origin_folds,
    load_config as load_validation_config,
    normalize_target_metadata_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_seasonal_count_models.json"
)

MODEL_S1 = "model_s1_seasonality_offset"
MODEL_S2 = "model_s2_seasonality_municipality_offset"
MODEL_S3 = "model_s3_seasonality_municipality_past_incidence_offset"
MODEL_IDS = (MODEL_S1, MODEL_S2, MODEL_S3)

PREDICTION_COLUMNS = (
    "fold_id",
    "model_id",
    "model_name",
    "municipality_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_lyme_cases_next_4w",
    "predicted_target_lyme_cases_next_4w",
    "expected_mean_ci_lower_95",
    "expected_mean_ci_upper_95",
    "expected_mean_ci_status",
    "conditional_poisson_prediction_lower_95",
    "conditional_poisson_prediction_upper_95",
    "prediction_status",
    "population_exposure",
    "population_year",
    "population_year_lag",
    "population_reference_date",
    "offset_log_population",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_4w_lyme_cases",
    "past_4w_lyme_incidence_per_100000",
    "past_case_window_start",
    "past_case_window_end",
    "latest_past_case_week_used",
    "fit_target_end_max",
    "fit_converged",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)

FOLD_METRIC_COLUMNS = (
    "fold_id",
    "model_id",
    "model_name",
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
    "model_id",
    "model_name",
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

FIT_DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "model_id",
    "model_name",
    "formula",
    "family",
    "link",
    "fit_method",
    "n_train_fold_rows",
    "n_train_used",
    "n_train_feature_missing",
    "n_validation_fold_rows",
    "n_validation_available",
    "n_parameters",
    "design_matrix_rank",
    "municipality_reference",
    "n_municipality_levels",
    "offset",
    "offset_coefficient",
    "population_exposure_min",
    "population_exposure_max",
    "population_year_lag_min",
    "population_year_lag_max",
    "train_target_end_max",
    "validation_start",
    "converged",
    "iterations",
    "warning_count",
    "warning_messages",
    "deviance",
    "pearson_chi2",
)

COEFFICIENT_COLUMNS = (
    "fold_id",
    "model_id",
    "feature",
    "coefficient",
    "standard_error",
)


class SeasonalCountModelError(ValueError):
    """Raised when Phase 9 inputs or statistical outputs violate the contract."""


@dataclass(frozen=True)
class PastIncidence:
    case_count: int | None
    incidence_per_100000: float | None
    status: str
    window_start: date
    window_end: date
    latest_information_week: date


@dataclass(frozen=True)
class PopulationExposure:
    population: int
    year: int


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
    past_incidence: PastIncidence


@dataclass(frozen=True)
class DesignSpec:
    model_id: str
    column_names: tuple[str, ...]
    municipality_levels: tuple[str, ...]
    municipality_reference: str | None


@dataclass(frozen=True)
class FittedPoissonModel:
    result: Any
    design_spec: DesignSpec
    design_rank: int
    warning_messages: tuple[str, ...]


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise SeasonalCountModelError(
            f"Seasonal count configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise SeasonalCountModelError("Configuration schema_version must equal 1.")

    inputs = config.get("inputs")
    modeling = config.get("modeling")
    models = config.get("models")
    metrics = config.get("metrics")
    outputs = config.get("outputs")
    if not all(isinstance(value, dict) for value in (inputs, modeling, metrics, outputs)):
        raise SeasonalCountModelError(
            "Configuration inputs, modeling, metrics and outputs are required."
        )
    if not isinstance(models, list):
        raise SeasonalCountModelError("Configuration models must be a list.")

    expected_input_keys = {
        "population",
        "weekly_cases",
        "validation_config",
        "validation_manifest",
        "baseline_fold_metrics",
        "baseline_aggregate_metrics",
    }
    if set(inputs) != expected_input_keys:
        raise SeasonalCountModelError("Input keys do not match the Phase 9 contract.")
    if any(not isinstance(value, str) or not value for value in inputs.values()):
        raise SeasonalCountModelError("Every configured input must be a non-empty path.")

    required_modeling = {
        "family",
        "link",
        "exposure_column",
        "offset_definition",
        "population_measure",
        "population_year_rule",
        "population_publication_availability",
        "population_availability_safeguard",
        "seasonality",
        "municipality",
        "past_epidemiology",
        "long_term_trend",
        "fitting",
        "intervals",
    }
    if set(modeling) != required_modeling:
        raise SeasonalCountModelError("Modeling keys do not match the Phase 9 contract.")
    expected_scalars = {
        "family": "poisson",
        "link": "log",
        "exposure_column": "population",
        "offset_definition": "log(population)",
        "population_measure": "Population - Total - 1 January",
        "population_year_rule": "latest_present_year_strictly_before_issue_year",
        "population_publication_availability": "exact_timestamps_unavailable",
    }
    for key, expected in expected_scalars.items():
        if modeling.get(key) != expected:
            raise SeasonalCountModelError(f"Modeling {key} must equal {expected!r}.")

    population_safeguard = modeling["population_availability_safeguard"]
    if population_safeguard != {
        "preferred_year": "issue_year_minus_1",
        "missing_preferred_year_rule": "use_latest_present_earlier_year",
        "issue_or_future_year_allowed": False,
        "exact_available_at_timestamps_required": False,
        "interpretation": (
            "conservative_leakage_prevention_proxy_not_verified_publication_timing"
        ),
    }:
        raise SeasonalCountModelError(
            "Population availability safeguard configuration is not supported."
        )

    seasonality = modeling["seasonality"]
    if seasonality != {
        "representation": "one_annual_harmonic_from_issue_week_date",
        "columns": ["seasonal_sin_annual", "seasonal_cos_annual"],
        "phase_definition": "2*pi*zero_based_day_of_year/days_in_issue_year",
    }:
        raise SeasonalCountModelError("Seasonality configuration is not supported.")
    municipality = modeling["municipality"]
    if municipality != {
        "representation": "treatment_coded_fixed_effect",
        "reference_rule": "lexicographically_first_training_municipality_code",
        "unseen_validation_municipality_rule": "prediction_missing",
    }:
        raise SeasonalCountModelError("Municipality configuration is not supported.")
    past = modeling["past_epidemiology"]
    if past != {
        "column": "past_4w_lyme_incidence_per_100000",
        "case_weeks": [4, 3, 2, 1],
        "latest_information_week": "t_minus_1",
        "denominator": "same_population_exposure_as_model_offset",
        "missing_prior_week_rule": "feature_missing",
    }:
        raise SeasonalCountModelError("Past epidemiology configuration is not supported.")
    trend = modeling["long_term_trend"]
    if trend.get("included") is not False or not isinstance(trend.get("reason"), str):
        raise SeasonalCountModelError("Long-term trend must remain explicitly excluded.")
    fitting = modeling["fitting"]
    if fitting != {
        "implementation": "statsmodels.genmod.generalized_linear_model.GLM",
        "method": "IRLS",
        "maxiter": 100,
        "tol": 1e-08,
        "cov_type": "nonrobust",
    }:
        raise SeasonalCountModelError("Fitting configuration is not supported.")
    intervals = modeling["intervals"]
    if intervals != {
        "mean_confidence_level": 0.95,
        "conditional_poisson_predictive_level": 0.95,
        "conditional_predictive_interval_parameter_uncertainty": "not_included",
    }:
        raise SeasonalCountModelError("Interval configuration is not supported.")

    observed_ids = [definition.get("model_id") for definition in models]
    if observed_ids != list(MODEL_IDS):
        raise SeasonalCountModelError(
            f"Model IDs must equal {list(MODEL_IDS)} in order."
        )
    for definition in models:
        if not isinstance(definition.get("name"), str) or not definition["name"]:
            raise SeasonalCountModelError("Every model requires a name.")
        if not isinstance(definition.get("design_columns"), list):
            raise SeasonalCountModelError("Every model requires design_columns.")

    if metrics != {
        "mae": "mean_absolute_error",
        "rmse": "root_mean_squared_error",
        "poisson_deviance": (
            "mean_poisson_deviance_only_when_all_prediction_observation_pairs_are_mathematically_valid"
        ),
    }:
        raise SeasonalCountModelError("Metric configuration is not supported.")

    expected_output_keys = {
        "directory",
        "model_configuration",
        "fold_predictions",
        "fold_metrics",
        "aggregate_metrics",
        "development_comparison",
        "fit_diagnostics",
        "coefficients",
        "quality_summary",
    }
    if set(outputs) != expected_output_keys:
        raise SeasonalCountModelError("Output keys do not match the Phase 9 contract.")
    if any(not isinstance(value, str) or not value for value in outputs.values()):
        raise SeasonalCountModelError("Every configured output must be non-empty.")
    return config


def read_development_target_metadata(
    path: Path, *, development_start_year: int, development_end_year: int
) -> list[TargetWindowRow]:
    required = {
        "municipality_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "target_status",
        "target_training_eligible",
    }
    selected: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SeasonalCountModelError(
                f"Lyme target metadata is missing columns: {missing}"
            )
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"target row {row_index} issue_week"
            )
            if not development_start_year <= issue_week.year <= development_end_year:
                continue
            selected.append({column: row[column] for column in required})
    return normalize_target_metadata_rows(selected)


def read_selected_development_target_values(
    path: Path,
    selected_keys: set[tuple[str, date]],
    *,
    lockbox_year: int,
) -> dict[tuple[str, date], int]:
    required = {
        "municipality_code",
        "issue_week",
        "target_lyme_cases_next_4w",
    }
    values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SeasonalCountModelError(f"Lyme target is missing columns: {missing}")
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"target row {row_index} issue_week"
            )
            if issue_week.year >= lockbox_year:
                continue
            code = parse_code(
                row["municipality_code"], context=f"target row {row_index} code"
            )
            key = (code, issue_week)
            if key not in selected_keys:
                continue
            if key in values:
                raise SeasonalCountModelError(f"Duplicate selected target key: {key}")
            values[key] = parse_nonnegative_integer(
                row["target_lyme_cases_next_4w"],
                context=f"target[{code}, {issue_week}] value",
            )
    missing_keys = sorted(selected_keys - set(values))
    if missing_keys:
        raise SeasonalCountModelError(
            f"Selected development targets are missing: {missing_keys[:20]}"
        )
    return values


def read_development_population(
    path: Path, *, lockbox_year: int
) -> dict[tuple[str, int], int]:
    required = {"municipality_code", "year", "population"}
    values: dict[tuple[str, int], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SeasonalCountModelError(
                f"Canonical population is missing columns: {missing}"
            )
        for row_index, row in enumerate(reader, start=1):
            year = parse_nonnegative_integer(
                row["year"], context=f"population row {row_index} year"
            )
            if year >= lockbox_year:
                continue
            code = parse_code(
                row["municipality_code"],
                context=f"population row {row_index} code",
            )
            raw_population = row["population"]
            if raw_population is None or not str(raw_population).strip():
                continue
            population = parse_nonnegative_integer(
                raw_population, context=f"population[{code}, {year}]"
            )
            if population <= 0:
                raise SeasonalCountModelError(
                    f"Population exposure must be positive for {code}, {year}."
                )
            key = (code, year)
            if key in values:
                raise SeasonalCountModelError(f"Duplicate population key: {key}")
            values[key] = population
    if not values:
        raise SeasonalCountModelError("Development population input is empty.")
    return values


def build_population_history(
    population_by_key: Mapping[tuple[str, int], int],
) -> dict[str, tuple[PopulationExposure, ...]]:
    history: dict[str, list[PopulationExposure]] = {}
    for (municipality_code, population_year), population in population_by_key.items():
        if (
            isinstance(population_year, bool)
            or not isinstance(population_year, int)
            or isinstance(population, bool)
            or not isinstance(population, int)
            or population <= 0
        ):
            raise SeasonalCountModelError(
                "Population history requires integer years and positive integer values."
            )
        history.setdefault(municipality_code, []).append(
            PopulationExposure(population=population, year=population_year)
        )
    return {
        municipality_code: tuple(sorted(values, key=lambda value: value.year))
        for municipality_code, values in history.items()
    }


def select_population_exposure(
    population_history: Mapping[str, Sequence[PopulationExposure]],
    *,
    municipality_code: str,
    issue_week: date,
) -> PopulationExposure:
    latest_allowed_year = issue_week.year - 1
    eligible = [
        value
        for value in population_history.get(municipality_code, ())
        if value.year <= latest_allowed_year
    ]
    if not eligible:
        raise SeasonalCountModelError(
            "No present population value strictly before the issue year for "
            f"{municipality_code}, {issue_week.isoformat()}."
        )
    selected = max(eligible, key=lambda value: value.year)
    if selected.year >= issue_week.year:
        raise SeasonalCountModelError(
            "Selected population year must be strictly earlier than the issue year."
        )
    return selected


def seasonal_terms(issue_week: date) -> tuple[float, float]:
    year_start = date(issue_week.year, 1, 1)
    next_year_start = date(issue_week.year + 1, 1, 1)
    zero_based_day = (issue_week - year_start).days
    days_in_year = (next_year_start - year_start).days
    phase = 2.0 * math.pi * zero_based_day / days_in_year
    return math.sin(phase), math.cos(phase)


def calculate_past_incidence(
    weekly_cases: Mapping[tuple[str, date], int],
    *,
    municipality_code: str,
    issue_week: date,
    population: int,
    prior_week_offsets: Sequence[int] = (4, 3, 2, 1),
) -> PastIncidence:
    if tuple(prior_week_offsets) != (4, 3, 2, 1):
        raise SeasonalCountModelError(
            "Past incidence requires exactly offsets (4, 3, 2, 1)."
        )
    if isinstance(population, bool) or not isinstance(population, int) or population <= 0:
        raise SeasonalCountModelError("Past incidence requires positive population.")
    required_weeks = [
        issue_week - timedelta(weeks=offset) for offset in prior_week_offsets
    ]
    missing_weeks = [
        week
        for week in required_weeks
        if (municipality_code, week) not in weekly_cases
    ]
    if missing_weeks:
        return PastIncidence(
            case_count=None,
            incidence_per_100000=None,
            status="missing_prior_week",
            window_start=required_weeks[0],
            window_end=required_weeks[-1],
            latest_information_week=required_weeks[-1],
        )
    case_count = sum(weekly_cases[(municipality_code, week)] for week in required_weeks)
    return PastIncidence(
        case_count=case_count,
        incidence_per_100000=case_count / population * 100000.0,
        status="available",
        window_start=required_weeks[0],
        window_end=required_weeks[-1],
        latest_information_week=required_weeks[-1],
    )


def prepare_model_rows(
    rows: Sequence[TargetWindowRow],
    target_values: Mapping[tuple[str, date], int],
    population_by_key: Mapping[tuple[str, int], int],
    weekly_cases: Mapping[tuple[str, date], int],
) -> list[ModelRow]:
    prepared: list[ModelRow] = []
    population_history = build_population_history(population_by_key)
    for row in rows:
        key = (row.municipality_code, row.issue_week)
        if key not in target_values:
            raise SeasonalCountModelError(f"Target value is missing for {key}.")
        population_exposure = select_population_exposure(
            population_history,
            municipality_code=row.municipality_code,
            issue_week=row.issue_week,
        )
        population = population_exposure.population
        seasonal_sin, seasonal_cos = seasonal_terms(row.issue_week)
        prepared.append(
            ModelRow(
                municipality_code=row.municipality_code,
                issue_week=row.issue_week,
                target_window_start=row.target_window_start,
                target_window_end=row.target_window_end,
                target_value=target_values[key],
                population=population,
                population_year=population_exposure.year,
                seasonal_sin=seasonal_sin,
                seasonal_cos=seasonal_cos,
                past_incidence=calculate_past_incidence(
                    weekly_cases,
                    municipality_code=row.municipality_code,
                    issue_week=row.issue_week,
                    population=population,
                ),
            )
        )
    return prepared


def make_design_spec(model_id: str, training_rows: Sequence[ModelRow]) -> DesignSpec:
    if model_id not in MODEL_IDS:
        raise SeasonalCountModelError(f"Unknown model ID: {model_id}")
    base_columns = ["intercept", "seasonal_sin_annual", "seasonal_cos_annual"]
    municipality_levels: tuple[str, ...] = ()
    municipality_reference: str | None = None
    if model_id in (MODEL_S2, MODEL_S3):
        municipality_levels = tuple(
            sorted({row.municipality_code for row in training_rows})
        )
        if not municipality_levels:
            raise SeasonalCountModelError("Municipality model has no training levels.")
        municipality_reference = municipality_levels[0]
        base_columns.extend(
            f"municipality[{code}]" for code in municipality_levels[1:]
        )
    if model_id == MODEL_S3:
        base_columns.append("past_4w_lyme_incidence_per_100000")
    return DesignSpec(
        model_id=model_id,
        column_names=tuple(base_columns),
        municipality_levels=municipality_levels,
        municipality_reference=municipality_reference,
    )


def row_is_design_available(row: ModelRow, spec: DesignSpec) -> bool:
    if spec.municipality_levels and row.municipality_code not in spec.municipality_levels:
        return False
    if spec.model_id == MODEL_S3 and row.past_incidence.incidence_per_100000 is None:
        return False
    return True


def build_design_matrix(
    rows: Sequence[ModelRow], spec: DesignSpec
) -> np.ndarray:
    if not rows:
        raise SeasonalCountModelError("Design matrix requires at least one row.")
    unavailable = [row for row in rows if not row_is_design_available(row, spec)]
    if unavailable:
        raise SeasonalCountModelError(
            f"Design matrix has {len(unavailable)} unavailable rows."
        )
    matrix = np.zeros((len(rows), len(spec.column_names)), dtype=np.float64)
    matrix[:, 0] = 1.0
    municipality_column = {
        code: 3 + index for index, code in enumerate(spec.municipality_levels[1:])
    }
    past_column = len(spec.column_names) - 1 if spec.model_id == MODEL_S3 else None
    for row_index, row in enumerate(rows):
        matrix[row_index, 1] = row.seasonal_sin
        matrix[row_index, 2] = row.seasonal_cos
        fixed_effect_column = municipality_column.get(row.municipality_code)
        if fixed_effect_column is not None:
            matrix[row_index, fixed_effect_column] = 1.0
        if past_column is not None:
            value = row.past_incidence.incidence_per_100000
            if value is None:
                raise SeasonalCountModelError("S3 past incidence is unexpectedly missing.")
            matrix[row_index, past_column] = value
    if not np.isfinite(matrix).all():
        raise SeasonalCountModelError("Design matrix contains non-finite values.")
    return matrix


def fit_poisson_model(
    training_rows: Sequence[ModelRow],
    *,
    model_id: str,
    method: str = "IRLS",
    maxiter: int = 100,
    tol: float = 1e-8,
    cov_type: str = "nonrobust",
) -> FittedPoissonModel:
    usable_rows = [
        row
        for row in training_rows
        if model_id != MODEL_S3 or row.past_incidence.incidence_per_100000 is not None
    ]
    if not usable_rows:
        raise SeasonalCountModelError(f"{model_id} has no usable training rows.")
    spec = make_design_spec(model_id, usable_rows)
    design = build_design_matrix(usable_rows, spec)
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise SeasonalCountModelError(
            f"{model_id} design is rank deficient: rank={rank}, columns={design.shape[1]}."
        )
    target = np.asarray([row.target_value for row in usable_rows], dtype=np.float64)
    exposure = np.asarray([row.population for row in usable_rows], dtype=np.float64)
    if np.any(exposure <= 0) or not np.isfinite(exposure).all():
        raise SeasonalCountModelError("GLM exposure must be finite and positive.")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sm.GLM(
            target,
            design,
            family=sm.families.Poisson(link=sm.families.links.Log()),
            exposure=exposure,
            missing="raise",
        ).fit(
            method=method,
            maxiter=maxiter,
            tol=tol,
            cov_type=cov_type,
        )
    warning_messages = tuple(
        f"{type(item.message).__name__}: {item.message}" for item in caught
    )
    if not np.isfinite(result.params).all():
        raise SeasonalCountModelError(f"{model_id} produced non-finite coefficients.")
    return FittedPoissonModel(
        result=result,
        design_spec=spec,
        design_rank=rank,
        warning_messages=warning_messages,
    )


def prediction_arrays(
    fitted: FittedPoissonModel,
    rows: Sequence[ModelRow],
    *,
    confidence_level: float = 0.95,
    predictive_level: float = 0.95,
) -> dict[str, np.ndarray]:
    design = build_design_matrix(rows, fitted.design_spec)
    exposure = np.asarray([row.population for row in rows], dtype=np.float64)
    mean = np.asarray(
        fitted.result.predict(design, exposure=exposure), dtype=np.float64
    )
    if np.any(mean <= 0) or not np.isfinite(mean).all():
        raise SeasonalCountModelError("Poisson predictions must be finite and positive.")
    alpha = 1.0 - confidence_level
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean_frame = fitted.result.get_prediction(
            design, exposure=exposure
        ).summary_frame(alpha=alpha)
    mean_lower = np.asarray(mean_frame["mean_ci_lower"], dtype=np.float64)
    mean_upper = np.asarray(mean_frame["mean_ci_upper"], dtype=np.float64)
    predictive_alpha = 1.0 - predictive_level
    predictive_lower = np.asarray(
        poisson.ppf(predictive_alpha / 2.0, mean), dtype=np.float64
    )
    predictive_upper = np.asarray(
        poisson.ppf(1.0 - predictive_alpha / 2.0, mean), dtype=np.float64
    )
    arrays = {
        "mean": mean,
        "mean_lower": mean_lower,
        "mean_upper": mean_upper,
        "mean_ci_available": np.isfinite(mean_lower) & np.isfinite(mean_upper),
        "predictive_lower": predictive_lower,
        "predictive_upper": predictive_upper,
    }
    if not np.isfinite(predictive_lower).all() or not np.isfinite(predictive_upper).all():
        raise SeasonalCountModelError(
            "Conditional Poisson prediction intervals contain non-finite values."
        )
    return arrays


def formula_for_model(model_id: str, municipality_reference: str | None) -> str:
    base = "target_lyme_cases_next_4w ~ 1 + seasonal_sin_annual + seasonal_cos_annual"
    if model_id in (MODEL_S2, MODEL_S3):
        base += (
            " + C(municipality_code, Treatment(reference="
            f"{municipality_reference}))"
        )
    if model_id == MODEL_S3:
        base += " + past_4w_lyme_incidence_per_100000"
    return base + " + offset(log(population))"


def read_baseline_fold_metrics(
    path: Path, folds: Sequence[RollingOriginFold]
) -> list[dict[str, str]]:
    required = {
        "fold_id",
        "baseline_id",
        "n_expected_predictions",
    }
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SeasonalCountModelError(
                f"Phase 8 fold metrics are missing columns: {missing}"
            )
        rows = list(reader)
    expected = {
        (fold.fold_id, baseline_id): len(fold.validation_rows)
        for fold in folds
        for baseline_id in BASELINE_IDS
    }
    observed: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["fold_id"], row["baseline_id"])
        if key in observed:
            raise SeasonalCountModelError(f"Duplicate Phase 8 fold metric: {key}")
        observed[key] = parse_nonnegative_integer(
            row["n_expected_predictions"], context=f"Phase 8 metric {key} count"
        )
    if observed != expected:
        raise SeasonalCountModelError(
            "Phase 8 fold metrics do not use the regenerated Phase 6 folds."
        )
    return rows


def read_baseline_aggregate_comparison(path: Path) -> list[dict[str, object]]:
    required = {
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
    }
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SeasonalCountModelError(
                f"Phase 8 aggregate metrics are missing columns: {missing}"
            )
        rows = list(reader)
    if [row["baseline_id"] for row in rows] != list(BASELINE_IDS):
        raise SeasonalCountModelError("Phase 8 aggregate baseline IDs are unexpected.")
    comparison: list[dict[str, object]] = []
    for row in rows:
        comparison.append(
            {
                "system_type": "phase_8_baseline",
                "candidate_id": row["baseline_id"],
                "candidate_name": row["baseline_name"],
                **{
                    column: row[column]
                    for column in COMPARISON_COLUMNS
                    if column
                    not in {"system_type", "candidate_id", "candidate_name"}
                },
            }
        )
    return comparison


def mean_present(values: Sequence[object]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return sum(present) / len(present) if present else None


def build_seasonal_count_models(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {
        key: resolve_repo_path(value) for key, value in config["inputs"].items()
    }
    missing_inputs = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing_inputs:
        raise SeasonalCountModelError(f"Phase 9 inputs do not exist: {missing_inputs}")

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
    read_baseline_fold_metrics(input_paths["baseline_fold_metrics"], folds)

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

    model_names = {
        definition["model_id"]: definition["name"] for definition in config["models"]
    }
    fitting = config["modeling"]["fitting"]
    intervals = config["modeling"]["intervals"]
    prediction_rows: list[dict[str, object]] = []
    fold_metric_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    training_population_year_lags: list[int] = []
    validation_population_year_lags: list[int] = []

    for fold in folds:
        train_rows = prepare_model_rows(
            fold.train_rows, target_values, population, weekly_cases
        )
        validation_rows = prepare_model_rows(
            fold.validation_rows, target_values, population, weekly_cases
        )
        training_population_year_lags.extend(
            row.issue_week.year - row.population_year for row in train_rows
        )
        validation_population_year_lags.extend(
            row.issue_week.year - row.population_year for row in validation_rows
        )
        train_target_end_max = max(row.target_window_end for row in train_rows)
        if train_target_end_max >= fold.validation_start:
            raise SeasonalCountModelError(
                f"{fold.fold_id} training targets reach validation."
            )

        for model_id in MODEL_IDS:
            fitted = fit_poisson_model(
                train_rows,
                model_id=model_id,
                method=fitting["method"],
                maxiter=fitting["maxiter"],
                tol=fitting["tol"],
                cov_type=fitting["cov_type"],
            )
            train_used = [
                row
                for row in train_rows
                if row_is_design_available(row, fitted.design_spec)
            ]
            validation_available = [
                row
                for row in validation_rows
                if row_is_design_available(row, fitted.design_spec)
            ]
            predicted_by_key: dict[tuple[str, date], dict[str, float]] = {}
            if validation_available:
                arrays = prediction_arrays(
                    fitted,
                    validation_available,
                    confidence_level=intervals["mean_confidence_level"],
                    predictive_level=intervals[
                        "conditional_poisson_predictive_level"
                    ],
                )
                for index, row in enumerate(validation_available):
                    predicted_by_key[(row.municipality_code, row.issue_week)] = {
                        key: float(values[index]) for key, values in arrays.items()
                    }

            model_fold_predictions: list[dict[str, object]] = []
            for row in validation_rows:
                key = (row.municipality_code, row.issue_week)
                predicted = predicted_by_key.get(key)
                if predicted is None:
                    prediction_status = (
                        "missing_unseen_municipality"
                        if fitted.design_spec.municipality_levels
                        and row.municipality_code
                        not in fitted.design_spec.municipality_levels
                        else "missing_past_incidence"
                    )
                    mean = None
                    mean_lower = None
                    mean_upper = None
                    mean_ci_status = "prediction_missing"
                    predictive_lower = None
                    predictive_upper = None
                    contribution = None
                    poisson_status = "prediction_missing"
                else:
                    prediction_status = (
                        "available"
                        if bool(fitted.result.converged)
                        else "available_fit_not_converged"
                    )
                    mean = predicted["mean"]
                    if bool(predicted["mean_ci_available"]):
                        mean_lower = predicted["mean_lower"]
                        mean_upper = predicted["mean_upper"]
                        mean_ci_status = "available"
                    else:
                        mean_lower = None
                        mean_upper = None
                        mean_ci_status = "unavailable_nonfinite_wald_bound"
                    predictive_lower = int(predicted["predictive_lower"])
                    predictive_upper = int(predicted["predictive_upper"])
                    contribution, poisson_status = poisson_deviance_contribution(
                        row.target_value, mean
                    )
                model_fold_predictions.append(
                    {
                        "fold_id": fold.fold_id,
                        "model_id": model_id,
                        "model_name": model_names[model_id],
                        "municipality_code": row.municipality_code,
                        "issue_week": row.issue_week,
                        "target_window_start": row.target_window_start,
                        "target_window_end": row.target_window_end,
                        "actual_target_lyme_cases_next_4w": row.target_value,
                        "predicted_target_lyme_cases_next_4w": mean,
                        "expected_mean_ci_lower_95": mean_lower,
                        "expected_mean_ci_upper_95": mean_upper,
                        "expected_mean_ci_status": mean_ci_status,
                        "conditional_poisson_prediction_lower_95": predictive_lower,
                        "conditional_poisson_prediction_upper_95": predictive_upper,
                        "prediction_status": prediction_status,
                        "population_exposure": row.population,
                        "population_year": row.population_year,
                        "population_year_lag": row.issue_week.year
                        - row.population_year,
                        "population_reference_date": date(row.population_year, 1, 1),
                        "offset_log_population": math.log(row.population),
                        "seasonal_sin_annual": row.seasonal_sin,
                        "seasonal_cos_annual": row.seasonal_cos,
                        "past_4w_lyme_cases": (
                            row.past_incidence.case_count if model_id == MODEL_S3 else None
                        ),
                        "past_4w_lyme_incidence_per_100000": (
                            row.past_incidence.incidence_per_100000
                            if model_id == MODEL_S3
                            else None
                        ),
                        "past_case_window_start": (
                            row.past_incidence.window_start
                            if model_id == MODEL_S3
                            else None
                        ),
                        "past_case_window_end": (
                            row.past_incidence.window_end
                            if model_id == MODEL_S3
                            else None
                        ),
                        "latest_past_case_week_used": (
                            row.past_incidence.latest_information_week
                            if model_id == MODEL_S3
                            else None
                        ),
                        "fit_target_end_max": train_target_end_max,
                        "fit_converged": bool(fitted.result.converged),
                        "poisson_deviance_contribution": contribution,
                        "poisson_deviance_status": poisson_status,
                    }
                )

            model_fold_predictions.sort(
                key=lambda item: (str(item["municipality_code"]), item["issue_week"])
            )
            prediction_rows.extend(model_fold_predictions)
            metric_summary = summarize_prediction_metrics(model_fold_predictions)
            fold_metric_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "model_id": model_id,
                    "model_name": model_names[model_id],
                    **metric_summary,
                }
            )

            result = fitted.result
            diagnostic_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "model_id": model_id,
                    "model_name": model_names[model_id],
                    "formula": formula_for_model(
                        model_id, fitted.design_spec.municipality_reference
                    ),
                    "family": "Poisson",
                    "link": "log",
                    "fit_method": fitting["method"],
                    "n_train_fold_rows": len(train_rows),
                    "n_train_used": len(train_used),
                    "n_train_feature_missing": len(train_rows) - len(train_used),
                    "n_validation_fold_rows": len(validation_rows),
                    "n_validation_available": len(validation_available),
                    "n_parameters": len(fitted.design_spec.column_names),
                    "design_matrix_rank": fitted.design_rank,
                    "municipality_reference": (
                        fitted.design_spec.municipality_reference
                    ),
                    "n_municipality_levels": len(
                        fitted.design_spec.municipality_levels
                    ),
                    "offset": "log(population)",
                    "offset_coefficient": 1.0,
                    "population_exposure_min": min(row.population for row in train_used),
                    "population_exposure_max": max(row.population for row in train_used),
                    "population_year_lag_min": min(
                        row.issue_week.year - row.population_year
                        for row in train_used
                    ),
                    "population_year_lag_max": max(
                        row.issue_week.year - row.population_year
                        for row in train_used
                    ),
                    "train_target_end_max": train_target_end_max,
                    "validation_start": fold.validation_start,
                    "converged": bool(result.converged),
                    "iterations": result.fit_history.get("iteration"),
                    "warning_count": len(fitted.warning_messages),
                    "warning_messages": json.dumps(
                        fitted.warning_messages, ensure_ascii=False
                    ),
                    "deviance": float(result.deviance),
                    "pearson_chi2": float(result.pearson_chi2),
                }
            )
            for feature, coefficient, standard_error in zip(
                fitted.design_spec.column_names,
                result.params,
                result.bse,
                strict=True,
            ):
                coefficient_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "model_id": model_id,
                        "feature": feature,
                        "coefficient": float(coefficient),
                        "standard_error": float(standard_error),
                    }
                )

    aggregate_metric_rows: list[dict[str, object]] = []
    for model_id in MODEL_IDS:
        model_predictions = [
            row for row in prediction_rows if row["model_id"] == model_id
        ]
        pooled = summarize_prediction_metrics(model_predictions)
        model_fold_metrics = [
            row for row in fold_metric_rows if row["model_id"] == model_id
        ]
        aggregate_metric_rows.append(
            {
                "model_id": model_id,
                "model_name": model_names[model_id],
                "n_folds": len(model_fold_metrics),
                "n_expected_predictions": pooled["n_expected_predictions"],
                "n_available_predictions": pooled["n_available_predictions"],
                "n_missing_predictions": pooled["n_missing_predictions"],
                "prediction_metric_status": pooled["prediction_metric_status"],
                "pooled_mae": pooled["mae"],
                "mean_fold_mae": mean_present(
                    [row["mae"] for row in model_fold_metrics]
                ),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": mean_present(
                    [row["rmse"] for row in model_fold_metrics]
                ),
                "pooled_mean_poisson_deviance": pooled[
                    "mean_poisson_deviance"
                ],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
                "n_poisson_valid": pooled["n_poisson_valid"],
                "n_poisson_invalid": pooled["n_poisson_invalid"],
            }
        )

    comparison_rows = read_baseline_aggregate_comparison(
        input_paths["baseline_aggregate_metrics"]
    )
    for row in aggregate_metric_rows:
        comparison_rows.append(
            {
                "system_type": "phase_9_statistical_model",
                "candidate_id": row["model_id"],
                "candidate_name": row["model_name"],
                **{
                    column: row[column]
                    for column in COMPARISON_COLUMNS
                    if column
                    not in {"system_type", "candidate_id", "candidate_name"}
                },
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
        raise SeasonalCountModelError("Output filenames must not contain subdirectories.")

    write_csv_rows(output_paths["fold_predictions"], PREDICTION_COLUMNS, prediction_rows)
    write_csv_rows(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, fold_metric_rows)
    write_csv_rows(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        aggregate_metric_rows,
    )
    write_csv_rows(
        output_paths["development_comparison"], COMPARISON_COLUMNS, comparison_rows
    )
    write_csv_rows(
        output_paths["fit_diagnostics"], FIT_DIAGNOSTIC_COLUMNS, diagnostic_rows
    )
    write_csv_rows(output_paths["coefficients"], COEFFICIENT_COLUMNS, coefficient_rows)

    source_records = {
        "population": file_record(input_paths["population"]),
        "weekly_cases": file_record(input_paths["weekly_cases"]),
        "target": file_record(target_path),
        "validation_config": file_record(input_paths["validation_config"]),
        "validation_manifest": file_record(input_paths["validation_manifest"]),
        "baseline_fold_metrics": file_record(input_paths["baseline_fold_metrics"]),
        "baseline_aggregate_metrics": file_record(
            input_paths["baseline_aggregate_metrics"]
        ),
        "phase_9_config": file_record(config_path),
        "builder": file_record(Path(__file__).resolve()),
    }
    realized_configuration: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.seasonal_count_models",
        "library_versions": {
            "statsmodels": statsmodels.__version__,
            "numpy": np.__version__,
            "scipy": importlib.metadata.version("scipy"),
            "patsy_transitive_dependency": importlib.metadata.version("patsy"),
        },
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
        "modeling": config["modeling"],
        "models": config["models"],
        "realized_formulas": {
            model_id: formula_for_model(
                model_id,
                next(
                    row["municipality_reference"]
                    for row in diagnostic_rows
                    if row["model_id"] == model_id
                ),
            )
            for model_id in MODEL_IDS
        },
        "metrics": config["metrics"],
        "folds": [
            {key: csv_value(value) for key, value in fold.manifest_record().items()}
            for fold in folds
        ],
        "sources": source_records,
    }
    output_paths["model_configuration"].write_text(
        json.dumps(realized_configuration, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    expected_predictions = sum(len(fold.validation_rows) for fold in folds) * len(
        MODEL_IDS
    )
    all_converged = all(bool(row["converged"]) for row in diagnostic_rows)
    s3_predictions = [row for row in prediction_rows if row["model_id"] == MODEL_S3]
    output_records = {
        key: file_record(path)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.seasonal_count_models",
        "status": "pass" if all_converged else "warning_nonconverged_fit",
        "sources": source_records,
        "outputs": output_records,
        "summary": {
            "fold_count": len(folds),
            "model_count": len(MODEL_IDS),
            "validation_municipality_week_rows": sum(
                len(fold.validation_rows) for fold in folds
            ),
            "prediction_rows": len(prediction_rows),
            "fold_metric_rows": len(fold_metric_rows),
            "aggregate_metric_rows": len(aggregate_metric_rows),
            "comparison_rows": len(comparison_rows),
            "fit_diagnostic_rows": len(diagnostic_rows),
            "coefficient_rows": len(coefficient_rows),
            "converged_fits": sum(bool(row["converged"]) for row in diagnostic_rows),
            "nonconverged_fits": sum(
                not bool(row["converged"]) for row in diagnostic_rows
            ),
            "unavailable_expected_mean_confidence_intervals": sum(
                row["expected_mean_ci_status"]
                == "unavailable_nonfinite_wald_bound"
                for row in prediction_rows
            ),
            "training_population_selections": len(training_population_year_lags),
            "validation_population_selections": len(validation_population_year_lags),
            "training_population_older_year_fallbacks": sum(
                lag > 1 for lag in training_population_year_lags
            ),
            "validation_population_older_year_fallbacks": sum(
                lag > 1 for lag in validation_population_year_lags
            ),
        },
        "checks": {
            "validation_manifest_matches_regenerated_folds": True,
            "phase_8_metrics_match_same_fold_ids_and_row_counts": True,
            "prediction_row_count_matches_fold_contract": len(prediction_rows)
            == expected_predictions,
            "all_fit_target_windows_precede_validation": all(
                row["train_target_end_max"] < row["validation_start"]
                for row in diagnostic_rows
            ),
            "all_prediction_issue_weeks_precede_lockbox": all(
                row["issue_week"].year < lockbox_year for row in prediction_rows
            ),
            "all_prediction_target_windows_precede_lockbox": all(
                row["target_window_end"].year < lockbox_year
                for row in prediction_rows
            ),
            "all_population_exposures_precede_lockbox": all(
                row["population_year"] < lockbox_year for row in prediction_rows
            ),
            "all_training_population_years_precede_issue_year": all(
                lag >= 1 for lag in training_population_year_lags
            ),
            "all_validation_population_years_precede_issue_year": all(
                lag >= 1 for lag in validation_population_year_lags
            ),
            "previous_year_population_preferred_when_present": all(
                (row["municipality_code"], row["issue_week"].year - 1)
                not in population
                or row["population_year"] == row["issue_week"].year - 1
                for row in prediction_rows
            ),
            "population_used_as_explicit_exposure": True,
            "population_in_design_matrix_as_ordinary_feature": False,
            "offset_coefficient_fixed_to_one": all(
                row["offset_coefficient"] == 1.0 for row in diagnostic_rows
            ),
            "all_design_matrices_full_rank": all(
                row["design_matrix_rank"] == row["n_parameters"]
                for row in diagnostic_rows
            ),
            "all_fits_converged": all_converged,
            "s3_latest_case_information_precedes_issue_week": all(
                row["latest_past_case_week_used"] < row["issue_week"]
                for row in s3_predictions
                if row["latest_past_case_week_used"] is not None
            ),
            "s3_incidence_denominator_matches_model_exposure": all(
                row["past_4w_lyme_cases"] is None
                and row["past_4w_lyme_incidence_per_100000"] is None
                or row["past_4w_lyme_cases"] is not None
                and row["past_4w_lyme_incidence_per_100000"] is not None
                and math.isclose(
                    row["past_4w_lyme_incidence_per_100000"],
                    row["past_4w_lyme_cases"]
                    / row["population_exposure"]
                    * 100000.0,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
                for row in s3_predictions
            ),
            "s3_current_week_used": False,
            "s3_future_week_used": False,
            "long_term_trend_used": False,
            "weather_features_used": False,
            "environmental_features_used": False,
            "catboost_used": False,
            "classification_auc_computed": False,
            "lockbox_target_values_used": False,
            "lockbox_case_values_used": False,
            "lockbox_population_values_used": False,
            "lockbox_performance_computed": False,
        },
        "population_availability": {
            "implemented_rule": (
                "latest_present_population_year_strictly_before_issue_year"
            ),
            "preferred_population_year": "issue_year_minus_1",
            "missing_previous_year_rule": "use_latest_present_earlier_year",
            "exact_available_at_timestamps": "unavailable",
            "interpretation": (
                "conservative_leakage_prevention_proxy_not_verified_publication_timing"
            ),
            "minimum_training_year_lag": min(training_population_year_lags),
            "maximum_training_year_lag": max(training_population_year_lags),
            "minimum_validation_year_lag": min(validation_population_year_lags),
            "maximum_validation_year_lag": max(validation_population_year_lags),
        },
        "predictive_intervals": {
            "expected_mean_confidence_interval": "statsmodels GLM mean 95 percent confidence interval",
            "nonfinite_expected_mean_interval_rule": "retain point and conditional count prediction; write missing mean bounds with explicit status",
            "conditional_count_interval": "central 95 percent Poisson interval conditional on fitted mean",
            "parameter_uncertainty_in_conditional_count_interval": "not_included",
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
        description="Evaluate seasonal Poisson Lyme models on development folds."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the Phase 9 configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_seasonal_count_models(config_path)
    summary = quality["summary"]
    print("Seasonal Lyme Poisson development models evaluated.")
    print(f"- folds: {summary['fold_count']}")
    print(f"- models: {summary['model_count']}")
    print(
        "- validation municipality-week rows: "
        f"{summary['validation_municipality_week_rows']}"
    )
    print(f"- fit convergence: {summary['converged_fits']}/{summary['fit_diagnostic_rows']}")
    print("Aggregate development metrics:")
    for row in quality["aggregate_metrics"]:
        print(
            f"- {row['model_id']}: MAE={row['pooled_mae']}, "
            f"RMSE={row['pooled_rmse']}, "
            f"Poisson={row['pooled_mean_poisson_deviance']}"
        )
    print("No 2025 lockbox performance was computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
