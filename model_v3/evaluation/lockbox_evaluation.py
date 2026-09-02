from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
import statsmodels
import xarray as xr
from catboost import CatBoostRegressor
from scipy import sparse

from model_v3.features.weather_weekly import (
    EXPECTED_UNITS,
    MEAN_OUTPUTS,
    OUTPUT_VARIABLES,
    SOURCE_VARIABLES,
    WEEKLY_COLUMNS,
    WEIGHT_COLUMNS,
    deaccumulate_precipitation,
    datetime64_to_utc,
    monday_week_start,
    read_canonical_codes,
    spatial_weighted_mean,
    write_csv_rows as write_weather_rows,
)
from model_v3.models.catboost_challenger import (
    CHALLENGER_ID,
    REFERENCE_ID,
    ChallengerRow,
    attach_weather,
    build_pool,
    fit_reference,
    load_config as load_catboost_config,
    ordered_rows,
    predict_reference,
    validate_feature_availability,
    validate_municipality_one_hot_contract,
)
from model_v3.models.non_ml_baselines import (
    BASELINE_D,
    HistoricalExpectations,
    file_record,
    fit_historical_expectations,
    parse_code,
    parse_monday,
    parse_nonnegative_integer,
    poisson_deviance_contribution,
    predict_historical_baselines,
    read_development_iso_weeks,
    read_development_weekly_cases,
    resolve_repo_path,
    sha256_file,
    summarize_prediction_metrics,
    write_csv_rows,
)
from model_v3.models.seasonal_count_models import (
    ModelRow,
    prepare_model_rows,
    read_development_population,
    read_development_target_metadata,
    read_selected_development_target_values,
)
from model_v3.models.weather_ablation import (
    WeeklyWeather,
    WeatherScaler,
    fit_weather_scaler,
    issue_weather_features,
    read_weekly_weather,
)
from model_v3.validation.rolling_origin import TargetWindowRow


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_lockbox_evaluation_2025.json"
)

SYSTEM_IDS = (CHALLENGER_ID, REFERENCE_ID, BASELINE_D)
SYSTEM_NAMES = {
    CHALLENGER_ID: "Frozen CatBoost Poisson final model",
    REFERENCE_ID: "Matched S3 weather Poisson GLM",
    BASELINE_D: "Municipality and seasonal historical expectation",
}
SYSTEM_TYPES = {
    CHALLENGER_ID: "final_selected_model",
    REFERENCE_ID: "primary_statistical_comparator",
    BASELINE_D: "secondary_epidemiological_baseline",
}

PREDICTION_COLUMNS = (
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
    "interval_lower",
    "interval_upper",
    "interval_status",
    "population_exposure",
    "population_year",
    "population_year_lag",
    "past_4w_lyme_cases",
    "past_4w_lyme_incidence_per_100000",
    "latest_past_case_week_used",
    "latest_weather_week_used",
    "latest_weather_week_end",
    "fit_target_end_max",
    "signed_error_prediction_minus_observation",
    "absolute_error",
    "squared_error",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)

METRIC_COLUMNS = (
    "system_type",
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
    "interval_metric_status",
)

CALIBRATION_OVERALL_COLUMNS = (
    "candidate_id",
    "candidate_name",
    "n",
    "observed_total",
    "predicted_total",
    "observed_mean",
    "predicted_mean",
    "mean_signed_error_prediction_minus_observation",
    "observed_to_predicted_total_ratio",
    "log_observed_to_predicted_total_ratio",
    "calibration_status",
    "diagnostic_only_no_recalibration",
)

CALIBRATION_GROUP_COLUMNS = (
    "candidate_id",
    "candidate_name",
    "calibration_group",
    "n",
    "prediction_min",
    "prediction_max",
    "predicted_mean",
    "observed_mean",
    "predicted_total",
    "observed_total",
    "observed_to_predicted_total_ratio",
    "mean_signed_error_prediction_minus_observation",
)

MUNICIPALITY_ERROR_COLUMNS = (
    "candidate_id",
    "candidate_name",
    "municipality_code",
    "municipality_name",
    "n_issue_weeks",
    "observed_total",
    "predicted_total",
    "mae",
    "rmse",
    "median_absolute_error",
    "maximum_absolute_error",
    "mean_signed_error_prediction_minus_observation",
    "mean_poisson_deviance",
    "poisson_deviance_status",
)

TEMPORAL_ERROR_COLUMNS = (
    "candidate_id",
    "candidate_name",
    "issue_week",
    "iso_year",
    "iso_week",
    "n_municipalities",
    "observed_total",
    "predicted_total",
    "mae",
    "rmse",
    "median_absolute_error",
    "maximum_absolute_error",
    "mean_signed_error_prediction_minus_observation",
    "mean_poisson_deviance",
    "poisson_deviance_status",
)


class LockboxEvaluationError(ValueError):
    """Raised when the one-time lockbox protocol is violated."""


@dataclass(frozen=True)
class PreflightContext:
    config: Mapping[str, Any]
    paths: Mapping[str, Path]
    municipality_names: Mapping[str, str]
    lockbox_calendar_weeks: tuple[date, ...]
    issue_weeks: tuple[date, ...]
    development_target_rows: tuple[TargetWindowRow, ...]
    development_target_values: Mapping[tuple[str, date], int]
    development_population: Mapping[tuple[str, int], int]
    development_weekly_cases: Mapping[tuple[str, date], int]
    development_training_rows: tuple[ChallengerRow, ...]
    combined_weather: Mapping[tuple[str, date], WeeklyWeather]
    weather_scaler: WeatherScaler
    historical_expectations: HistoricalExpectations
    n_development_rows_before_feature_completeness: int
    n_development_rows_excluded_missing_past_cases: int
    n_development_rows_excluded_incomplete_weather: int
    weather_extension_quality: Mapping[str, Any]


