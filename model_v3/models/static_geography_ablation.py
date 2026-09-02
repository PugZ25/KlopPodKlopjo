from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm

from model_v3.models.non_ml_baselines import (
    csv_value,
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
from model_v3.validation.rolling_origin import (
    generate_rolling_origin_folds,
    load_config as load_validation_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_static_geography_ablation.json"
)

CONTROL_ID = "statistical_baseline_s1"
AUGMENTED_ID = "statistical_baseline_s1_plus_static_geography"
CANDIDATE_IDS = (CONTROL_ID, AUGMENTED_ID)
AREA_COLUMN = "municipality_area_km2"
BASE_COLUMNS = (
    "intercept",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
)
AUGMENTED_COLUMNS = BASE_COLUMNS + (AREA_COLUMN,)

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
    "population_reference_date",
    "offset_log_population",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "municipality_area_km2",
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
    "metric",
    "control_value",
    "augmented_value",
    "augmented_minus_control",
    "result",
)

DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "candidate_id",
    "candidate_name",
    "formula",
    "n_train",
    "n_validation",
    "n_parameters",
    "design_matrix_rank",
    "offset",
    "offset_coefficient",
    "train_target_end_max",
    "validation_start",
    "population_exposure_min",
    "population_exposure_max",
    "population_year_lag_min",
    "population_year_lag_max",
    "area_min_km2",
    "area_max_km2",
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


class StaticGeographyAblationError(ValueError):
    """Raised when the Phase 11 experiment violates its declared contract."""


@dataclass(frozen=True)
class AblationRow:
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