@dataclass(frozen=True)
class FittedSystems:
    catboost_model: CatBoostRegressor
    reference_model: Any
    train_target_end_max: date


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise LockboxEvaluationError("Lockbox configuration must be in repository.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise LockboxEvaluationError("Lockbox schema_version must equal 1.")
    freeze = config.get("freeze", {})
    if freeze != {
        "model_selection_document": "model_v3/MODEL_SELECTION.md",
        "model_selection_sha256": "4b665ca2138be3e8eb061c135590868b67ce58dd4a070318de59cae632b6ea8f",
        "lockbox_year": 2025,
        "development_start_year": 2016,
        "development_end_year": 2024,
        "run_once": True,
        "systems": list(SYSTEM_IDS),
        "no_post_lockbox_model_selection": True,
    }:
        raise LockboxEvaluationError("Frozen lockbox declaration changed.")
    target = config.get("target", {})
    if target != {
        "analysis_unit": "municipality_code_x_issue_week",
        "column": "target_lyme_cases_next_4w",
        "included_week_offsets": [1, 2, 3, 4],
        "issue_week_included": False,
        "lockbox_window_rule": "target_window_fully_contained_in_calendar_year_2025",
        "future_week_completeness_rule": "all_four_future_weeks_must_exist_in_verified_canonical_calendar_otherwise_boundary_purge",
    }:
        raise LockboxEvaluationError("Frozen target declaration changed.")
    weather = config.get("weather_extension", {})
    expected_weather = {
        "dataset": "reanalysis-era5-land",
        "product": "final_ERA5_Land",
        "required_expver": "0001",
        "first_valid_time": "2024-12-01T00:00:00Z",
        "cutoff": "2025-11-30T23:00:00Z",
        "first_file": "era5land_slovenia_2024_12.nc",
        "last_file": "era5land_slovenia_2025_11.nc",
        "latest_feature_week_start": "2025-11-17",
        "latest_feature_week_end": "2025-11-23",
        "spatial_weights": "reuse_frozen_area_weighted_polygon_overlay_weights",
        "fixed_municipality_zones_all_years": True,
        "post_cutoff_rule": "do_not_extrapolate_impute_or_create_weather_after_cutoff",
    }
    if weather != expected_weather:
        raise LockboxEvaluationError("Lockbox weather extension contract changed.")
    metrics = config.get("metrics", {})
    if metrics != {
        "mae": "mean_absolute_error",
        "rmse": "root_mean_squared_error",
        "poisson_deviance": "mean_poisson_deviance_only_when_all_prediction_observation_pairs_are_mathematically_valid",
        "interval_metrics": "not_available_frozen_final_system_has_no_predictive_intervals",
    }:
        raise LockboxEvaluationError("Frozen metric declaration changed.")
    calibration = config.get("calibration_diagnostics", {})
    if calibration.get("reliability_groups") != 10:
        raise LockboxEvaluationError("Calibration group count changed.")
    if calibration.get("diagnostic_only_no_recalibration") is not True:
        raise LockboxEvaluationError("Calibration must remain diagnostic only.")
    protected = config.get("protected_input", {})
    if protected.get("path") != config.get("inputs", {}).get("weekly_cases"):
        raise LockboxEvaluationError("Protected weekly-case path changed.")
    if protected.get("sha256") != (
        "e85085beb9314b7866781d0a8b77e5afe58812280de2e8503680576bd65daf1d"
    ):
        raise LockboxEvaluationError("Protected weekly-case hash changed.")
    required_outputs = {
        "directory",
        "weather_extension",
        "weather_quality",
        "predictions",
        "metrics",
        "calibration_overall",
        "calibration_groups",
        "municipality_errors",
        "temporal_errors",
        "fit_diagnostics",
        "quality_summary",
        "receipt",
        "report",
    }
    if set(config.get("outputs", {})) != required_outputs:
        raise LockboxEvaluationError("Lockbox output declaration changed.")
    return config


def output_paths(config: Mapping[str, Any]) -> dict[str, Path]:
    outputs = config["outputs"]
    directory = resolve_repo_path(outputs["directory"])
    paths = {
        key: directory / value
        for key, value in outputs.items()
        if key not in {"directory", "report"}
    }
    paths["directory"] = directory
    paths["report"] = resolve_repo_path(outputs["report"])
    if any(
        path.parent != directory
        for key, path in paths.items()
        if key not in {"directory", "report"}
    ):
        raise LockboxEvaluationError("Lockbox output names must not contain paths.")
    return paths


def verify_frozen_hashes(config: Mapping[str, Any]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for raw_path, expected in config["frozen_sha256"].items():
        path = resolve_repo_path(raw_path)
        if not path.is_file():
            raise LockboxEvaluationError(f"Frozen input is missing: {raw_path}")
        actual = sha256_file(path)
        if actual != expected:
            raise LockboxEvaluationError(
                f"Frozen input changed: {raw_path}: expected={expected}, actual={actual}"
            )
        records.append(file_record(path))
    selection_path = resolve_repo_path(config["freeze"]["model_selection_document"])
    if sha256_file(selection_path) != config["freeze"]["model_selection_sha256"]:
        raise LockboxEvaluationError("MODEL_SELECTION.md changed after freeze.")
    return records


def verify_runtime_versions() -> dict[str, str]:
    versions = {
        "catboost": catboost.__version__,
        "numpy": np.__version__,
        "statsmodels": statsmodels.__version__,
    }
    expected = {"catboost": "1.2.10", "numpy": "2.4.4", "statsmodels": "0.14.6"}
    if versions != expected:
        raise LockboxEvaluationError(
            f"Frozen dependency versions changed: expected={expected}, actual={versions}"
        )
    return versions


def read_municipality_names(path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != (
            "municipality_code",
            "municipality_name",
        ):
            raise LockboxEvaluationError("Municipality schema changed.")
        for row_index, row in enumerate(reader, start=1):
            code = parse_code(row["municipality_code"], context=f"municipality {row_index}")
            name = row["municipality_name"].strip()
            if not name or code in names:
                raise LockboxEvaluationError("Municipality names are missing or duplicated.")
            names[code] = name
    if len(names) != 212:
        raise LockboxEvaluationError("Lockbox requires exactly 212 municipalities.")
    return names


def read_lockbox_issue_weeks(
    path: Path, *, lockbox_year: int
) -> tuple[tuple[date, ...], tuple[date, ...]]:
    observed: list[date] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "issue_week" not in (reader.fieldnames or ()):
            raise LockboxEvaluationError("Calendar lacks issue_week.")
        for row_index, row in enumerate(reader, start=1):
            issue_week = parse_monday(
                row["issue_week"], context=f"calendar row {row_index} issue_week"
            )
            if issue_week.year == lockbox_year:
                observed.append(issue_week)
    observed = sorted(set(observed))
    first = date(lockbox_year, 1, 1)
    while first.weekday() != 0:
        first += timedelta(days=1)
    expected_through_last_observed: list[date] = []
    current = first
    while observed and current <= observed[-1]:
        expected_through_last_observed.append(current)
        current += timedelta(weeks=1)
    if not observed or observed != expected_through_last_observed:
        raise LockboxEvaluationError(
            "Calendar does not contain a contiguous sequence of 2025 Mondays."
        )
    observed_set = set(observed)
    eligible = tuple(
        week
        for week in observed
        if all(
            week + timedelta(weeks=offset) in observed_set
            for offset in (1, 2, 3, 4)
        )
    )
    if not eligible:
        raise LockboxEvaluationError("Lockbox has no eligible issue weeks.")
    return tuple(observed), eligible


def expected_monthly_weather_files(
    directory: Path, *, first_name: str, last_name: str
) -> list[Path]:
    def parse_name(name: str) -> tuple[int, int]:
        stem = name.removeprefix("era5land_slovenia_").removesuffix(".nc")
        try:
            year, month = (int(value) for value in stem.split("_"))
        except (TypeError, ValueError) as exc:
            raise LockboxEvaluationError(f"Invalid ERA5-Land filename: {name}") from exc
        return year, month

    start = parse_name(first_name)
    end = parse_name(last_name)
    expected: list[Path] = []
    year, month = start
    while (year, month) <= end:
        expected.append(directory / f"era5land_slovenia_{year:04d}_{month:02d}.nc")
        month += 1
        if month == 13:
            year += 1
            month = 1
    missing = [path.name for path in expected if not path.is_file()]
    if missing:
        raise LockboxEvaluationError(f"Lockbox weather files are missing: {missing}")
    return expected


def read_frozen_weight_matrix(
    path: Path,
    *,
    codes: Sequence[str],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> sparse.csr_matrix:
    code_index = {code: index for index, code in enumerate(codes)}
    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    coordinates: dict[int, tuple[float, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEIGHT_COLUMNS:
            raise LockboxEvaluationError("Frozen weather-weight schema changed.")
        for row_number, row in enumerate(reader, start=1):
            code = parse_code(row["municipality_code"], context=f"weight row {row_number}")
            if code not in code_index:
                raise LockboxEvaluationError(f"Unknown municipality in weights: {code}")
            try:
                grid_index = int(row["grid_cell_index"])
                latitude = float(row["latitude"])
                longitude = float(row["longitude"])
                weight = float(row["normalized_intersection_weight"])
            except ValueError as exc:
                raise LockboxEvaluationError(f"Invalid weather weight row {row_number}.") from exc
            if grid_index < 0 or grid_index >= len(latitudes) * len(longitudes):
                raise LockboxEvaluationError("Weather grid-cell index is out of range.")
            expected_coordinate = (
                float(latitudes[grid_index // len(longitudes)]),
                float(longitudes[grid_index % len(longitudes)]),
            )
            if not (
                math.isclose(latitude, expected_coordinate[0], abs_tol=1e-12)
                and math.isclose(longitude, expected_coordinate[1], abs_tol=1e-12)
            ):
                raise LockboxEvaluationError("Frozen weight grid differs from 2025 grid.")
            if grid_index in coordinates and coordinates[grid_index] != (latitude, longitude):
                raise LockboxEvaluationError("Grid-cell coordinate changed within weights.")
            coordinates[grid_index] = (latitude, longitude)
            if not math.isfinite(weight) or weight <= 0:
                raise LockboxEvaluationError("Weather intersection weight is invalid.")
            row_indices.append(code_index[code])
            column_indices.append(grid_index)
            values.append(weight)
    matrix = sparse.csr_matrix(
        (values, (row_indices, column_indices)),
        shape=(len(codes), len(latitudes) * len(longitudes)),
    )
    sums = np.asarray(matrix.sum(axis=1)).reshape(-1)
    if not np.allclose(sums, 1.0, rtol=0.0, atol=1e-12):
        raise LockboxEvaluationError("Frozen municipality weights do not sum to one.")
    return matrix


def extension_rows_to_weather(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, date], WeeklyWeather]:
    result: dict[tuple[str, date], WeeklyWeather] = {}
    for row in rows:
        code = str(row["municipality_code"])
        week_start = row["week_start"]
        week_end = row["week_end"]
        if not isinstance(week_start, date) or not isinstance(week_end, date):
            raise LockboxEvaluationError("Internal weather dates are invalid.")
        status = str(row["weather_status"])
        values = (
            {column: float(row[column]) for column in OUTPUT_VARIABLES}
            if status == "complete"
            else None
        )
        key = (code, week_start)
        if key in result:
            raise LockboxEvaluationError(f"Duplicate lockbox weather row: {key}")
        result[key] = WeeklyWeather(code, week_start, week_end, status, values)
    return result


def build_weather_extension(
    config: Mapping[str, Any], paths: Mapping[str, Path], outputs: Mapping[str, Path]
) -> tuple[dict[tuple[str, date], WeeklyWeather], dict[str, Any]]:
    policy = config["weather_extension"]
    monthly_files = expected_monthly_weather_files(
        paths["raw_weather_directory"],
        first_name=policy["first_file"],
        last_name=policy["last_file"],
    )
    codes = read_canonical_codes(paths["municipality"])
    reference_latitudes: np.ndarray | None = None
    reference_longitudes: np.ndarray | None = None
    weights: sparse.csr_matrix | None = None
    weekly_sums: dict[date, np.ndarray] = {}
    weekly_counts: dict[date, np.ndarray] = {}
    weekly_times: dict[date, set[datetime]] = defaultdict(set)
    raw_nan_counts = {name: 0 for name in SOURCE_VARIABLES}
    previous_tp: np.ndarray | None = None
    previous_time: datetime | None = None
    first_time: datetime | None = None
    last_time: datetime | None = None
    expver_values: set[str] = set()
    correction_count = 0
    most_negative_corrected = 0.0

    for path in monthly_files:
        with xr.open_dataset(path) as dataset:
            if set(dataset.sizes) != {"valid_time", "latitude", "longitude"}:
                raise LockboxEvaluationError(f"Unexpected dimensions in {path.name}.")
            latitudes = np.asarray(dataset["latitude"].values, dtype=np.float64)
            longitudes = np.asarray(dataset["longitude"].values, dtype=np.float64)
            if reference_latitudes is None:
                reference_latitudes = latitudes
                reference_longitudes = longitudes
                weights = read_frozen_weight_matrix(
                    paths["weather_grid_weights"],
                    codes=codes,
                    latitudes=latitudes,
                    longitudes=longitudes,
                )
            elif not np.array_equal(latitudes, reference_latitudes) or not np.array_equal(
                longitudes, reference_longitudes
            ):
                raise LockboxEvaluationError(f"ERA5-Land grid changed in {path.name}.")
            if weights is None:
                raise LockboxEvaluationError("Weather weights were not initialized.")
            for variable in SOURCE_VARIABLES:
                if variable not in dataset:
                    raise LockboxEvaluationError(f"{path.name} lacks {variable}.")
                data_array = dataset[variable]
                if data_array.dims != ("valid_time", "latitude", "longitude"):
                    raise LockboxEvaluationError(
                        f"Unexpected {variable} dimensions in {path.name}."
                    )
                if data_array.attrs.get("units") != EXPECTED_UNITS[variable]:
                    raise LockboxEvaluationError(
                        f"Unexpected {variable} unit in {path.name}."
                    )
            times = [datetime64_to_utc(value) for value in dataset["valid_time"].values]
            if not times or any(
                later - earlier != timedelta(hours=1)
                for earlier, later in zip(times, times[1:])
            ):
                raise LockboxEvaluationError(f"Non-hourly time axis in {path.name}.")
            if previous_time is not None and times[0] - previous_time != timedelta(hours=1):
                raise LockboxEvaluationError(f"Weather gap before {path.name}.")
            observed_expver = {str(value) for value in np.unique(dataset["expver"].values)}
            if observed_expver != {policy["required_expver"]}:
                raise LockboxEvaluationError(
                    f"Unexpected ERA5-Land expver in {path.name}: {observed_expver}"
                )
            expver_values.update(observed_expver)
            flattened: dict[str, np.ndarray] = {}
            for variable in SOURCE_VARIABLES:
                source = np.asarray(dataset[variable].values, dtype=np.float64)
                raw_nan_counts[variable] += int(np.isnan(source).sum())
                flattened[variable] = source.reshape(len(times), -1)
            hourly_tp, previous_tp, _, corrected, corrected_minimum = (
                deaccumulate_precipitation(
                    flattened["tp"],
                    times,
                    previous_accumulated=previous_tp,
                    previous_time=previous_time,
                )
            )
            correction_count += corrected
            most_negative_corrected = min(most_negative_corrected, corrected_minimum)
            hourly = {
                "t2m_mean_c": spatial_weighted_mean(flattened["t2m"], weights) - 273.15,
                "d2m_mean_c": spatial_weighted_mean(flattened["d2m"], weights) - 273.15,
                "tp_sum_mm": spatial_weighted_mean(hourly_tp, weights) * 1000.0,
                "stl1_mean_c": spatial_weighted_mean(flattened["stl1"], weights) - 273.15,
                "stl2_mean_c": spatial_weighted_mean(flattened["stl2"], weights) - 273.15,
                "swvl1_mean_m3_m3": spatial_weighted_mean(flattened["swvl1"], weights),
                "swvl2_mean_m3_m3": spatial_weighted_mean(flattened["swvl2"], weights),
            }
            stacked = np.stack([hourly[name] for name in OUTPUT_VARIABLES], axis=2)
            for index, current_time in enumerate(times):
                week_start = monday_week_start(current_time)
                weekly_times[week_start].add(current_time)
                if week_start not in weekly_sums:
                    weekly_sums[week_start] = np.zeros(
                        (len(codes), len(OUTPUT_VARIABLES)), dtype=np.float64
                    )
                    weekly_counts[week_start] = np.zeros(
                        (len(codes), len(OUTPUT_VARIABLES)), dtype=np.int64
                    )
                present = np.isfinite(stacked[index])
                weekly_sums[week_start] += np.where(present, stacked[index], 0.0)
                weekly_counts[week_start] += present.astype(np.int64)
            first_time = first_time or times[0]
            last_time = times[-1]
            previous_time = times[-1]

    expected_first = datetime.fromisoformat(policy["first_valid_time"].replace("Z", "+00:00"))
    expected_last = datetime.fromisoformat(policy["cutoff"].replace("Z", "+00:00"))
    if first_time != expected_first or last_time != expected_last:
        raise LockboxEvaluationError(
            f"Lockbox weather coverage changed: first={first_time}, last={last_time}."
        )

    weekly_rows: list[dict[str, object]] = []
    for week_start in sorted(weekly_sums):
        counts = weekly_counts[week_start]
        sums = weekly_sums[week_start]
        source_hours = len(weekly_times[week_start])
        complete = source_hours == 168 and bool(np.all(counts == 168))
        for municipality_index, code in enumerate(codes):
            row: dict[str, object] = {
                "municipality_code": code,
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "weather_status": "complete" if complete else "incomplete_source_week",
                "source_hour_count": source_hours,
                "minimum_present_hours": int(counts[municipality_index].min()),
            }
            for variable_index, output in enumerate(OUTPUT_VARIABLES):
                if not complete:
                    row[output] = None
                elif output in MEAN_OUTPUTS:
                    row[output] = sums[municipality_index, variable_index] / 168.0
                else:
                    row[output] = sums[municipality_index, variable_index]
            weekly_rows.append(row)

    write_weather_rows(outputs["weather_extension"], WEEKLY_COLUMNS, weekly_rows)
    extension = extension_rows_to_weather(weekly_rows)
    latest_required = date.fromisoformat(policy["latest_feature_week_start"])
    if any(
        extension[(code, latest_required)].status != "complete" for code in codes
    ):
        raise LockboxEvaluationError("Latest required 2025 weather week is incomplete.")
    quality: dict[str, Any] = {
        "schema_version": 1,
        "status": "pass",
        "pipeline": "model_v3.evaluation.lockbox_evaluation",
        "policy": policy,
        "source_audit": {
            "files_opened": len(monthly_files),
            "first_valid_time": first_time.isoformat() if first_time else None,
            "last_valid_time": last_time.isoformat() if last_time else None,
            "expver_values": sorted(expver_values),
            "raw_nan_counts": raw_nan_counts,
            "precipitation_roundoff_negative_corrections": correction_count,
            "most_negative_precipitation_roundoff_corrected_m": most_negative_corrected,
        },
        "sources": {
            "raw_hourly_files": [file_record(path) for path in monthly_files],
            "frozen_grid_weights": file_record(paths["weather_grid_weights"]),
        },
        "weekly_dataset": file_record(outputs["weather_extension"]),
        "checks": {
            "same_seven_variables_and_units": True,
            "same_frozen_polygon_overlay_weights": True,
            "fixed_212_municipalities": len(codes) == 212,
            "only_required_weather_through_cutoff_opened": last_time == expected_last,
            "latest_required_feature_week_complete": True,
            "no_weather_extrapolated_or_imputed": True,
        },
    }
    outputs["weather_quality"].write_text(
        json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return extension, quality


def merge_weather(
    development: Mapping[tuple[str, date], WeeklyWeather],
    extension: Mapping[tuple[str, date], WeeklyWeather],
) -> dict[tuple[str, date], WeeklyWeather]:
    combined = dict(development)
    for key, new in extension.items():
        old = combined.get(key)
        if old is None:
            combined[key] = new
            continue
        if old.status == "complete" and new.status != "complete":
            continue
        if old.status != "complete" and new.status == "complete":
            combined[key] = new
            continue
        if old.status == "complete" and new.status == "complete":
            if old.values is None or new.values is None:
                raise LockboxEvaluationError("Complete overlap lacks weather values.")
            for column in OUTPUT_VARIABLES:
                if not math.isclose(
                    float(old.values[column]),
                    float(new.values[column]),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    raise LockboxEvaluationError(
                        f"Development/lockbox weather overlap differs for {key}, {column}."
                    )
    return combined


def ensure_lockbox_outputs_absent(outputs: Mapping[str, Path]) -> None:
    protected_keys = {
        "predictions",
        "metrics",
        "calibration_overall",
        "calibration_groups",
        "municipality_errors",
        "temporal_errors",
        "fit_diagnostics",
        "quality_summary",
        "receipt",
        "report",
    }
    present = [str(outputs[key]) for key in protected_keys if outputs[key].exists()]
    if present:
        raise LockboxEvaluationError(
            "Lockbox has already been opened or final outputs already exist: "
            + ", ".join(sorted(present))
        )


def prepare_preflight(config_path: Path = DEFAULT_CONFIG_PATH) -> PreflightContext:
    config = load_config(config_path)
    verify_frozen_hashes(config)
    verify_runtime_versions()
    paths = {key: resolve_repo_path(value) for key, value in config["inputs"].items()}
    missing = [key for key, path in paths.items() if not path.exists()]
    if missing:
        raise LockboxEvaluationError(f"Lockbox inputs are missing: {missing}")
    outputs = output_paths(config)
    outputs["directory"].mkdir(parents=True, exist_ok=True)
    ensure_lockbox_outputs_absent(outputs)

    municipality_names = read_municipality_names(paths["municipality"])
    lockbox_calendar_weeks, issue_weeks = read_lockbox_issue_weeks(
        paths["calendar"], lockbox_year=config["freeze"]["lockbox_year"]
    )
    extension, extension_quality = build_weather_extension(config, paths, outputs)
    development_weather, development_weather_quality = read_weekly_weather(
        paths["development_weather"],
        paths["development_weather_quality"],
        lockbox_year=config["freeze"]["lockbox_year"],
    )
    if development_weather_quality.get("policy", {}).get(
        "fixed_analytical_zones_all_years"
    ) is not True:
        raise LockboxEvaluationError("Development weather municipality policy changed.")
    combined_weather = merge_weather(development_weather, extension)
    missing_weather = [
        (code, issue_week)
        for issue_week in issue_weeks
        for code in municipality_names
        if issue_weather_features(
            combined_weather, municipality_code=code, issue_week=issue_week
        )
        is None
    ]
    if missing_weather:
        raise LockboxEvaluationError(
            f"Preflight found incomplete lockbox weather features: {missing_weather[:20]}"
        )

    freeze = config["freeze"]
    target_rows = read_development_target_metadata(
        paths["development_target"],
        development_start_year=freeze["development_start_year"],
        development_end_year=freeze["development_end_year"],
    )
    development_rows = tuple(
        row
        for row in target_rows
        if row.target_training_eligible
        and row.target_window_end < date(freeze["lockbox_year"], 1, 1)
    )
    if not development_rows:
        raise LockboxEvaluationError("No development rows are eligible for final fit.")
    selected_keys = {(row.municipality_code, row.issue_week) for row in development_rows}
    target_values = read_selected_development_target_values(
        paths["development_target"],
        selected_keys,
        lockbox_year=freeze["lockbox_year"],
    )
    population = read_development_population(
        paths["population"], lockbox_year=freeze["lockbox_year"]
    )
    weekly_cases = read_development_weekly_cases(
        paths["weekly_cases"], lockbox_year=freeze["lockbox_year"]
    )
    phase9_rows = prepare_model_rows(
        development_rows, target_values, population, weekly_cases
    )
    complete_past_rows = [
        row for row in phase9_rows if row.past_incidence.status == "available"
    ]
    missing_past = len(phase9_rows) - len(complete_past_rows)
    training_rows, missing_weather_count = attach_weather(
        complete_past_rows, combined_weather
    )
    validate_feature_availability(training_rows)
    if {row.municipality_code for row in training_rows} != set(municipality_names):
        raise LockboxEvaluationError("Final training data do not cover 212 municipalities.")
    scaler = fit_weather_scaler(training_rows)
    iso_weeks = read_development_iso_weeks(
        paths["calendar"], lockbox_year=freeze["lockbox_year"]
    )
    expectations = fit_historical_expectations(
        development_rows, target_values, iso_weeks
    )
    load_catboost_config(paths["catboost_config"])
    return PreflightContext(
        config=config,
        paths=paths,
        municipality_names=municipality_names,
        lockbox_calendar_weeks=lockbox_calendar_weeks,
        issue_weeks=issue_weeks,
        development_target_rows=development_rows,
        development_target_values=target_values,
        development_population=population,
        development_weekly_cases=weekly_cases,
        development_training_rows=tuple(training_rows),
        combined_weather=combined_weather,
        weather_scaler=scaler,
        historical_expectations=expectations,
        n_development_rows_before_feature_completeness=len(phase9_rows),
        n_development_rows_excluded_missing_past_cases=missing_past,
        n_development_rows_excluded_incomplete_weather=missing_weather_count,
        weather_extension_quality=extension_quality,
    )


def fit_frozen_systems(context: PreflightContext) -> FittedSystems:
    catboost_config = load_catboost_config(context.paths["catboost_config"])
    statistical_config = json.loads(
        context.paths["statistical_config"].read_text(encoding="utf-8")
    )
    fitting = statistical_config["modeling"]["fitting"]
    reference = fit_reference(
        context.development_training_rows, context.weather_scaler, fitting
    )
    challenger = catboost_config["challenger"]
    model = CatBoostRegressor(
        loss_function=challenger["loss_function"],
        eval_metric=challenger["loss_function"],
        has_time=challenger["ordering"]["has_time"],
        **challenger["parameters"],
    )
    model.fit(
        build_pool(
            context.development_training_rows,
            context.weather_scaler,
            include_labels=True,
        )
    )
    train_target_end_max = max(
        row.target_window_end for row in context.development_training_rows
    )
    if train_target_end_max >= date(context.config["freeze"]["lockbox_year"], 1, 1):
        raise LockboxEvaluationError("Final training target reaches the lockbox.")
    return FittedSystems(model, reference, train_target_end_max)


def create_open_receipt(
    path: Path, *, config_path: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "status": "opened_not_completed",
        "lockbox_year": config["freeze"]["lockbox_year"],
        "opened_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_config": file_record(config_path.resolve()),
        "model_selection_sha256": config["freeze"]["model_selection_sha256"],
        "protected_input_expected_sha256": config["protected_input"]["sha256"],
        "rerun_allowed": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise LockboxEvaluationError("Lockbox receipt already exists; rerun refused.") from exc
    return payload


def read_lockbox_weekly_cases_once(
    path: Path,
    *,
    lockbox_year: int,
    expected_sha256: str,
) -> tuple[dict[tuple[str, date], int], str]:
    with path.open("rb") as handle:
        payload = handle.read()
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != expected_sha256:
        raise LockboxEvaluationError(
            f"Protected weekly-case hash changed: {actual_sha256}"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LockboxEvaluationError("Protected weekly cases are not UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"municipality_code", "issue_week", "lyme_cases"}
    if not required.issubset(reader.fieldnames or ()):
        raise LockboxEvaluationError("Protected weekly-case schema changed.")
    values: dict[tuple[str, date], int] = {}
    for row_index, row in enumerate(reader, start=1):
        issue_week = parse_monday(
            row["issue_week"], context=f"protected row {row_index} issue_week"
        )
        if issue_week.year != lockbox_year:
            continue
        code = parse_code(
            row["municipality_code"], context=f"protected row {row_index} code"
        )
        value = parse_nonnegative_integer(
            row["lyme_cases"], context=f"protected[{code}, {issue_week}] Lyme cases"
        )
        key = (code, issue_week)
        if key in values:
            raise LockboxEvaluationError(f"Duplicate protected weekly case: {key}")
        values[key] = value
    if not values:
        raise LockboxEvaluationError("No 2025 weekly cases were opened.")
    return values, actual_sha256


def construct_lockbox_target(
    *,
    expected_case_weeks: Sequence[date],
    issue_weeks: Sequence[date],
    municipality_codes: Sequence[str],
    lockbox_cases: Mapping[tuple[str, date], int],
    lockbox_year: int,
) -> tuple[list[TargetWindowRow], dict[tuple[str, date], int]]:
    if not expected_case_weeks or any(
        week.year != lockbox_year for week in expected_case_weeks
    ):
        raise LockboxEvaluationError("Expected lockbox case weeks are invalid.")
    expected_keys = {
        (code, week) for code in municipality_codes for week in expected_case_weeks
    }
    missing_case_rows = sorted(expected_keys - set(lockbox_cases))
    unexpected_case_rows = sorted(set(lockbox_cases) - expected_keys)
    if missing_case_rows or unexpected_case_rows:
        raise LockboxEvaluationError(
            "2025 weekly-case grid changed: "
            f"missing={missing_case_rows[:20]}, unexpected={unexpected_case_rows[:20]}"
        )
    rows: list[TargetWindowRow] = []
    targets: dict[tuple[str, date], int] = {}
    for issue_week in issue_weeks:
        future_weeks = [issue_week + timedelta(weeks=offset) for offset in (1, 2, 3, 4)]
        if any(week.year != lockbox_year for week in future_weeks):
            raise LockboxEvaluationError("Eligible lockbox target crosses year boundary.")
        for code in municipality_codes:
            future_keys = [(code, week) for week in future_weeks]
            missing = [key for key in future_keys if key not in lockbox_cases]
            if missing:
                raise LockboxEvaluationError(f"Lockbox target window is incomplete: {missing}")
            key = (code, issue_week)
            targets[key] = sum(lockbox_cases[future_key] for future_key in future_keys)
            rows.append(
                TargetWindowRow(
                    municipality_code=code,
                    issue_week=issue_week,
                    target_window_start=future_weeks[0],
                    target_window_end=future_weeks[-1],
                    target_status="complete",
                    target_training_eligible=True,
                )
            )
    return sorted(rows), targets


def prepare_lockbox_rows(
    context: PreflightContext,
    lockbox_cases: Mapping[tuple[str, date], int],
) -> tuple[list[ChallengerRow], dict[tuple[str, date], int]]:
    rows, targets = construct_lockbox_target(
        expected_case_weeks=context.lockbox_calendar_weeks,
        issue_weeks=context.issue_weeks,
        municipality_codes=sorted(context.municipality_names),
        lockbox_cases=lockbox_cases,
        lockbox_year=context.config["freeze"]["lockbox_year"],
    )
    all_cases = dict(context.development_weekly_cases)
    overlap = set(all_cases) & set(lockbox_cases)
    if overlap:
        raise LockboxEvaluationError(f"Development/lockbox weekly cases overlap: {sorted(overlap)[:20]}")
    all_cases.update(lockbox_cases)
    phase9_rows = prepare_model_rows(
        rows,
        targets,
        context.development_population,
        all_cases,
    )
    incomplete_past = [row for row in phase9_rows if row.past_incidence.status != "available"]
    if incomplete_past:
        raise LockboxEvaluationError(
            f"Lockbox past-case features are incomplete: {len(incomplete_past)} rows."
        )
    attached, excluded_weather = attach_weather(phase9_rows, context.combined_weather)
    if excluded_weather:
        raise LockboxEvaluationError(
            f"Lockbox weather features are incomplete: {excluded_weather} rows."
        )
    validate_feature_availability(attached)
    if len(attached) != len(rows):
        raise LockboxEvaluationError("Lockbox feature row count changed.")
    return attached, targets


def prediction_row(
    row: ChallengerRow,
    prediction: float,
    *,
    candidate_id: str,
    fit_target_end_max: date,
    weather_used: bool,
) -> dict[str, object]:
    contribution, poisson_status = poisson_deviance_contribution(
        row.target_value, prediction
    )
    signed_error = prediction - row.target_value
    return {
        "system_type": SYSTEM_TYPES[candidate_id],
        "candidate_id": candidate_id,
        "candidate_name": SYSTEM_NAMES[candidate_id],
        "municipality_code": row.municipality_code,
        "issue_week": row.issue_week,
        "target_window_start": row.target_window_start,
        "target_window_end": row.target_window_end,
        "actual_target_lyme_cases_next_4w": row.target_value,
        "predicted_target_lyme_cases_next_4w": prediction,
        "prediction_status": "available",
        "interval_lower": None,
        "interval_upper": None,
        "interval_status": "not_available_frozen_system_has_no_predictive_intervals",
        "population_exposure": row.population,
        "population_year": row.population_year,
        "population_year_lag": row.issue_week.year - row.population_year,
        "past_4w_lyme_cases": row.past_incidence.case_count,
        "past_4w_lyme_incidence_per_100000": row.past_incidence.incidence_per_100000,
        "latest_past_case_week_used": row.past_incidence.latest_information_week,
        "latest_weather_week_used": row.weather.latest_week_start if weather_used else None,
        "latest_weather_week_end": row.weather.latest_week_end if weather_used else None,
        "fit_target_end_max": fit_target_end_max,
        "signed_error_prediction_minus_observation": signed_error,
        "absolute_error": abs(signed_error),
        "squared_error": signed_error * signed_error,
        "poisson_deviance_contribution": contribution,
        "poisson_deviance_status": poisson_status,
    }


def generate_predictions(
    context: PreflightContext,
    fitted: FittedSystems,
    lockbox_rows: Sequence[ChallengerRow],
) -> list[dict[str, object]]:
    rows = ordered_rows(lockbox_rows)
    catboost_config = load_catboost_config(context.paths["catboost_config"])
    one_hot_max_size = catboost_config["challenger"]["parameters"]["one_hot_max_size"]
    validate_municipality_one_hot_contract(
        context.development_training_rows,
        rows,
        one_hot_max_size=one_hot_max_size,
    )
    pool = build_pool(rows, context.weather_scaler, include_labels=False)
    catboost_values = np.asarray(
        fitted.catboost_model.predict(
            pool,
            prediction_type=catboost_config["challenger"]["prediction_type"],
        ),
        dtype=np.float64,
    )
    reference_values = predict_reference(
        fitted.reference_model, rows, context.weather_scaler
    )
    if (
        len(catboost_values) != len(rows)
        or len(reference_values) != len(rows)
        or np.any(catboost_values <= 0)
        or not np.isfinite(catboost_values).all()
    ):
        raise LockboxEvaluationError("Frozen model predictions are invalid.")

    predictions: list[dict[str, object]] = []
    for row, value in zip(rows, catboost_values, strict=True):
        predictions.append(
            prediction_row(
                row,
                float(value),
                candidate_id=CHALLENGER_ID,
                fit_target_end_max=fitted.train_target_end_max,
                weather_used=True,
            )
        )
    for row, value in zip(rows, reference_values, strict=True):
        predictions.append(
            prediction_row(
                row,
                float(value),
                candidate_id=REFERENCE_ID,
                fit_target_end_max=fitted.train_target_end_max,
                weather_used=True,
            )
        )
    for row in rows:
        baseline = predict_historical_baselines(
            context.historical_expectations,
            municipality_code=row.municipality_code,
            iso_week=row.issue_week.isocalendar().week,
        )[BASELINE_D]
        predictions.append(
            prediction_row(
                row,
                baseline.value,
                candidate_id=BASELINE_D,
                fit_target_end_max=context.historical_expectations.latest_target_end,
                weather_used=False,
            )
        )
    return sorted(
        predictions,
        key=lambda item: (
            SYSTEM_IDS.index(str(item["candidate_id"])),
            item["issue_week"],
            str(item["municipality_code"]),
        ),
    )


def metric_rows(predictions: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate_id in SYSTEM_IDS:
        selected = [row for row in predictions if row["candidate_id"] == candidate_id]
        summary = summarize_prediction_metrics(selected)
        rows.append(
            {
                "system_type": SYSTEM_TYPES[candidate_id],
                "candidate_id": candidate_id,
                "candidate_name": SYSTEM_NAMES[candidate_id],
                **summary,
                "interval_metric_status": "not_available_frozen_system_has_no_predictive_intervals",
            }
        )
    return rows


def overall_calibration_rows(
    predictions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for candidate_id in SYSTEM_IDS:
        rows = [row for row in predictions if row["candidate_id"] == candidate_id]
        observed = [float(row["actual_target_lyme_cases_next_4w"]) for row in rows]
        predicted = [float(row["predicted_target_lyme_cases_next_4w"]) for row in rows]
        observed_total = sum(observed)
        predicted_total = sum(predicted)
        if predicted_total <= 0:
            ratio = None
            log_ratio = None
            status = "invalid_nonpositive_predicted_total"
        else:
            ratio = observed_total / predicted_total
            log_ratio = math.log(ratio) if ratio > 0 else None
            status = "valid" if log_ratio is not None else "undefined_zero_observed_total"
        result.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": SYSTEM_NAMES[candidate_id],
                "n": len(rows),
                "observed_total": observed_total,
                "predicted_total": predicted_total,
                "observed_mean": statistics.fmean(observed),
                "predicted_mean": statistics.fmean(predicted),
                "mean_signed_error_prediction_minus_observation": statistics.fmean(
                    prediction - observation
                    for prediction, observation in zip(predicted, observed, strict=True)
                ),
                "observed_to_predicted_total_ratio": ratio,
                "log_observed_to_predicted_total_ratio": log_ratio,
                "calibration_status": status,
                "diagnostic_only_no_recalibration": True,
            }
        )
    return result


def calibration_group_rows(
    predictions: Sequence[Mapping[str, object]], *, n_groups: int
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for candidate_id in SYSTEM_IDS:
        rows = sorted(
            (row for row in predictions if row["candidate_id"] == candidate_id),
            key=lambda row: (
                float(row["predicted_target_lyme_cases_next_4w"]),
                row["issue_week"],
                str(row["municipality_code"]),
            ),
        )
        groups: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for rank, row in enumerate(rows):
            group = min(n_groups, rank * n_groups // len(rows) + 1)
            groups[group].append(row)
        for group in range(1, n_groups + 1):
            selected = groups[group]
            predicted = [float(row["predicted_target_lyme_cases_next_4w"]) for row in selected]
            observed = [float(row["actual_target_lyme_cases_next_4w"]) for row in selected]
            predicted_total = sum(predicted)
            observed_total = sum(observed)
            result.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": SYSTEM_NAMES[candidate_id],
                    "calibration_group": group,
                    "n": len(selected),
                    "prediction_min": min(predicted),
                    "prediction_max": max(predicted),
                    "predicted_mean": statistics.fmean(predicted),
                    "observed_mean": statistics.fmean(observed),
                    "predicted_total": predicted_total,
                    "observed_total": observed_total,
                    "observed_to_predicted_total_ratio": (
                        observed_total / predicted_total if predicted_total > 0 else None
                    ),
                    "mean_signed_error_prediction_minus_observation": statistics.fmean(
                        prediction - observation
                        for prediction, observation in zip(predicted, observed, strict=True)
                    ),
                }
            )
    return result


def grouped_error_summary(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    observed = [float(row["actual_target_lyme_cases_next_4w"]) for row in rows]
    predicted = [float(row["predicted_target_lyme_cases_next_4w"]) for row in rows]
    errors = [
        prediction - observation
        for prediction, observation in zip(predicted, observed, strict=True)
    ]
    absolute = [abs(value) for value in errors]
    contributions = [
        row["poisson_deviance_contribution"]
        for row in rows
        if row["poisson_deviance_contribution"] is not None
    ]
    poisson_valid = len(contributions) == len(rows)
    return {
        "observed_total": sum(observed),
        "predicted_total": sum(predicted),
        "mae": statistics.fmean(absolute),
        "rmse": math.sqrt(statistics.fmean(value * value for value in errors)),
        "median_absolute_error": statistics.median(absolute),
        "maximum_absolute_error": max(absolute),
        "mean_signed_error_prediction_minus_observation": statistics.fmean(errors),
        "mean_poisson_deviance": (
            statistics.fmean(float(value) for value in contributions)
            if poisson_valid
            else None
        ),
        "poisson_deviance_status": (
            "valid" if poisson_valid else "invalid_zero_prediction_positive_observation_present"
        ),
    }


def municipality_error_rows(
    predictions: Sequence[Mapping[str, object]],
    municipality_names: Mapping[str, str],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        grouped[(str(row["candidate_id"]), str(row["municipality_code"]))].append(row)
    result: list[dict[str, object]] = []
    for (candidate_id, code), rows in sorted(
        grouped.items(), key=lambda item: (SYSTEM_IDS.index(item[0][0]), item[0][1])
    ):
        result.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": SYSTEM_NAMES[candidate_id],
                "municipality_code": code,
                "municipality_name": municipality_names[code],
                "n_issue_weeks": len(rows),
                **grouped_error_summary(rows),
            }
        )
    return result


def temporal_error_rows(
    predictions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, date], list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        grouped[(str(row["candidate_id"]), row["issue_week"])].append(row)  # type: ignore[index]
    result: list[dict[str, object]] = []
    for (candidate_id, issue_week), rows in sorted(
        grouped.items(), key=lambda item: (SYSTEM_IDS.index(item[0][0]), item[0][1])
    ):
        iso = issue_week.isocalendar()
        result.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": SYSTEM_NAMES[candidate_id],
                "issue_week": issue_week,
                "iso_year": iso.year,
                "iso_week": iso.week,
                "n_municipalities": len(rows),
                **grouped_error_summary(rows),
            }
        )
    return result


def read_development_performance(path: Path) -> list[dict[str, object]]:
    wanted = set(SYSTEM_IDS)
    result: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candidate_id = row["candidate_id"]
            if candidate_id not in wanted:
                continue
            result.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": row["candidate_name"],
                    "n_predictions": int(row["n_available_predictions"]),
                    "mae": float(row["pooled_mae"]),
                    "rmse": float(row["pooled_rmse"]),
                    "mean_poisson_deviance": (
                        float(row["pooled_mean_poisson_deviance"])
                        if row["pooled_mean_poisson_deviance"]
                        else None
                    ),
                    "poisson_deviance_status": row["poisson_deviance_status"],
                }
            )
    if {str(row["candidate_id"]) for row in result} != wanted:
        raise LockboxEvaluationError("Development comparison lacks a frozen system.")
    return sorted(result, key=lambda row: SYSTEM_IDS.index(str(row["candidate_id"])))


def format_metric(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.6f}"


def quantile_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise LockboxEvaluationError("Distribution summary is empty.")
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.quantile(array, 0.0)),
        "p25": float(np.quantile(array, 0.25)),
        "median": float(np.quantile(array, 0.5)),
        "p75": float(np.quantile(array, 0.75)),
        "p90": float(np.quantile(array, 0.9)),
        "maximum": float(np.quantile(array, 1.0)),
    }


def build_report(
    *,
    context: PreflightContext,
    development: Sequence[Mapping[str, object]],
    lockbox_metrics: Sequence[Mapping[str, object]],
    calibration: Sequence[Mapping[str, object]],
    municipality_errors: Sequence[Mapping[str, object]],
    temporal_errors: Sequence[Mapping[str, object]],
    protected_sha256: str,
) -> str:
    development_by_id = {str(row["candidate_id"]): row for row in development}
    lockbox_by_id = {str(row["candidate_id"]): row for row in lockbox_metrics}
    calibration_by_id = {str(row["candidate_id"]): row for row in calibration}
    final_municipality = [
        row for row in municipality_errors if row["candidate_id"] == CHALLENGER_ID
    ]
    final_temporal = [row for row in temporal_errors if row["candidate_id"] == CHALLENGER_ID]
    municipality_distribution = quantile_summary(
        [float(row["mae"]) for row in final_municipality]
    )
    temporal_distribution = quantile_summary([float(row["mae"]) for row in final_temporal])
    highest_municipalities = sorted(
        final_municipality, key=lambda row: float(row["mae"]), reverse=True
    )[:10]
    highest_weeks = sorted(
        final_temporal, key=lambda row: float(row["mae"]), reverse=True
    )[:10]
    final_lockbox = lockbox_by_id[CHALLENGER_ID]
    final_development = development_by_id[CHALLENGER_ID]

    lines = [
        "# Final 2025 Lyme lockbox evaluation",
        "",
        "- **Evaluation status:** COMPLETE — one-time lockbox opened",
        f"- **Lockbox:** calendar year {context.config['freeze']['lockbox_year']}",
        f"- **Final model:** `{CHALLENGER_ID}`",
        f"- **Eligible issue weeks:** {len(context.issue_weeks)} ({context.issue_weeks[0]} through {context.issue_weeks[-1]})",
        f"- **Observed 2025 calendar weeks:** {len(context.lockbox_calendar_weeks)} (through {context.lockbox_calendar_weeks[-1]})",
        f"- **Boundary-purged issue weeks with incomplete future horizon:** {len(context.lockbox_calendar_weeks) - len(context.issue_weeks)}",
        f"- **Municipalities:** {len(context.municipality_names)} fixed analytical zones",
        f"- **Predictions per system:** {final_lockbox['n_available_predictions']}",
        f"- **Protected weekly-case SHA-256:** `{protected_sha256}`",
        "",
        "The frozen development design was applied without tuning, feature changes, target changes, threshold changes, calibration, or model reselection. Results below are descriptive evaluation evidence; they do not authorize post-lockbox model selection.",
        "",
        "## DEVELOPMENT PERFORMANCE",
        "",
        "Development values are the frozen rolling-origin results from 2017–2024 and are shown separately from the lockbox.",
        "",
        "| System | N | MAE | RMSE | Mean Poisson deviance | Deviance status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for candidate_id in SYSTEM_IDS:
        row = development_by_id[candidate_id]
        lines.append(
            f"| {row['candidate_name']} | {row['n_predictions']} | {format_metric(row['mae'])} | {format_metric(row['rmse'])} | {format_metric(row['mean_poisson_deviance'])} | {row['poisson_deviance_status']} |"
        )
    lines.extend(
        [
            "",
            "## LOCKBOX PERFORMANCE",
            "",
            "| System | N | MAE | RMSE | Mean Poisson deviance | Deviance status |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for candidate_id in SYSTEM_IDS:
        row = lockbox_by_id[candidate_id]
        lines.append(
            f"| {row['candidate_name']} | {row['n_available_predictions']} | {format_metric(row['mae'])} | {format_metric(row['rmse'])} | {format_metric(row['mean_poisson_deviance'])} | {row['poisson_deviance_status']} |"
        )
    lines.extend(
        [
            "",
            "### Development-to-lockbox change for the frozen final model",
            "",
            f"- MAE: {format_metric(final_development['mae'])} → {format_metric(final_lockbox['mae'])}",
            f"- RMSE: {format_metric(final_development['rmse'])} → {format_metric(final_lockbox['rmse'])}",
            f"- Mean Poisson deviance: {format_metric(final_development['mean_poisson_deviance'])} → {format_metric(final_lockbox['mean_poisson_deviance'])}",
            "",
            "These changes are reported without modifying or replacing the frozen model.",
            "",
            "## Calibration diagnostics",
            "",
            "These are diagnostics only. No recalibration was fitted or applied.",
            "",
            "| System | Observed total | Predicted total | Observed mean | Predicted mean | Mean error (prediction − observation) | O/P ratio |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for candidate_id in SYSTEM_IDS:
        row = calibration_by_id[candidate_id]
        lines.append(
            f"| {row['candidate_name']} | {format_metric(row['observed_total'])} | {format_metric(row['predicted_total'])} | {format_metric(row['observed_mean'])} | {format_metric(row['predicted_mean'])} | {format_metric(row['mean_signed_error_prediction_minus_observation'])} | {format_metric(row['observed_to_predicted_total_ratio'])} |"
        )
    lines.extend(
        [
            "",
            "Ten deterministic equal-count reliability groups are saved in `model_v3/outputs/lockbox_2025/lyme_lockbox_calibration_groups.csv`.",
            "",
            "## Municipality-level error distribution",
            "",
            "The table below summarizes the frozen final model's MAE across 212 municipalities. Full per-municipality results for all systems are saved separately.",
            "",
            "| Minimum | P25 | Median | P75 | P90 | Maximum |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {format_metric(municipality_distribution['minimum'])} | {format_metric(municipality_distribution['p25'])} | {format_metric(municipality_distribution['median'])} | {format_metric(municipality_distribution['p75'])} | {format_metric(municipality_distribution['p90'])} | {format_metric(municipality_distribution['maximum'])} |",
            "",
            "Highest municipality-level MAE values:",
            "",
            "| Municipality | Code | N weeks | MAE | Mean error | Observed total | Predicted total |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in highest_municipalities:
        lines.append(
            f"| {row['municipality_name']} | {row['municipality_code']} | {row['n_issue_weeks']} | {format_metric(row['mae'])} | {format_metric(row['mean_signed_error_prediction_minus_observation'])} | {format_metric(row['observed_total'])} | {format_metric(row['predicted_total'])} |"
        )
    lines.extend(
        [
            "",
            "## Temporal error distribution",
            "",
            f"The table below summarizes municipality-level MAE across the {len(context.issue_weeks)} eligible issue weeks for the frozen final model.",
            "",
            "| Minimum | P25 | Median | P75 | P90 | Maximum |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {format_metric(temporal_distribution['minimum'])} | {format_metric(temporal_distribution['p25'])} | {format_metric(temporal_distribution['median'])} | {format_metric(temporal_distribution['p75'])} | {format_metric(temporal_distribution['p90'])} | {format_metric(temporal_distribution['maximum'])} |",
            "",
            "Highest issue-week MAE values:",
            "",
            "| Issue week | ISO week | MAE | Mean error | Observed total | Predicted total |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in highest_weeks:
        lines.append(
            f"| {row['issue_week']} | {row['iso_week']} | {format_metric(row['mae'])} | {format_metric(row['mean_signed_error_prediction_minus_observation'])} | {format_metric(row['observed_total'])} | {format_metric(row['predicted_total'])} |"
        )
    lines.extend(
        [
            "",
            "## Interval metrics",
            "",
            "Not available. The frozen final CatBoost system did not define predictive intervals, and no interval method was added after opening the lockbox.",
            "",
            "## Lockbox integrity",
            "",
            "- Target is exactly `t+1..t+4`; issue week `t` is excluded.",
            "- Every evaluated target window is fully contained in 2025.",
            "- Training targets end before 2025.",
            "- Population is from the most recent strictly earlier year.",
            "- Case and weather features end at `t-1` or earlier.",
            "- ERA5-Land uses the same final product, seven variables, units, weekly aggregation, and frozen polygon-overlay weights as development.",
            "- No thresholding, classification, calibration fitting, or model reselection was performed.",
            "- The run receipt prevents a second evaluation execution.",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_lockbox_evaluation(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    context = prepare_preflight(config_path)
    outputs = output_paths(context.config)
    fitted = fit_frozen_systems(context)
    receipt = create_open_receipt(
        outputs["receipt"], config_path=config_path, config=context.config
    )

    lockbox_cases, protected_sha256 = read_lockbox_weekly_cases_once(
        context.paths["weekly_cases"],
        lockbox_year=context.config["freeze"]["lockbox_year"],
        expected_sha256=context.config["protected_input"]["sha256"],
    )
    lockbox_rows, lockbox_targets = prepare_lockbox_rows(context, lockbox_cases)
    predictions = generate_predictions(context, fitted, lockbox_rows)
    metrics = metric_rows(predictions)
    calibration_overall = overall_calibration_rows(predictions)
    calibration_groups = calibration_group_rows(
        predictions,
        n_groups=context.config["calibration_diagnostics"]["reliability_groups"],
    )
    municipality_errors = municipality_error_rows(
        predictions, context.municipality_names
    )
    temporal_errors = temporal_error_rows(predictions)
    development = read_development_performance(
        context.paths["development_comparison"]
    )

    write_csv_rows(outputs["predictions"], PREDICTION_COLUMNS, predictions)
    write_csv_rows(outputs["metrics"], METRIC_COLUMNS, metrics)
    write_csv_rows(
        outputs["calibration_overall"],
        CALIBRATION_OVERALL_COLUMNS,
        calibration_overall,
    )
    write_csv_rows(
        outputs["calibration_groups"],
        CALIBRATION_GROUP_COLUMNS,
        calibration_groups,
    )
    write_csv_rows(
        outputs["municipality_errors"],
        MUNICIPALITY_ERROR_COLUMNS,
        municipality_errors,
    )
    write_csv_rows(
        outputs["temporal_errors"], TEMPORAL_ERROR_COLUMNS, temporal_errors
    )

    fit_diagnostics = {
        "schema_version": 1,
        "status": "complete",
        "development_rows_before_feature_completeness": context.n_development_rows_before_feature_completeness,
        "development_rows_excluded_missing_past_cases": context.n_development_rows_excluded_missing_past_cases,
        "development_rows_excluded_incomplete_weather": context.n_development_rows_excluded_incomplete_weather,
        "development_rows_used": len(context.development_training_rows),
        "development_target_end_max": fitted.train_target_end_max.isoformat(),
        "lockbox_issue_weeks": len(context.issue_weeks),
        "lockbox_calendar_weeks": len(context.lockbox_calendar_weeks),
        "lockbox_boundary_purged_issue_weeks": len(context.lockbox_calendar_weeks)
        - len(context.issue_weeks),
        "lockbox_rows": len(lockbox_rows),
        "lockbox_targets": len(lockbox_targets),
        "lockbox_weekly_case_rows_opened": len(lockbox_cases),
        "weather_scaler_fit_scope": "all_eligible_development_rows_only",
        "weather_scaler_means": dict(context.weather_scaler.means),
        "weather_scaler_standard_deviations": dict(
            context.weather_scaler.standard_deviations
        ),
        "reference_converged": bool(fitted.reference_model.result.converged),
        "reference_iterations": fitted.reference_model.result.fit_history.get("iteration"),
        "reference_warning_messages": list(fitted.reference_model.warning_messages),
        "catboost_tree_count": fitted.catboost_model.tree_count_,
        "catboost_parameters": load_catboost_config(context.paths["catboost_config"])[
            "challenger"
        ]["parameters"],
        "runtime_versions": verify_runtime_versions(),
        "intervals": "not_available_frozen_final_system_has_no_predictive_intervals",
        "calibration_applied": False,
        "hyperparameter_tuning_performed": False,
        "model_reselection_performed": False,
    }
    write_json(outputs["fit_diagnostics"], fit_diagnostics)

    report = build_report(
        context=context,
        development=development,
        lockbox_metrics=metrics,
        calibration=calibration_overall,
        municipality_errors=municipality_errors,
        temporal_errors=temporal_errors,
        protected_sha256=protected_sha256,
    )
    outputs["report"].write_text(report, encoding="utf-8")

    expected_predictions = len(context.issue_weeks) * len(context.municipality_names)
    checks = {
        "frozen_hashes_verified_before_open": True,
        "protected_weekly_cases_parsed_once": True,
        "target_is_exactly_t_plus_1_through_t_plus_4": all(
            row.target_window_start == row.issue_week + timedelta(weeks=1)
            and row.target_window_end == row.issue_week + timedelta(weeks=4)
            for row in lockbox_rows
        ),
        "issue_week_excluded_from_target": True,
        "target_windows_fully_contained_in_2025": all(
            row.target_window_start.year == 2025 and row.target_window_end.year == 2025
            for row in lockbox_rows
        ),
        "training_targets_end_before_lockbox": fitted.train_target_end_max < date(2025, 1, 1),
        "population_year_strictly_precedes_issue_year": all(
            row.population_year < row.issue_week.year for row in lockbox_rows
        ),
        "past_case_information_strictly_precedes_issue_week": all(
            row.past_incidence.latest_information_week < row.issue_week
            for row in lockbox_rows
        ),
        "weather_information_strictly_precedes_issue_week": all(
            row.weather.latest_week_end < row.issue_week for row in lockbox_rows
        ),
        "all_systems_use_same_lockbox_rows": all(
            int(row["n_expected_predictions"]) == expected_predictions for row in metrics
        ),
        "all_predictions_available": all(
            int(row["n_missing_predictions"]) == 0 for row in metrics
        ),
        "no_intervals_added_after_freeze": True,
        "no_calibration_applied": True,
        "no_model_reselection": True,
        "no_threshold_or_classification_logic": True,
    }
    if not all(checks.values()):
        raise LockboxEvaluationError(f"Lockbox integrity check failed: {checks}")

    output_records = {
        key: file_record(path)
        for key, path in outputs.items()
        if key
        in {
            "weather_extension",
            "weather_quality",
            "predictions",
            "metrics",
            "calibration_overall",
            "calibration_groups",
            "municipality_errors",
            "temporal_errors",
            "fit_diagnostics",
            "report",
        }
    }
    quality = {
        "schema_version": 1,
        "status": "pass",
        "pipeline": "model_v3.evaluation.lockbox_evaluation",
        "freeze": context.config["freeze"],
        "protected_input": {
            "path": context.config["protected_input"]["path"],
            "sha256": protected_sha256,
            "lockbox_rows_parsed": len(lockbox_cases),
            "parse_count": 1,
        },
        "support": {
            "issue_week_start": min(context.issue_weeks).isoformat(),
            "issue_week_end": max(context.issue_weeks).isoformat(),
            "n_issue_weeks": len(context.issue_weeks),
            "calendar_week_end": max(context.lockbox_calendar_weeks).isoformat(),
            "n_calendar_weeks": len(context.lockbox_calendar_weeks),
            "n_boundary_purged_issue_weeks": len(context.lockbox_calendar_weeks)
            - len(context.issue_weeks),
            "n_municipalities": len(context.municipality_names),
            "n_predictions_per_system": expected_predictions,
        },
        "checks": checks,
        "metrics": metrics,
        "calibration_overall": calibration_overall,
        "outputs": output_records,
    }
    write_json(outputs["quality_summary"], quality)
    output_records["quality_summary"] = file_record(outputs["quality_summary"])

    completed_receipt = {
        **receipt,
        "status": "completed",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protected_input_actual_sha256": protected_sha256,
        "lockbox_rows_parsed": len(lockbox_cases),
        "protected_parse_count": 1,
        "output_records": output_records,
        "rerun_allowed": False,
    }
    write_json(outputs["receipt"], completed_receipt)
    return {
        "report": str(outputs["report"].relative_to(REPO_ROOT)),
        "metrics": metrics,
        "quality_summary": str(outputs["quality_summary"].relative_to(REPO_ROOT)),
        "receipt": str(outputs["receipt"].relative_to(REPO_ROOT)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen Lyme 2025 lockbox evaluation exactly once."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Repository-local lockbox evaluation configuration.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Verify frozen inputs and 2025 weather without opening 2025 cases.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.preflight_only:
        context = prepare_preflight(args.config)
        print("Lockbox preflight passed; 2025 case values were not parsed.")
        print(f"Eligible issue weeks: {len(context.issue_weeks)}")
        print(f"Fixed municipalities: {len(context.municipality_names)}")
        print(f"Development rows ready: {len(context.development_training_rows)}")
        return 0
    result = run_lockbox_evaluation(args.config)
    print("One-time 2025 lockbox evaluation completed.")
    print(f"Report: {result['report']}")
    for row in result["metrics"]:
        print(
            f"{row['candidate_id']}: MAE={row['mae']:.6f}, "
            f"RMSE={row['rmse']:.6f}, "
            f"Poisson={format_metric(row['mean_poisson_deviance'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