@dataclass(frozen=True)
class FittedCandidate:
    result: Any
    column_names: tuple[str, ...]
    design_rank: int
    warning_messages: tuple[str, ...]


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise StaticGeographyAblationError(
            f"Ablation configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise StaticGeographyAblationError("Configuration schema_version must equal 1.")

    expected_inputs = {
        "population",
        "static_features",
        "static_quality_summary",
        "validation_config",
        "validation_manifest",
        "phase_9_config",
        "phase_9_fold_predictions",
    }
    inputs = config.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != expected_inputs:
        raise StaticGeographyAblationError("Input keys do not match the Phase 11 contract.")
    if any(not isinstance(value, str) or not value for value in inputs.values()):
        raise StaticGeographyAblationError("Every input path must be a non-empty string.")

    expected_experiment = {
        "control": {
            "candidate_id": CONTROL_ID,
            "name": "Phase 9 S1 unchanged",
            "phase_9_model_id": MODEL_S1,
            "design_columns": list(BASE_COLUMNS),
            "formula": (
                "target_lyme_cases_next_4w ~ 1 + seasonal_sin_annual + "
                "seasonal_cos_annual + offset(log(population))"
            ),
        },
        "augmented": {
            "candidate_id": AUGMENTED_ID,
            "name": "Phase 9 S1 plus municipality area",
            "design_columns": list(AUGMENTED_COLUMNS),
            "formula": (
                "target_lyme_cases_next_4w ~ 1 + seasonal_sin_annual + "
                "seasonal_cos_annual + municipality_area_km2 + "
                "offset(log(population))"
            ),
        },
        "static_feature_columns": [AREA_COLUMN],
        "baseline_change_rule": "only_append_declared_static_feature_columns",
        "s2_s3_exclusion_reason": (
            "municipality fixed effects make time-invariant municipality "
            "descriptors exactly non-identifiable"
        ),
    }
    if config.get("experiment") != expected_experiment:
        raise StaticGeographyAblationError("Experiment definition is unsupported.")

    expected_metrics = {
        "mae": "mean_absolute_error",
        "rmse": "root_mean_squared_error",
        "poisson_deviance": (
            "mean_poisson_deviance_only_when_all_prediction_observation_pairs_"
            "are_mathematically_valid"
        ),
        "increment_definition": "augmented_minus_control",
        "lower_is_better": True,
    }
    if config.get("metrics") != expected_metrics:
        raise StaticGeographyAblationError("Metric definition is unsupported.")

    expected_outputs = {
        "directory",
        "experiment_configuration",
        "fold_predictions",
        "fold_metrics",
        "aggregate_metrics",
        "incremental_comparison",
        "fit_diagnostics",
        "coefficients",
        "quality_summary",
    }
    outputs = config.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != expected_outputs:
        raise StaticGeographyAblationError("Output keys do not match the contract.")
    if any(not isinstance(value, str) or not value for value in outputs.values()):
        raise StaticGeographyAblationError("Every output value must be non-empty.")
    return config


def read_static_features(
    path: Path, quality_path: Path
) -> tuple[dict[str, float], dict[str, Any]]:
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if quality.get("status") != "pass":
        raise StaticGeographyAblationError("Static feature quality status is not pass.")
    dataset = quality.get("dataset")
    if not isinstance(dataset, dict) or dataset.get("sha256") != file_record(path)["sha256"]:
        raise StaticGeographyAblationError(
            "Static feature file does not match its quality summary hash."
        )
    expected_dictionary = {
        "column": AREA_COLUMN,
        "ellipsoid": "WGS84",
        "missing_data_rule": "fail_on_missing_invalid_or_nonpositive_geometry_area",
        "multipolygon_rule": "sum_polygon_areas",
        "polygon_hole_rule": "subtract_absolute_geodesic_hole_areas",
        "source_geom_area_property_exclusion_reason": (
            "unit_not_verified_in_active_source_documentation"
        ),
        "source_geom_area_property_used": False,
        "transformation": (
            "absolute_wgs84_ellipsoidal_polygon_area_m2_divided_by_1000000"
        ),
        "unit": "square_kilometres",
    }
    feature_dictionary = quality.get("feature_dictionary")
    if not isinstance(feature_dictionary, dict) or feature_dictionary.get(
        AREA_COLUMN
    ) != expected_dictionary:
        raise StaticGeographyAblationError("Static feature dictionary is unexpected.")

    areas: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("municipality_code", AREA_COLUMN):
            raise StaticGeographyAblationError("Static feature columns are unexpected.")
        for row_index, row in enumerate(reader, start=1):
            code = parse_code(
                row["municipality_code"], context=f"static feature row {row_index}"
            )
            if code in areas:
                raise StaticGeographyAblationError(
                    f"Duplicate static feature municipality: {code}"
                )
            try:
                area = float(row[AREA_COLUMN])
            except (TypeError, ValueError) as exc:
                raise StaticGeographyAblationError(
                    f"Invalid municipality area for {code}: {row[AREA_COLUMN]!r}"
                ) from exc
            if not math.isfinite(area) or area <= 0:
                raise StaticGeographyAblationError(
                    f"Municipality area must be finite and positive for {code}."
                )
            areas[code] = area
    if not areas or len(areas) != dataset.get("row_count"):
        raise StaticGeographyAblationError(
            "Static feature row count does not match its quality summary."
        )
    return areas, quality


def prepare_rows(
    target_rows: Sequence[Any],
    target_values: Mapping[tuple[str, date], int],
    population_by_key: Mapping[tuple[str, int], int],
    areas: Mapping[str, float],
) -> list[AblationRow]:
    population_history = build_population_history(population_by_key)
    prepared: list[AblationRow] = []
    for target_row in target_rows:
        key = (target_row.municipality_code, target_row.issue_week)
        if key not in target_values:
            raise StaticGeographyAblationError(f"Target is missing for {key}.")
        if target_row.municipality_code not in areas:
            raise StaticGeographyAblationError(
                f"Static area is missing for {target_row.municipality_code}."
            )
        exposure = select_population_exposure(
            population_history,
            municipality_code=target_row.municipality_code,
            issue_week=target_row.issue_week,
        )
        seasonal_sin, seasonal_cos = seasonal_terms(target_row.issue_week)
        prepared.append(
            AblationRow(
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
            )
        )
    return prepared


def design_columns(candidate_id: str) -> tuple[str, ...]:
    if candidate_id == CONTROL_ID:
        return BASE_COLUMNS
    if candidate_id == AUGMENTED_ID:
        return AUGMENTED_COLUMNS
    raise StaticGeographyAblationError(f"Unknown candidate ID: {candidate_id}")


def build_design_matrix(
    rows: Sequence[AblationRow], candidate_id: str
) -> np.ndarray:
    if not rows:
        raise StaticGeographyAblationError("Design matrix requires rows.")
    columns = design_columns(candidate_id)
    matrix = np.zeros((len(rows), len(columns)), dtype=np.float64)
    matrix[:, 0] = 1.0
    for row_index, row in enumerate(rows):
        matrix[row_index, 1] = row.seasonal_sin
        matrix[row_index, 2] = row.seasonal_cos
        if candidate_id == AUGMENTED_ID:
            matrix[row_index, 3] = row.municipality_area_km2
    if not np.isfinite(matrix).all():
        raise StaticGeographyAblationError("Design matrix contains non-finite values.")
    return matrix


def fit_candidate(
    rows: Sequence[AblationRow],
    *,
    candidate_id: str,
    method: str,
    maxiter: int,
    tol: float,
    cov_type: str,
) -> FittedCandidate:
    design = build_design_matrix(rows, candidate_id)
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise StaticGeographyAblationError(
            f"{candidate_id} design is rank deficient: {rank}/{design.shape[1]}."
        )
    target = np.asarray([row.target_value for row in rows], dtype=np.float64)
    exposure = np.asarray([row.population for row in rows], dtype=np.float64)
    if np.any(exposure <= 0) or not np.isfinite(exposure).all():
        raise StaticGeographyAblationError("Population exposure must be positive.")
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
    if not np.isfinite(result.params).all():
        raise StaticGeographyAblationError(
            f"{candidate_id} produced non-finite coefficients."
        )
    return FittedCandidate(
        result=result,
        column_names=design_columns(candidate_id),
        design_rank=rank,
        warning_messages=tuple(
            f"{type(item.message).__name__}: {item.message}" for item in caught
        ),
    )


def predict_candidate(
    fitted: FittedCandidate,
    rows: Sequence[AblationRow],
    *,
    candidate_id: str,
) -> np.ndarray:
    design = build_design_matrix(rows, candidate_id)
    exposure = np.asarray([row.population for row in rows], dtype=np.float64)
    predictions = np.asarray(
        fitted.result.predict(design, exposure=exposure), dtype=np.float64
    )
    if np.any(predictions <= 0) or not np.isfinite(predictions).all():
        raise StaticGeographyAblationError(
            f"{candidate_id} predictions must be finite and positive."
        )
    return predictions


def read_phase_9_s1_predictions(
    path: Path, *, lockbox_year: int
) -> dict[tuple[str, str, date], float]:
    required = {
        "fold_id",
        "model_id",
        "municipality_code",
        "issue_week",
        "predicted_target_lyme_cases_next_4w",
    }
    predictions: dict[tuple[str, str, date], float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise StaticGeographyAblationError(
                f"Phase 9 predictions are missing columns: {missing}"
            )
        for row_index, row in enumerate(reader, start=1):
            if row["model_id"] != MODEL_S1:
                continue
            issue_week = parse_monday(
                row["issue_week"], context=f"Phase 9 prediction row {row_index}"
            )
            if issue_week.year >= lockbox_year:
                raise StaticGeographyAblationError(
                    "Phase 9 reference predictions contain a lockbox issue week."
                )
            code = parse_code(
                row["municipality_code"],
                context=f"Phase 9 prediction row {row_index}",
            )
            key = (row["fold_id"], code, issue_week)
            if key in predictions:
                raise StaticGeographyAblationError(
                    f"Duplicate Phase 9 S1 prediction: {key}"
                )
            try:
                prediction = float(row["predicted_target_lyme_cases_next_4w"])
            except (TypeError, ValueError) as exc:
                raise StaticGeographyAblationError(
                    f"Invalid Phase 9 S1 prediction at {key}."
                ) from exc
            if not math.isfinite(prediction) or prediction <= 0:
                raise StaticGeographyAblationError(
                    f"Phase 9 S1 prediction must be finite and positive at {key}."
                )
            predictions[key] = prediction
    if not predictions:
        raise StaticGeographyAblationError("Phase 9 S1 reference predictions are empty.")
    return predictions


def classify_metric_delta(delta: float) -> str:
    if not math.isfinite(delta):
        raise StaticGeographyAblationError("Metric delta must be finite.")
    if delta < 0:
        return "improvement"
    if delta > 0:
        return "deterioration"
    return "no_change"


def build_static_geography_ablation(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    input_paths = {
        key: resolve_repo_path(value) for key, value in config["inputs"].items()
    }
    missing_inputs = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing_inputs:
        raise StaticGeographyAblationError(
            f"Phase 11 inputs do not exist: {missing_inputs}"
        )

    phase_9_config = load_phase_9_config(input_paths["phase_9_config"])
    phase_9_s1 = phase_9_config["models"][0]
    if phase_9_s1.get("model_id") != MODEL_S1 or tuple(
        phase_9_s1.get("design_columns", ())
    ) != BASE_COLUMNS:
        raise StaticGeographyAblationError(
            "Phase 9 S1 no longer matches the declared control design."
        )
    fitting = phase_9_config["modeling"]["fitting"]
    areas, static_quality = read_static_features(
        input_paths["static_features"], input_paths["static_quality_summary"]
    )

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
    population = read_development_population(
        input_paths["population"], lockbox_year=lockbox_year
    )
    phase_9_reference = read_phase_9_s1_predictions(
        input_paths["phase_9_fold_predictions"], lockbox_year=lockbox_year
    )

    experiment = config["experiment"]
    candidate_names = {
        CONTROL_ID: experiment["control"]["name"],
        AUGMENTED_ID: experiment["augmented"]["name"],
    }
    formulas = {
        CONTROL_ID: experiment["control"]["formula"],
        AUGMENTED_ID: experiment["augmented"]["formula"],
    }
    prediction_rows: list[dict[str, object]] = []
    fold_metric_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    population_year_lags: list[int] = []

    for fold in folds:
        train_rows = prepare_rows(fold.train_rows, target_values, population, areas)
        validation_rows = prepare_rows(
            fold.validation_rows, target_values, population, areas
        )
        population_year_lags.extend(
            row.issue_week.year - row.population_year
            for row in train_rows + validation_rows
        )
        train_target_end_max = max(row.target_window_end for row in train_rows)
        if train_target_end_max >= fold.validation_start:
            raise StaticGeographyAblationError(
                f"{fold.fold_id} training targets reach validation."
            )

        for candidate_id in CANDIDATE_IDS:
            fitted = fit_candidate(
                train_rows,
                candidate_id=candidate_id,
                method=fitting["method"],
                maxiter=fitting["maxiter"],
                tol=fitting["tol"],
                cov_type=fitting["cov_type"],
            )
            predicted = predict_candidate(
                fitted, validation_rows, candidate_id=candidate_id
            )
            candidate_fold_predictions: list[dict[str, object]] = []
            for row, prediction in zip(validation_rows, predicted, strict=True):
                prediction = float(prediction)
                contribution, poisson_status = poisson_deviance_contribution(
                    row.target_value, prediction
                )
                candidate_fold_predictions.append(
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
                            "available"
                            if bool(fitted.result.converged)
                            else "available_fit_not_converged"
                        ),
                        "population_exposure": row.population,
                        "population_year": row.population_year,
                        "population_year_lag": (
                            row.issue_week.year - row.population_year
                        ),
                        "population_reference_date": date(row.population_year, 1, 1),
                        "offset_log_population": math.log(row.population),
                        "seasonal_sin_annual": row.seasonal_sin,
                        "seasonal_cos_annual": row.seasonal_cos,
                        "municipality_area_km2": (
                            row.municipality_area_km2
                            if candidate_id == AUGMENTED_ID
                            else None
                        ),
                        "fit_target_end_max": train_target_end_max,
                        "fit_converged": bool(fitted.result.converged),
                        "poisson_deviance_contribution": contribution,
                        "poisson_deviance_status": poisson_status,
                    }
                )
            candidate_fold_predictions.sort(
                key=lambda item: (str(item["municipality_code"]), item["issue_week"])
            )
            prediction_rows.extend(candidate_fold_predictions)
            fold_metric_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names[candidate_id],
                    **summarize_prediction_metrics(candidate_fold_predictions),
                }
            )

            result = fitted.result
            diagnostic_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names[candidate_id],
                    "formula": formulas[candidate_id],
                    "n_train": len(train_rows),
                    "n_validation": len(validation_rows),
                    "n_parameters": len(fitted.column_names),
                    "design_matrix_rank": fitted.design_rank,
                    "offset": "log(population)",
                    "offset_coefficient": 1.0,
                    "train_target_end_max": train_target_end_max,
                    "validation_start": fold.validation_start,
                    "population_exposure_min": min(row.population for row in train_rows),
                    "population_exposure_max": max(row.population for row in train_rows),
                    "population_year_lag_min": min(
                        row.issue_week.year - row.population_year for row in train_rows
                    ),
                    "population_year_lag_max": max(
                        row.issue_week.year - row.population_year for row in train_rows
                    ),
                    "area_min_km2": (
                        min(row.municipality_area_km2 for row in train_rows)
                        if candidate_id == AUGMENTED_ID
                        else None
                    ),
                    "area_max_km2": (
                        max(row.municipality_area_km2 for row in train_rows)
                        if candidate_id == AUGMENTED_ID
                        else None
                    ),
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
        candidate_predictions = [
            row for row in prediction_rows if row["candidate_id"] == candidate_id
        ]
        candidate_fold_metrics = [
            row for row in fold_metric_rows if row["candidate_id"] == candidate_id
        ]
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
                "mean_fold_mae": mean_present(
                    [row["mae"] for row in candidate_fold_metrics]
                ),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": mean_present(
                    [row["rmse"] for row in candidate_fold_metrics]
                ),
                "pooled_mean_poisson_deviance": pooled[
                    "mean_poisson_deviance"
                ],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
                "n_poisson_valid": pooled["n_poisson_valid"],
                "n_poisson_invalid": pooled["n_poisson_invalid"],
            }
        )

    aggregate_by_id = {row["candidate_id"]: row for row in aggregate_rows}
    incremental_rows: list[dict[str, object]] = []
    for metric in (
        "pooled_mae",
        "pooled_rmse",
        "pooled_mean_poisson_deviance",
    ):
        control_value = float(aggregate_by_id[CONTROL_ID][metric])
        augmented_value = float(aggregate_by_id[AUGMENTED_ID][metric])
        delta = augmented_value - control_value
        incremental_rows.append(
            {
                "metric": metric,
                "control_value": control_value,
                "augmented_value": augmented_value,
                "augmented_minus_control": delta,
                "result": classify_metric_delta(delta),
            }
        )

    control_predictions = {
        (row["fold_id"], row["municipality_code"], row["issue_week"]): float(
            row["predicted_target_lyme_cases_next_4w"]
        )
        for row in prediction_rows
        if row["candidate_id"] == CONTROL_ID
    }
    if set(control_predictions) != set(phase_9_reference):
        raise StaticGeographyAblationError(
            "Control prediction keys do not match Phase 9 S1 prediction keys."
        )
    control_differences = {
        key: abs(control_predictions[key] - phase_9_reference[key])
        for key in control_predictions
    }
    maximum_control_difference = max(control_differences.values(), default=0.0)
    if not all(
        math.isclose(
            control_predictions[key],
            phase_9_reference[key],
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        for key in control_predictions
    ):
        raise StaticGeographyAblationError(
            "Recomputed control predictions do not reproduce Phase 9 S1."
        )

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key != "directory"
    }
    if any(path.parent != output_directory for path in output_paths.values()):
        raise StaticGeographyAblationError(
            "Output filenames must not contain subdirectories."
        )
    write_csv_rows(output_paths["fold_predictions"], PREDICTION_COLUMNS, prediction_rows)
    write_csv_rows(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, fold_metric_rows)
    write_csv_rows(
        output_paths["aggregate_metrics"], AGGREGATE_METRIC_COLUMNS, aggregate_rows
    )
    write_csv_rows(
        output_paths["incremental_comparison"],
        INCREMENTAL_COLUMNS,
        incremental_rows,
    )
    write_csv_rows(output_paths["fit_diagnostics"], DIAGNOSTIC_COLUMNS, diagnostic_rows)
    write_csv_rows(output_paths["coefficients"], COEFFICIENT_COLUMNS, coefficient_rows)

    source_records = {
        "population": file_record(input_paths["population"]),
        "static_features": file_record(input_paths["static_features"]),
        "static_quality_summary": file_record(input_paths["static_quality_summary"]),
        "target": file_record(target_path),
        "validation_config": file_record(input_paths["validation_config"]),
        "validation_manifest": file_record(input_paths["validation_manifest"]),
        "phase_9_config": file_record(input_paths["phase_9_config"]),
        "phase_9_fold_predictions": file_record(
            input_paths["phase_9_fold_predictions"]
        ),
        "phase_11_config": file_record(config_path),
        "builder": file_record(Path(__file__).resolve()),
    }
    realized_configuration: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.static_geography_ablation",
        "library_versions": {
            "statsmodels": statsmodels.__version__,
            "numpy": np.__version__,
            "scipy": importlib.metadata.version("scipy"),
        },
        "development_policy": {
            "start_year": policy["development_start_year"],
            "end_year": policy["development_end_year"],
            "excluded_lockbox_year": lockbox_year,
            "fold_strategy": policy["fold_strategy"],
        },
        "target": {
            "column": "target_lyme_cases_next_4w",
            "forecast_window": "t_plus_1_through_t_plus_4",
        },
        "experiment": experiment,
        "phase_9_fitting_reused_without_change": fitting,
        "phase_9_population_policy_reused_without_change": phase_9_config[
            "modeling"
        ]["population_availability_safeguard"],
        "metrics": config["metrics"],
        "folds": [
            {key: csv_value(value) for key, value in fold.manifest_record().items()}
            for fold in folds
        ],
        "static_feature_dictionary": static_quality["feature_dictionary"],
        "static_feature_temporal_scope": static_quality["temporal_scope"],
        "sources": source_records,
    }
    output_paths["experiment_configuration"].write_text(
        json.dumps(realized_configuration, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    expected_prediction_rows = sum(len(fold.validation_rows) for fold in folds) * len(
        CANDIDATE_IDS
    )
    all_converged = all(bool(row["converged"]) for row in diagnostic_rows)
    output_records = {
        key: file_record(path)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.models.static_geography_ablation",
        "status": "pass" if all_converged else "warning_nonconverged_fit",
        "sources": source_records,
        "outputs": output_records,
        "summary": {
            "fold_count": len(folds),
            "candidate_count": len(CANDIDATE_IDS),
            "validation_municipality_week_rows": sum(
                len(fold.validation_rows) for fold in folds
            ),
            "prediction_rows": len(prediction_rows),
            "fit_count": len(diagnostic_rows),
            "converged_fits": sum(bool(row["converged"]) for row in diagnostic_rows),
            "nonconverged_fits": sum(
                not bool(row["converged"]) for row in diagnostic_rows
            ),
            "maximum_absolute_control_prediction_difference_from_phase_9_s1": (
                maximum_control_difference
            ),
            "minimum_population_year_lag": min(population_year_lags),
            "maximum_population_year_lag": max(population_year_lags),
        },
        "checks": {
            "validation_manifest_matches_regenerated_folds": True,
            "control_design_columns_equal_phase_9_s1": True,
            "control_predictions_reproduce_phase_9_s1_within_csv_tolerance": True,
            "phase_9_predictions_excluded_from_feature_matrix": True,
            "phase_9_predictions_used_only_for_postfit_control_parity_check": True,
            "only_augmented_design_column_is_municipality_area_km2": (
                AUGMENTED_COLUMNS[:-1] == BASE_COLUMNS
                and AUGMENTED_COLUMNS[-1] == AREA_COLUMN
            ),
            "prediction_row_count_matches_fold_contract": (
                len(prediction_rows) == expected_prediction_rows
            ),
            "candidate_prediction_counts_identical": all(
                sum(row["candidate_id"] == candidate_id for row in prediction_rows)
                == expected_prediction_rows // len(CANDIDATE_IDS)
                for candidate_id in CANDIDATE_IDS
            ),
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
            "all_population_years_precede_issue_year": all(
                row["population_year"] < row["issue_week"].year
                for row in prediction_rows
            ),
            "population_used_as_explicit_exposure": True,
            "population_excluded_from_ordinary_design_columns": True,
            "offset_coefficient_fixed_to_one": all(
                row["offset_coefficient"] == 1.0 for row in diagnostic_rows
            ),
            "all_design_matrices_full_rank": all(
                row["design_matrix_rank"] == row["n_parameters"]
                for row in diagnostic_rows
            ),
            "all_fits_converged": all_converged,
            "no_static_feature_missing_values_imputed": True,
            "no_weather_features_used": True,
            "no_land_cover_features_used": True,
            "no_elevation_features_used": True,
            "no_catboost_used": True,
            "no_classification_metrics_used": True,
            "no_lockbox_target_values_used": True,
            "no_lockbox_population_values_used": True,
            "no_lockbox_performance_computed": True,
        },
        "static_feature": {
            "column": AREA_COLUMN,
            "dictionary": static_quality["feature_dictionary"][AREA_COLUMN],
            "temporal_scope": static_quality["temporal_scope"],
            "source": static_quality["sources"]["municipality_geometry"],
        },
        "incremental_comparison": [
            {key: csv_value(value) for key, value in row.items()}
            for row in incremental_rows
        ],
        "aggregate_metrics": [
            {key: csv_value(value) for key, value in row.items()}
            for row in aggregate_rows
        ],
    }
    if not all(quality["checks"].values()):
        quality["status"] = "fail"
    output_paths["quality_summary"].write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if quality["status"] == "fail":
        raise StaticGeographyAblationError("Phase 11 quality checks failed.")
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate S1 with and without static municipality area."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the Phase 11 configuration.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_static_geography_ablation(config_path)
    summary = quality["summary"]
    print("Static geography development ablation evaluated.")
    print(f"- folds: {summary['fold_count']}")
    print(f"- candidates: {summary['candidate_count']}")
    print(
        "- validation municipality-week rows per candidate: "
        f"{summary['validation_municipality_week_rows']}"
    )
    print(f"- fit convergence: {summary['converged_fits']}/{summary['fit_count']}")
    print("Incremental development results (augmented minus control):")
    for row in quality["incremental_comparison"]:
        print(
            f"- {row['metric']}: {row['augmented_minus_control']} "
            f"({row['result']})"
        )
    print("The 2025 lockbox was not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
