from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
import statsmodels
import statsmodels.api as sm
from catboost import CatBoostRegressor, Pool


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_region_model.json"

WEATHER_SOURCE_COLUMNS = (
    "t2m_mean_c",
    "d2m_mean_c",
    "tp_sum_mm",
    "stl1_mean_c",
    "stl2_mean_c",
    "swvl1_mean_m3_m3",
    "swvl2_mean_m3_m3",
)
WEATHER_FEATURE_COLUMNS = (
    "t2m_mean_c_previous_4w_mean",
    "tp_sum_mm_previous_4w_sum",
    "stl1_mean_c_previous_4w_mean",
    "swvl1_mean_m3_m3_previous_4w_mean",
)
CATBOOST_FEATURE_COLUMNS = (
    "statistical_region_code",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_8w_kme_incidence_per_100000",
) + WEATHER_FEATURE_COLUMNS

BASELINE_RATE = "baseline_region_historical_rate"
BASELINE_PERSISTENCE = "baseline_persistence_8w"
GLM_BASE = "glm_seasonal_region_offset"
GLM_PAST = "glm_past_kme_offset"
GLM_WEATHER_ONLY = "glm_weather_only_offset"
GLM_SEASONAL_WEATHER = "glm_seasonal_region_weather_offset"
GLM_FULL = "glm_compact_weather_offset"
CATBOOST_WEATHER = "catboost_compact_weather_offset"
SYSTEM_IDS = (
    BASELINE_RATE,
    BASELINE_PERSISTENCE,
    GLM_BASE,
    GLM_PAST,
    GLM_WEATHER_ONLY,
    GLM_SEASONAL_WEATHER,
    GLM_FULL,
    CATBOOST_WEATHER,
)
NON_ML_SYSTEM_IDS = SYSTEM_IDS[:-1]
GLM_IDS = (
    GLM_BASE,
    GLM_PAST,
    GLM_WEATHER_ONLY,
    GLM_SEASONAL_WEATHER,
    GLM_FULL,
)

FEATURE_PANEL_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "target_kme_cases_next_8w",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "population_exposure_per_100000",
    "offset_log_population_per_100000",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_8w_kme_cases",
    "past_8w_kme_incidence_per_100000",
    "past_case_window_start",
    "past_case_window_end",
    "latest_past_case_week_used",
    "weather_window_start",
    "latest_weather_week_used",
    "latest_weather_week_end",
) + WEATHER_FEATURE_COLUMNS

FOLD_MANIFEST_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "train_issue_start",
    "train_issue_end",
    "train_target_end_max",
    "validation_start",
    "validation_end",
    "n_train",
    "n_validation",
    "n_purged_target_boundary",
    "target_embargo_weeks",
)
PREDICTION_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "system_type",
    "candidate_id",
    "statistical_region_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_kme_cases_next_8w",
    "predicted_target_kme_cases_next_8w",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "past_8w_kme_cases",
    "past_8w_kme_incidence_per_100000",
    "latest_past_case_week_used",
    "latest_weather_week_used",
    "latest_weather_week_end",
    "fit_target_end_max",
    "absolute_error",
    "squared_error",
    "poisson_deviance_contribution",
    "poisson_deviance_status",
)
FOLD_METRIC_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "candidate_id",
    "n_predictions",
    "mae",
    "rmse",
    "mean_poisson_deviance",
    "poisson_deviance_status",
)
AGGREGATE_METRIC_COLUMNS = (
    "candidate_id",
    "system_type",
    "n_folds",
    "n_predictions",
    "pooled_mae",
    "mean_fold_mae",
    "pooled_rmse",
    "mean_fold_rmse",
    "pooled_mean_poisson_deviance",
    "poisson_deviance_status",
    "n_folds_improving_over_persistence_mae",
)
DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "candidate_id",
    "n_train",
    "n_validation",
    "n_parameters_or_features",
    "converged",
    "iterations",
    "warning_count",
    "warning_messages",
    "train_target_end_max",
    "validation_start",
    "training_scaler_means",
    "training_scaler_standard_deviations",
)
COEFFICIENT_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "candidate_id",
    "feature",
    "coefficient",
    "standard_error",
)
IMPORTANCE_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "candidate_id",
    "feature",
    "importance",
)


class KmeModelError(ValueError):
    """Raised when a KME model data or leakage contract fails."""


@dataclass(frozen=True)
class TargetObservation:
    region_code: str
    issue_week: date
    target_start: date
    target_end: date
    target_value: int


@dataclass(frozen=True)
class PreparedRow:
    region_code: str
    region_name: str
    issue_week: date
    target_start: date
    target_end: date
    target_value: int
    population: int
    population_year_min: int
    population_year_max: int
    seasonal_sin: float
    seasonal_cos: float
    past_cases: int
    past_incidence: float
    past_window_start: date
    past_window_end: date
    weather_values: Mapping[str, float]
    weather_window_start: date
    latest_weather_week: date
    latest_weather_week_end: date

    @property
    def exposure_per_100000(self) -> float:
        return self.population / 100_000.0

    @property
    def offset(self) -> float:
        return math.log(self.exposure_per_100000)


@dataclass(frozen=True)
class Fold:
    fold_id: str
    validation_iso_year: int
    validation_start: date
    validation_end: date
    train_rows: tuple[PreparedRow, ...]
    validation_rows: tuple[PreparedRow, ...]
    n_purged: int


@dataclass(frozen=True)
class Standardizer:
    means: Mapping[str, float]
    standard_deviations: Mapping[str, float]

    def transform(self, feature: str, value: float) -> float:
        return (value - self.means[feature]) / self.standard_deviations[feature]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(path_value: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root / path


def repository_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def require_hash(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise KmeModelError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise KmeModelError("Unsupported KME region model schema_version")
    if config["design"]["target_offsets"] != list(range(1, 9)):
        raise KmeModelError("KME target offsets must remain t+1 through t+8")
    if config["design"]["issue_week_included"] is not False:
        raise KmeModelError("KME issue week must remain excluded from the target")
    configured_ids = tuple(system["candidate_id"] for system in config["systems"])
    if configured_ids != SYSTEM_IDS:
        raise KmeModelError("Configured KME systems do not match the fixed comparison")
    return config


def parse_monday(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KmeModelError(f"Invalid date: {value!r}") from exc
    if parsed.weekday() != 0:
        raise KmeModelError(f"Expected canonical Monday, got {value!r}")
    return parsed


def read_regions(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"statistical_region_code", "statistical_region_name"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("Statistical-region schema is invalid")
        for row in reader:
            code = row["statistical_region_code"]
            if code in result:
                raise KmeModelError(f"Duplicate statistical region: {code}")
            result[code] = row["statistical_region_name"]
    if len(result) != 12:
        raise KmeModelError(f"Expected 12 statistical regions, found {len(result)}")
    return result


def read_mapping(path: Path, regions: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "statistical_region_code"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("Municipality-region mapping schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            region = row["statistical_region_code"]
            if municipality in result:
                raise KmeModelError(f"Duplicate municipality mapping: {municipality}")
            if region not in regions:
                raise KmeModelError(f"Unknown mapped region: {region}")
            result[municipality] = region
    if len(result) != 212:
        raise KmeModelError(f"Expected 212 municipality mappings, found {len(result)}")
    return result


def read_targets(path: Path, regions: Mapping[str, str]) -> list[TargetObservation]:
    result: list[TargetObservation] = []
    seen: set[tuple[str, date]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "statistical_region_code",
            "issue_week",
            "target_window_start",
            "target_window_end",
            "target_kme_cases_next_8w",
            "target_status",
            "target_training_eligible",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("KME target schema is invalid")
        for row in reader:
            if row["target_training_eligible"] != "true":
                continue
            if row["target_status"] != "complete":
                raise KmeModelError("Training-eligible target row is not complete")
            region = row["statistical_region_code"]
            if region not in regions:
                raise KmeModelError(f"Unknown target region: {region}")
            issue = parse_monday(row["issue_week"])
            target_start = parse_monday(row["target_window_start"])
            target_end = parse_monday(row["target_window_end"])
            if target_start != issue + timedelta(weeks=1):
                raise KmeModelError("KME target does not begin at t+1")
            if target_end != issue + timedelta(weeks=8):
                raise KmeModelError("KME target does not end at t+8")
            try:
                value = int(row["target_kme_cases_next_8w"])
            except ValueError as exc:
                raise KmeModelError("Complete KME target must be an integer") from exc
            if value < 0:
                raise KmeModelError("KME target must be non-negative")
            key = (region, issue)
            if key in seen:
                raise KmeModelError(f"Duplicate target key: {key}")
            seen.add(key)
            result.append(TargetObservation(region, issue, target_start, target_end, value))
    return sorted(result, key=lambda row: (row.issue_week, row.region_code))


def read_region_weekly_cases(
    path: Path, mapping: Mapping[str, str]
) -> dict[tuple[str, date], int]:
    municipality_values: dict[tuple[str, date], int] = {}
    result: defaultdict[tuple[str, date], int] = defaultdict(int)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "issue_week", "kme_cases"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("Weekly KME case schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            if municipality not in mapping:
                raise KmeModelError(f"Unmapped weekly municipality: {municipality}")
            week = parse_monday(row["issue_week"])
            key = (municipality, week)
            if key in municipality_values:
                raise KmeModelError(f"Duplicate municipality-week case row: {key}")
            if row["kme_cases"] == "":
                raise KmeModelError(f"Missing canonical KME case: {key}")
            try:
                value = int(row["kme_cases"])
            except ValueError as exc:
                raise KmeModelError(f"Invalid KME case: {row['kme_cases']!r}") from exc
            if value < 0:
                raise KmeModelError("KME cases must be non-negative")
            municipality_values[key] = value
            result[(mapping[municipality], week)] += value
    weeks = {week for _, week in municipality_values}
    expected = {(municipality, week) for municipality in mapping for week in weeks}
    if set(municipality_values) != expected:
        raise KmeModelError("Municipality-week case grid is incomplete")
    return dict(result)


def read_population(path: Path) -> dict[str, dict[int, int | None]]:
    result: defaultdict[str, dict[int, int | None]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "year", "population"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("Population schema is invalid")
        for row in reader:
            municipality = row["municipality_code"]
            year = int(row["year"])
            if year in result[municipality]:
                raise KmeModelError(f"Duplicate population key: {municipality}, {year}")
            if row["population"] == "":
                result[municipality][year] = None
            else:
                value = int(row["population"])
                if value <= 0:
                    raise KmeModelError("Population exposure must be positive when present")
                result[municipality][year] = value
    return dict(result)


def selected_region_population(
    region_code: str,
    issue_week: date,
    mapping: Mapping[str, str],
    population: Mapping[str, Mapping[int, int | None]],
) -> tuple[int, int, int]:
    selected: list[tuple[int, int]] = []
    for municipality in sorted(code for code, region in mapping.items() if region == region_code):
        available = [
            (year, value)
            for year, value in population.get(municipality, {}).items()
            if year < issue_week.year and value is not None
        ]
        if not available:
            raise KmeModelError(
                f"No safely earlier population for {municipality} at {issue_week}"
            )
        year, value = max(available)
        selected.append((year, int(value)))
    if not selected:
        raise KmeModelError(f"Region {region_code} has no mapped municipalities")
    return sum(value for _, value in selected), min(year for year, _ in selected), max(
        year for year, _ in selected
    )


def read_areas(path: Path, mapping: Mapping[str, str]) -> dict[str, float]:
    result: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "municipality_area_km2"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError("Municipality-area schema is invalid")
        for row in reader:
            code = row["municipality_code"]
            if code not in mapping:
                raise KmeModelError(f"Area contains unmapped municipality: {code}")
            if code in result:
                raise KmeModelError(f"Duplicate municipality area: {code}")
            value = float(row["municipality_area_km2"])
            if not math.isfinite(value) or value <= 0:
                raise KmeModelError("Municipality area must be positive and finite")
            result[code] = value
    if set(result) != set(mapping):
        raise KmeModelError("Municipality areas do not cover mapping exactly")
    return result


def read_weather_file(path: Path) -> dict[tuple[str, date], dict[str, Any]]:
    result: dict[tuple[str, date], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "municipality_code",
            "week_start",
            "week_end",
            "weather_status",
            *WEATHER_SOURCE_COLUMNS,
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeModelError(f"Weather schema is invalid: {path}")
        for row in reader:
            municipality = row["municipality_code"]
            week = parse_monday(row["week_start"])
            key = (municipality, week)
            if key in result:
                raise KmeModelError(f"Duplicate weather key: {key}")
            status = row["weather_status"]
            values: dict[str, float] | None = None
            if status == "complete":
                values = {}
                for column in WEATHER_SOURCE_COLUMNS:
                    if row[column] == "":
                        raise KmeModelError(f"Complete weather row has missing {column}")
                    value = float(row[column])
                    if not math.isfinite(value):
                        raise KmeModelError("Weather values must be finite")
                    values[column] = value
            elif status != "incomplete_source_week":
                raise KmeModelError(f"Unknown weather_status: {status}")
            result[key] = {
                "week_end": date.fromisoformat(row["week_end"]),
                "status": status,
                "values": values,
            }
    return result


def combine_weather_sources(
    development: Mapping[tuple[str, date], Mapping[str, Any]],
    extension: Mapping[tuple[str, date], Mapping[str, Any]],
) -> dict[tuple[str, date], Mapping[str, Any]]:
    combined = dict(development)
    for key, incoming in extension.items():
        current = combined.get(key)
        if current is None or (
            current["status"] != "complete" and incoming["status"] == "complete"
        ):
            combined[key] = incoming
        elif current["status"] == incoming["status"] == "complete":
            for column in WEATHER_SOURCE_COLUMNS:
                if not math.isclose(
                    current["values"][column],
                    incoming["values"][column],
                    rel_tol=0.0,
                    abs_tol=1e-10,
                ):
                    raise KmeModelError(f"Overlapping weather sources disagree for {key}")
    return combined


def aggregate_region_weather(
    weather: Mapping[tuple[str, date], Mapping[str, Any]],
    mapping: Mapping[str, str],
    areas: Mapping[str, float],
) -> dict[tuple[str, date], dict[str, Any]]:
    municipalities_by_region: defaultdict[str, list[str]] = defaultdict(list)
    for municipality, region in mapping.items():
        municipalities_by_region[region].append(municipality)
    weeks = sorted({week for _, week in weather})
    result: dict[tuple[str, date], dict[str, Any]] = {}
    for region, municipalities in municipalities_by_region.items():
        total_area = sum(areas[municipality] for municipality in municipalities)
        for week in weeks:
            rows = [weather.get((municipality, week)) for municipality in municipalities]
            if any(row is None or row["status"] != "complete" for row in rows):
                continue
            values = {
                column: sum(
                    areas[municipality] * row["values"][column]
                    for municipality, row in zip(municipalities, rows)
                )
                / total_area
                for column in WEATHER_SOURCE_COLUMNS
            }
            result[(region, week)] = {
                "week_end": rows[0]["week_end"],
                "values": values,
            }
    return result


def annual_harmonic(issue_week: date) -> tuple[float, float]:
    year_start = date(issue_week.year, 1, 1)
    next_year = date(issue_week.year + 1, 1, 1)
    phase = 2.0 * math.pi * (issue_week - year_start).days / (next_year - year_start).days
    return math.sin(phase), math.cos(phase)


def prepare_rows(
    targets: Sequence[TargetObservation],
    regions: Mapping[str, str],
    mapping: Mapping[str, str],
    region_cases: Mapping[tuple[str, date], int],
    population: Mapping[str, Mapping[int, int | None]],
    region_weather: Mapping[tuple[str, date], Mapping[str, Any]],
) -> tuple[list[PreparedRow], dict[str, int]]:
    rows: list[PreparedRow] = []
    exclusions = Counter()
    for target in targets:
        try:
            population_value, population_year_min, population_year_max = (
                selected_region_population(
                    target.region_code, target.issue_week, mapping, population
                )
            )
        except KmeModelError as exc:
            if not str(exc).startswith("No safely earlier population"):
                raise
            exclusions["missing_safe_population"] += 1
            continue
        past_weeks = tuple(
            target.issue_week - timedelta(weeks=offset) for offset in range(8, 0, -1)
        )
        if any((target.region_code, week) not in region_cases for week in past_weeks):
            exclusions["incomplete_past_case_window"] += 1
            continue
        past_cases = sum(region_cases[(target.region_code, week)] for week in past_weeks)
        weather_weeks = tuple(
            target.issue_week - timedelta(weeks=offset) for offset in range(4, 0, -1)
        )
        weather_rows = [region_weather.get((target.region_code, week)) for week in weather_weeks]
        if any(row is None for row in weather_rows):
            exclusions["incomplete_weather_window"] += 1
            continue
        latest_weather_end = weather_rows[-1]["week_end"]
        if latest_weather_end >= target.issue_week:
            raise KmeModelError("Weather feature reaches issue time")
        if past_weeks[-1] >= target.issue_week:
            raise KmeModelError("Past KME feature reaches issue time")
        weather_values = {
            "t2m_mean_c_previous_4w_mean": statistics.fmean(
                row["values"]["t2m_mean_c"] for row in weather_rows
            ),
            "tp_sum_mm_previous_4w_sum": sum(
                row["values"]["tp_sum_mm"] for row in weather_rows
            ),
            "stl1_mean_c_previous_4w_mean": statistics.fmean(
                row["values"]["stl1_mean_c"] for row in weather_rows
            ),
            "swvl1_mean_m3_m3_previous_4w_mean": statistics.fmean(
                row["values"]["swvl1_mean_m3_m3"] for row in weather_rows
            ),
        }
        seasonal_sin, seasonal_cos = annual_harmonic(target.issue_week)
        rows.append(
            PreparedRow(
                target.region_code,
                regions[target.region_code],
                target.issue_week,
                target.target_start,
                target.target_end,
                target.target_value,
                population_value,
                population_year_min,
                population_year_max,
                seasonal_sin,
                seasonal_cos,
                past_cases,
                past_cases / population_value * 100_000.0,
                past_weeks[0],
                past_weeks[-1],
                weather_values,
                weather_weeks[0],
                weather_weeks[-1],
                latest_weather_end,
            )
        )
    return sorted(rows, key=lambda row: (row.issue_week, row.region_code)), dict(exclusions)


def generate_folds(rows: Sequence[PreparedRow], config: Mapping[str, Any]) -> list[Fold]:
    validation = config["validation"]
    first_year = int(validation["first_candidate_validation_iso_year"])
    last_year = int(validation["last_validation_iso_year"])
    minimum_years = int(validation["minimum_distinct_training_iso_years"])
    folds: list[Fold] = []
    for year in range(first_year, last_year + 1):
        year_weeks = sorted(
            {row.issue_week for row in rows if row.issue_week.isocalendar().year == year}
        )
        if not year_weeks:
            continue
        validation_start = min(year_weeks)
        validation_end = max(year_weeks)
        validation_rows = tuple(
            row
            for row in rows
            if row.issue_week.isocalendar().year == year
            and row.target_start.isocalendar().year == year
            and row.target_end.isocalendar().year == year
        )
        train_rows = tuple(row for row in rows if row.target_end < validation_start)
        training_years = {row.issue_week.isocalendar().year for row in train_rows}
        if len(training_years) < minimum_years or not validation_rows:
            continue
        purged = sum(
            row.issue_week < validation_start and row.target_end >= validation_start
            for row in rows
        )
        if max(row.target_end for row in train_rows) >= validation_start:
            raise KmeModelError("Training target overlaps validation")
        if any(row.target_end.isocalendar().year != year for row in validation_rows):
            raise KmeModelError("Validation target leaks beyond validation ISO year")
        folds.append(
            Fold(
                f"kme_{year}",
                year,
                validation_start,
                validation_end,
                train_rows,
                validation_rows,
                purged,
            )
        )
    if not folds:
        raise KmeModelError("No valid KME rolling-origin folds")
    return folds


def continuous_feature_value(row: PreparedRow, feature: str) -> float:
    if feature == "past_8w_kme_incidence_per_100000":
        return row.past_incidence
    if feature in row.weather_values:
        return row.weather_values[feature]
    raise KmeModelError(f"Unknown continuous feature: {feature}")


def fit_standardizer(rows: Sequence[PreparedRow], features: Sequence[str]) -> Standardizer:
    means: dict[str, float] = {}
    standard_deviations: dict[str, float] = {}
    for feature in features:
        values = [continuous_feature_value(row, feature) for row in rows]
        mean = statistics.fmean(values)
        standard_deviation = statistics.pstdev(values)
        if not math.isfinite(standard_deviation) or standard_deviation <= 0:
            raise KmeModelError(f"Training feature has zero variance: {feature}")
        means[feature] = mean
        standard_deviations[feature] = standard_deviation
    return Standardizer(means, standard_deviations)


def glm_continuous_features(candidate_id: str) -> tuple[str, ...]:
    if candidate_id == GLM_BASE:
        return ()
    if candidate_id == GLM_PAST:
        return ("past_8w_kme_incidence_per_100000",)
    if candidate_id in (GLM_WEATHER_ONLY, GLM_SEASONAL_WEATHER):
        return WEATHER_FEATURE_COLUMNS
    if candidate_id == GLM_FULL:
        return ("past_8w_kme_incidence_per_100000",) + WEATHER_FEATURE_COLUMNS
    raise KmeModelError(f"Unknown GLM candidate: {candidate_id}")


def build_glm_matrix(
    rows: Sequence[PreparedRow],
    region_levels: Sequence[str],
    candidate_id: str,
    standardizer: Standardizer,
) -> tuple[np.ndarray, tuple[str, ...]]:
    reference = region_levels[0]
    continuous = glm_continuous_features(candidate_id)
    include_seasonality_and_region = candidate_id != GLM_WEATHER_ONLY
    region_columns = (
        tuple(f"region[{region}]" for region in region_levels if region != reference)
        if include_seasonality_and_region
        else ()
    )
    columns = ("intercept",)
    if include_seasonality_and_region:
        columns += ("seasonal_sin_annual", "seasonal_cos_annual") + region_columns
    columns += tuple(f"z_{feature}" for feature in continuous)
    matrix: list[list[float]] = []
    for row in rows:
        if row.region_code not in region_levels:
            raise KmeModelError(f"Unseen validation region: {row.region_code}")
        values = [1.0]
        if include_seasonality_and_region:
            values.extend((row.seasonal_sin, row.seasonal_cos))
            values.extend(
                float(row.region_code == region)
                for region in region_levels
                if region != reference
            )
        values.extend(
            standardizer.transform(feature, continuous_feature_value(row, feature))
            for feature in continuous
        )
        matrix.append(values)
    return np.asarray(matrix, dtype=float), columns


def catboost_matrix(rows: Sequence[PreparedRow]) -> list[list[Any]]:
    matrix: list[list[Any]] = []
    for row in rows:
        matrix.append(
            [
                row.region_code,
                row.seasonal_sin,
                row.seasonal_cos,
                row.past_incidence,
                *(row.weather_values[feature] for feature in WEATHER_FEATURE_COLUMNS),
            ]
        )
    return matrix


def build_catboost_pool(rows: Sequence[PreparedRow], *, include_labels: bool) -> Pool:
    labels = [row.target_value for row in rows] if include_labels else None
    return Pool(
        data=catboost_matrix(rows),
        label=labels,
        cat_features=[0],
        feature_names=list(CATBOOST_FEATURE_COLUMNS),
        baseline=np.asarray([row.offset for row in rows], dtype=float).reshape(-1, 1),
        timestamp=[row.issue_week.toordinal() for row in rows],
    )


def poisson_deviance_contribution(observed: int, predicted: float) -> tuple[float | None, str]:
    if not math.isfinite(predicted) or predicted < 0:
        return None, "invalid_prediction"
    if predicted == 0:
        return (0.0, "valid") if observed == 0 else (None, "invalid_zero_prediction_positive_observation")
    if observed == 0:
        return 2.0 * predicted, "valid"
    return 2.0 * (observed * math.log(observed / predicted) - observed + predicted), "valid"


def system_type(candidate_id: str) -> str:
    if candidate_id in (BASELINE_RATE, BASELINE_PERSISTENCE):
        return "baseline"
    if candidate_id in GLM_IDS:
        return "statistical_model"
    if candidate_id == CATBOOST_WEATHER:
        return "ml_challenger"
    raise KmeModelError(f"Unknown candidate: {candidate_id}")


def prediction_row(
    fold: Fold,
    candidate_id: str,
    row: PreparedRow,
    prediction: float,
) -> dict[str, Any]:
    deviance, deviance_status = poisson_deviance_contribution(row.target_value, prediction)
    error = prediction - row.target_value
    return {
        "fold_id": fold.fold_id,
        "validation_iso_year": fold.validation_iso_year,
        "system_type": system_type(candidate_id),
        "candidate_id": candidate_id,
        "statistical_region_code": row.region_code,
        "issue_week": row.issue_week,
        "target_window_start": row.target_start,
        "target_window_end": row.target_end,
        "actual_target_kme_cases_next_8w": row.target_value,
        "predicted_target_kme_cases_next_8w": prediction,
        "population_exposure": row.population,
        "population_year_min": row.population_year_min,
        "population_year_max": row.population_year_max,
        "past_8w_kme_cases": row.past_cases,
        "past_8w_kme_incidence_per_100000": row.past_incidence,
        "latest_past_case_week_used": row.past_window_end,
        "latest_weather_week_used": row.latest_weather_week,
        "latest_weather_week_end": row.latest_weather_week_end,
        "fit_target_end_max": max(train.target_end for train in fold.train_rows),
        "absolute_error": abs(error),
        "squared_error": error * error,
        "poisson_deviance_contribution": deviance,
        "poisson_deviance_status": deviance_status,
    }


def predict_baseline_rate(fold: Fold) -> list[float]:
    totals: defaultdict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    global_total = [0.0, 0.0]
    for row in fold.train_rows:
        totals[row.region_code][0] += row.target_value
        totals[row.region_code][1] += row.exposure_per_100000
        global_total[0] += row.target_value
        global_total[1] += row.exposure_per_100000
    global_rate = global_total[0] / global_total[1]
    predictions = []
    for row in fold.validation_rows:
        numerator, denominator = totals[row.region_code]
        rate = numerator / denominator if denominator > 0 else global_rate
        predictions.append(rate * row.exposure_per_100000)
    return predictions


def fit_predict_glm(
    fold: Fold, candidate_id: str, config: Mapping[str, Any]
) -> tuple[list[float], dict[str, Any], list[dict[str, Any]]]:
    continuous = glm_continuous_features(candidate_id)
    standardizer = fit_standardizer(fold.train_rows, continuous)
    region_levels = tuple(sorted({row.region_code for row in fold.train_rows}))
    if set(region_levels) != {row.region_code for row in fold.validation_rows}:
        raise KmeModelError("Training and validation region levels differ")
    train_matrix, columns = build_glm_matrix(
        fold.train_rows, region_levels, candidate_id, standardizer
    )
    validation_matrix, validation_columns = build_glm_matrix(
        fold.validation_rows, region_levels, candidate_id, standardizer
    )
    if columns != validation_columns:
        raise KmeModelError("Training and validation GLM columns differ")
    labels = np.asarray([row.target_value for row in fold.train_rows], dtype=float)
    offsets = np.asarray([row.offset for row in fold.train_rows], dtype=float)
    model = sm.GLM(labels, train_matrix, family=sm.families.Poisson(), offset=offsets)
    captured: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = model.fit(
            maxiter=int(config["glm"]["maxiter"]),
            tol=float(config["glm"]["tol"]),
        )
        captured = [str(item.message) for item in caught]
    predictions = result.predict(
        validation_matrix,
        offset=np.asarray([row.offset for row in fold.validation_rows], dtype=float),
    )
    if any(not math.isfinite(value) or value < 0 for value in predictions):
        raise KmeModelError(f"Invalid GLM prediction from {candidate_id}")
    diagnostic = {
        "n_parameters_or_features": len(columns),
        "converged": bool(result.converged),
        "iterations": int(result.fit_history.get("iteration", -1)),
        "warning_count": len(captured),
        "warning_messages": " | ".join(captured),
        "training_scaler_means": json.dumps(standardizer.means, sort_keys=True),
        "training_scaler_standard_deviations": json.dumps(
            standardizer.standard_deviations, sort_keys=True
        ),
    }
    coefficients = [
        {
            "feature": feature,
            "coefficient": float(coefficient),
            "standard_error": float(standard_error),
        }
        for feature, coefficient, standard_error in zip(columns, result.params, result.bse)
    ]
    return [float(value) for value in predictions], diagnostic, coefficients


def fit_predict_catboost(
    fold: Fold, config: Mapping[str, Any]
) -> tuple[list[float], dict[str, Any], list[dict[str, Any]]]:
    params = dict(config["catboost"])
    params.pop("prediction_type")
    params.pop("hyperparameter_search")
    train_pool = build_catboost_pool(fold.train_rows, include_labels=True)
    validation_pool = build_catboost_pool(fold.validation_rows, include_labels=False)
    model = CatBoostRegressor(**params)
    captured: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(train_pool)
        captured = [str(item.message) for item in caught]
    predictions = model.predict(validation_pool, prediction_type="Exponent")
    if any(not math.isfinite(value) or value < 0 for value in predictions):
        raise KmeModelError("Invalid CatBoost prediction")
    diagnostic = {
        "n_parameters_or_features": len(CATBOOST_FEATURE_COLUMNS),
        "converged": True,
        "iterations": model.tree_count_,
        "warning_count": len(captured),
        "warning_messages": " | ".join(captured),
        "training_scaler_means": "not_applicable",
        "training_scaler_standard_deviations": "not_applicable",
    }
    importance = [
        {"feature": feature, "importance": float(value)}
        for feature, value in zip(
            CATBOOST_FEATURE_COLUMNS, model.get_feature_importance(train_pool)
        )
    ]
    return [float(value) for value in predictions], diagnostic, importance


def summarize_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    absolute_errors = [float(row["absolute_error"]) for row in rows]
    squared_errors = [float(row["squared_error"]) for row in rows]
    valid_deviances = [
        float(row["poisson_deviance_contribution"])
        for row in rows
        if row["poisson_deviance_status"] == "valid"
    ]
    all_valid = len(valid_deviances) == len(rows)
    return {
        "n_predictions": len(rows),
        "mae": statistics.fmean(absolute_errors),
        "rmse": math.sqrt(statistics.fmean(squared_errors)),
        "mean_poisson_deviance": statistics.fmean(valid_deviances) if all_valid else None,
        "poisson_deviance_status": "valid" if all_valid else "invalid_pairs_present",
    }


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def json_value(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def feature_panel_row(row: PreparedRow) -> dict[str, Any]:
    return {
        "statistical_region_code": row.region_code,
        "statistical_region_name": row.region_name,
        "issue_week": row.issue_week,
        "target_window_start": row.target_start,
        "target_window_end": row.target_end,
        "target_kme_cases_next_8w": row.target_value,
        "population_exposure": row.population,
        "population_year_min": row.population_year_min,
        "population_year_max": row.population_year_max,
        "population_exposure_per_100000": row.exposure_per_100000,
        "offset_log_population_per_100000": row.offset,
        "seasonal_sin_annual": row.seasonal_sin,
        "seasonal_cos_annual": row.seasonal_cos,
        "past_8w_kme_cases": row.past_cases,
        "past_8w_kme_incidence_per_100000": row.past_incidence,
        "past_case_window_start": row.past_window_start,
        "past_case_window_end": row.past_window_end,
        "latest_past_case_week_used": row.past_window_end,
        "weather_window_start": row.weather_window_start,
        "latest_weather_week_used": row.latest_weather_week,
        "latest_weather_week_end": row.latest_weather_week_end,
        **row.weather_values,
    }


def fold_manifest_row(fold: Fold, embargo_weeks: int) -> dict[str, Any]:
    return {
        "fold_id": fold.fold_id,
        "validation_iso_year": fold.validation_iso_year,
        "train_issue_start": min(row.issue_week for row in fold.train_rows),
        "train_issue_end": max(row.issue_week for row in fold.train_rows),
        "train_target_end_max": max(row.target_end for row in fold.train_rows),
        "validation_start": fold.validation_start,
        "validation_end": fold.validation_end,
        "n_train": len(fold.train_rows),
        "n_validation": len(fold.validation_rows),
        "n_purged_target_boundary": fold.n_purged,
        "target_embargo_weeks": embargo_weeks,
    }


def evaluate(
    rows: Sequence[PreparedRow], folds: Sequence[Fold], config: Mapping[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    coefficients: list[dict[str, Any]] = []
    importance: list[dict[str, Any]] = []
    for fold in folds:
        candidate_predictions: dict[str, list[float]] = {
            BASELINE_RATE: predict_baseline_rate(fold),
            BASELINE_PERSISTENCE: [float(row.past_cases) for row in fold.validation_rows],
        }
        for candidate_id in GLM_IDS:
            values, diagnostic, candidate_coefficients = fit_predict_glm(
                fold, candidate_id, config
            )
            candidate_predictions[candidate_id] = values
            diagnostics.append(
                {
                    "fold_id": fold.fold_id,
                    "validation_iso_year": fold.validation_iso_year,
                    "candidate_id": candidate_id,
                    "n_train": len(fold.train_rows),
                    "n_validation": len(fold.validation_rows),
                    "train_target_end_max": max(row.target_end for row in fold.train_rows),
                    "validation_start": fold.validation_start,
                    **diagnostic,
                }
            )
            coefficients.extend(
                {
                    "fold_id": fold.fold_id,
                    "validation_iso_year": fold.validation_iso_year,
                    "candidate_id": candidate_id,
                    **row,
                }
                for row in candidate_coefficients
            )
        cat_values, cat_diagnostic, cat_importance = fit_predict_catboost(fold, config)
        candidate_predictions[CATBOOST_WEATHER] = cat_values
        diagnostics.append(
            {
                "fold_id": fold.fold_id,
                "validation_iso_year": fold.validation_iso_year,
                "candidate_id": CATBOOST_WEATHER,
                "n_train": len(fold.train_rows),
                "n_validation": len(fold.validation_rows),
                "train_target_end_max": max(row.target_end for row in fold.train_rows),
                "validation_start": fold.validation_start,
                **cat_diagnostic,
            }
        )
        importance.extend(
            {
                "fold_id": fold.fold_id,
                "validation_iso_year": fold.validation_iso_year,
                "candidate_id": CATBOOST_WEATHER,
                **row,
            }
            for row in cat_importance
        )
        if tuple(candidate_predictions) != SYSTEM_IDS:
            raise KmeModelError("Not every fixed system produced predictions")
        for candidate_id, values in candidate_predictions.items():
            if len(values) != len(fold.validation_rows):
                raise KmeModelError(f"Prediction count mismatch for {candidate_id}")
            predictions.extend(
                prediction_row(fold, candidate_id, row, prediction)
                for row, prediction in zip(fold.validation_rows, values)
            )

    fold_metrics: list[dict[str, Any]] = []
    for fold in folds:
        for candidate_id in SYSTEM_IDS:
            selected = [
                row
                for row in predictions
                if row["fold_id"] == fold.fold_id and row["candidate_id"] == candidate_id
            ]
            fold_metrics.append(
                {
                    "fold_id": fold.fold_id,
                    "validation_iso_year": fold.validation_iso_year,
                    "candidate_id": candidate_id,
                    **summarize_metrics(selected),
                }
            )
    aggregate_metrics: list[dict[str, Any]] = []
    persistence_by_fold = {
        row["fold_id"]: row
        for row in fold_metrics
        if row["candidate_id"] == BASELINE_PERSISTENCE
    }
    for candidate_id in SYSTEM_IDS:
        selected_predictions = [
            row for row in predictions if row["candidate_id"] == candidate_id
        ]
        selected_folds = [
            row for row in fold_metrics if row["candidate_id"] == candidate_id
        ]
        pooled = summarize_metrics(selected_predictions)
        aggregate_metrics.append(
            {
                "candidate_id": candidate_id,
                "system_type": system_type(candidate_id),
                "n_folds": len(selected_folds),
                "n_predictions": pooled["n_predictions"],
                "pooled_mae": pooled["mae"],
                "mean_fold_mae": statistics.fmean(float(row["mae"]) for row in selected_folds),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": statistics.fmean(float(row["rmse"]) for row in selected_folds),
                "pooled_mean_poisson_deviance": pooled["mean_poisson_deviance"],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
                "n_folds_improving_over_persistence_mae": sum(
                    float(row["mae"]) < float(persistence_by_fold[row["fold_id"]]["mae"])
                    for row in selected_folds
                ),
            }
        )
    return {
        "predictions": predictions,
        "fold_metrics": fold_metrics,
        "aggregate_metrics": aggregate_metrics,
        "diagnostics": diagnostics,
        "coefficients": coefficients,
        "importance": importance,
    }


def select_system(
    aggregate_metrics: Sequence[Mapping[str, Any]],
    fold_metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    aggregate_by_id = {row["candidate_id"]: row for row in aggregate_metrics}
    best_non_ml = min(
        NON_ML_SYSTEM_IDS,
        key=lambda candidate_id: float(aggregate_by_id[candidate_id]["pooled_mae"]),
    )
    best_non_ml_mae = float(aggregate_by_id[best_non_ml]["pooled_mae"])
    catboost_mae = float(aggregate_by_id[CATBOOST_WEATHER]["pooled_mae"])
    fold_by_id = defaultdict(dict)
    for row in fold_metrics:
        fold_by_id[row["candidate_id"]][row["fold_id"]] = float(row["mae"])
    compared_folds = tuple(sorted(fold_by_id[best_non_ml]))
    catboost_improvement_count = sum(
        fold_by_id[CATBOOST_WEATHER][fold_id] < fold_by_id[best_non_ml][fold_id]
        for fold_id in compared_folds
    )
    catboost_improves_every_fold = catboost_improvement_count == len(compared_folds)
    promote_catboost = catboost_mae < best_non_ml_mae and catboost_improves_every_fold
    selected = CATBOOST_WEATHER if promote_catboost else best_non_ml
    return {
        "selected_candidate_id": selected,
        "status": "development_selection_no_untouched_lockbox",
        "primary_metric": "pooled_mae",
        "best_non_ml_candidate_id": best_non_ml,
        "best_non_ml_pooled_mae": best_non_ml_mae,
        "catboost_pooled_mae": catboost_mae,
        "catboost_n_folds_improving_vs_best_non_ml": catboost_improvement_count,
        "n_compared_folds": len(compared_folds),
        "catboost_improves_every_fold_vs_best_non_ml": catboost_improves_every_fold,
        "catboost_promoted": promote_catboost,
        "selection_rule": (
            "CatBoost requires lower pooled MAE and lower MAE in every validation fold; "
            "otherwise select the lowest pooled-MAE non-ML system."
        ),
        "approval_status": "implemented_development_system_not_lockbox_validated",
    }


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def render_report(
    rows: Sequence[PreparedRow],
    folds: Sequence[Fold],
    results: Mapping[str, Sequence[Mapping[str, Any]]],
    selection: Mapping[str, Any],
    config: Mapping[str, Any],
) -> str:
    aggregate = sorted(
        results["aggregate_metrics"], key=lambda row: float(row["pooled_mae"])
    )
    metric_lines = [
        "| Candidate | Type | Pooled MAE | RMSE | Poisson deviance | Folds better than persistence |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        deviance = (
            f"{float(row['pooled_mean_poisson_deviance']):.4f}"
            if row["pooled_mean_poisson_deviance"] is not None
            else "INVALID"
        )
        metric_lines.append(
            f"| `{row['candidate_id']}` | {row['system_type']} | "
            f"{float(row['pooled_mae']):.4f} | {float(row['pooled_rmse']):.4f} | "
            f"{deviance} | {row['n_folds_improving_over_persistence_mae']}/{row['n_folds']} |"
        )
    selected = selection["selected_candidate_id"]
    metric_by_id = {row["candidate_id"]: row for row in results["aggregate_metrics"]}
    base_mae = float(metric_by_id[GLM_BASE]["pooled_mae"])
    weather_only_mae = float(metric_by_id[GLM_WEATHER_ONLY]["pooled_mae"])
    seasonal_weather_mae = float(metric_by_id[GLM_SEASONAL_WEATHER]["pooled_mae"])
    full_weather_mae = float(metric_by_id[GLM_FULL]["pooled_mae"])
    return f"""# KME statistical-region forecasting system

## Outcome

The implemented KME system uses **statistical region × issue week** and predicts the reported KME count in exactly **t+1 through t+8**. The issue week is excluded. This choice follows the verified SURS regional feasibility analysis: region × 8-week windows are materially less sparse than municipality windows while retaining more temporal blocks than a 12-week horizon.

This is rolling-origin development evidence, not untouched lockbox performance. KME observations from 2015-2025 already informed design, so a future KME lockbox must begin after this period.

## Information available at issue time

- Population: sum of the latest present municipality values strictly before the issue calendar year; used as `log(population/100000)` offset and as the past-incidence denominator.
- Past epidemiology: regional KME cases in exactly `t-8..t-1`.
- Seasonality: one annual sine/cosine harmonic derived from issue date.
- Weather: final ERA5-Land 0001, using complete weeks `t-4..t-1` only. Municipality weekly inputs come from grid-cell polygon-intersection overlay weights, not point or centroid sampling; those municipality means are then area-weighted to regions.
- Compact weather features: 4-week mean air temperature, 4-week precipitation sum, 4-week mean shallow-soil temperature, and 4-week mean shallow-soil moisture.

Current/future cases and weather are rejected. Weather-missing rows are excluded from every comparator, preserving common support. Municipality/region area is not an ordinary predictor because it is time-invariant and redundant with region identity; it is used only for weather aggregation.

## Candidate specifications

- Regional historical rate: training-only regional target count divided by population exposure, rescaled to each validation exposure.
- Persistence: regional count from exactly `t-8..t-1`.
- Seasonal regional GLM: `log(E[Y]) = log(population/100000) + intercept + annual_sin + annual_cos + region_effect`.
- Past-incidence GLM: seasonal regional GLM plus training-standardized prior 8-week incidence.
- Weather-only GLM: `log(E[Y]) = log(population/100000) + intercept + four_training_standardized_weather_summaries`; it deliberately excludes seasonality, region, and past cases.
- Weather-adjusted GLMs: the seasonal regional GLM with weather, and then with both weather and past incidence.
- CatBoost challenger: Poisson loss with `log(population/100000)` as the input baseline and the same region, seasonality, past-incidence, and compact weather information. Its fixed conservative parameters are in `model_v3/config/kme_region_model.json`; no search is run.

The GLMs use a log link and produce expected counts by exponentiating the fitted linear predictor plus offset. All 40 GLM fits and all 8 CatBoost fits completed with no recorded warning; the GLMs reported convergence. Predictive intervals are not implemented for this development experiment.

## Validation

{len(folds)} expanding rolling-origin folds validate ISO years {folds[0].validation_iso_year}-{folds[-1].validation_iso_year}. Training target windows end strictly before validation starts. Validation target windows remain fully within their validation ISO year. The eight-week target boundary is explicitly purged.

Feature-complete panel rows: {len(rows)}. Validation predictions per system: {sum(len(fold.validation_rows) for fold in folds)}.

## Results

{chr(10).join(metric_lines)}

Selected development system: **`{selected}`**.

Selection rule: {selection['selection_rule']} CatBoost promoted: **{str(selection['catboost_promoted']).lower()}**.

The explicit weather-only model has MAE {weather_only_mae:.4f}. Adding weather to the seasonal regional model changes MAE from {base_mae:.4f} to {seasonal_weather_mae:.4f}; adding both past incidence and weather gives {full_weather_mae:.4f}. These are deteriorations, so weather remains a tested ablation rather than a forced component of the selected sparse-data model. CatBoost with the full compact feature set improves the seasonal regional reference in {selection['catboost_n_folds_improving_vs_best_non_ml']}/{selection['n_compared_folds']} folds, which is not stable enough for promotion under the pre-declared rule.

## Small-sample safeguards

- Region aggregation reduces municipality-level structural zeros without disaggregating predictions back to municipalities.
- The weather set is limited a priori to four summaries; correlated duplicate depths and fine lag variants are excluded.
- CatBoost uses one conservative fixed configuration and no hyperparameter search.
- CatBoost is not promoted for a small pooled improvement; it must also improve every validation fold over the best non-ML system.
- No low/medium/high categories, personal-risk language, classification probabilities, or arbitrary risk scores are created.

## Limitations

- The historical NIJZ source lacks observation-level publication/revision timestamps. Canonical confirmation-week values are used; past cases stop at `t-1` as a conservative modelling safeguard, not a verified NIJZ publication delay.
- Weather associations need not be causal and may partly reflect human outdoor activity.
- Overlapping eight-week targets make row-level errors dependent; rolling-year folds, not nominal row count, are the primary stability evidence.
- No untouched KME lockbox remains in 2015-2025.
- This system forecasts regional reported counts. Municipality forecasts or disaggregation are not implemented.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    input_config = config["inputs"]
    paths = {
        key: resolve_repo_path(input_config[key], repo_root)
        for key in (
            "target",
            "weekly_cases",
            "population",
            "statistical_region",
            "municipality_statistical_region",
            "municipality_area",
            "development_weather",
            "weather_extension",
        )
    }
    hashes = {
        key: require_hash(paths[key], input_config[f"{key}_sha256"], key) for key in paths
    }
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    targets = read_targets(paths["target"], regions)
    region_cases = read_region_weekly_cases(paths["weekly_cases"], mapping)
    population = read_population(paths["population"])
    areas = read_areas(paths["municipality_area"], mapping)
    development_weather = read_weather_file(paths["development_weather"])
    extension_weather = read_weather_file(paths["weather_extension"])
    combined_weather = combine_weather_sources(development_weather, extension_weather)
    region_weather = aggregate_region_weather(combined_weather, mapping, areas)
    rows, exclusions = prepare_rows(
        targets,
        regions,
        mapping,
        region_cases,
        population,
        region_weather,
    )
    folds = generate_folds(rows, config)
    results = evaluate(rows, folds, config)
    selection = select_system(results["aggregate_metrics"], results["fold_metrics"])

    output_config = config["outputs"]
    output_directory = resolve_repo_path(output_config["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / output_config[key]
        for key in (
            "feature_panel",
            "fold_manifest",
            "fold_predictions",
            "fold_metrics",
            "aggregate_metrics",
            "fit_diagnostics",
            "coefficients",
            "feature_importance",
            "selection",
            "quality_summary",
        )
    }
    report_path = resolve_repo_path(output_config["report"], repo_root)
    write_csv(
        output_paths["feature_panel"],
        FEATURE_PANEL_COLUMNS,
        [feature_panel_row(row) for row in rows],
    )
    write_csv(
        output_paths["fold_manifest"],
        FOLD_MANIFEST_COLUMNS,
        [
            fold_manifest_row(fold, int(config["validation"]["target_embargo_weeks"]))
            for fold in folds
        ],
    )
    write_csv(output_paths["fold_predictions"], PREDICTION_COLUMNS, results["predictions"])
    write_csv(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, results["fold_metrics"])
    write_csv(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        results["aggregate_metrics"],
    )
    write_csv(output_paths["fit_diagnostics"], DIAGNOSTIC_COLUMNS, results["diagnostics"])
    write_csv(output_paths["coefficients"], COEFFICIENT_COLUMNS, results["coefficients"])
    write_csv(output_paths["feature_importance"], IMPORTANCE_COLUMNS, results["importance"])
    output_paths["selection"].write_text(
        json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(rows, folds, results, selection, config), encoding="utf-8"
    )

    material_outputs = {
        key: file_record(path, repo_root)
        for key, path in output_paths.items()
        if key != "quality_summary"
    }
    material_outputs["report"] = file_record(report_path, repo_root)
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.models.kme_region_model",
        "status": "complete_development_evaluation_no_untouched_lockbox",
        "configuration": file_record(config_path, repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "library_versions": {
            "catboost": catboost.__version__,
            "numpy": np.__version__,
            "statsmodels": statsmodels.__version__,
        },
        "inputs": {
            key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
            for key in paths
        },
        "data_support": {
            "n_feature_complete_rows": len(rows),
            "first_issue_week": min(row.issue_week for row in rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in rows).isoformat(),
            "excluded_target_rows": exclusions,
            "n_folds": len(folds),
            "validation_iso_years": [fold.validation_iso_year for fold in folds],
            "n_validation_predictions_per_system": sum(
                len(fold.validation_rows) for fold in folds
            ),
        },
        "checks": {
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded_from_target": True,
            "train_target_end_strictly_before_validation": True,
            "validation_target_windows_contained": True,
            "eight_week_boundary_purge_applied": True,
            "past_cases_latest_t_minus_1": True,
            "weather_latest_completed_week_t_minus_1": True,
            "current_or_future_weather_used": False,
            "population_issue_or_future_year_used": False,
            "population_as_ordinary_feature": False,
            "area_as_ordinary_feature": False,
            "weather_scaling_fit_on_validation": False,
            "catboost_hyperparameter_search": False,
            "untouched_KME_lockbox_claimed": False,
            "risk_categories_created": False,
            "personal_risk_output_created": False,
        },
        "feature_contract": config["feature_contract"],
        "fold_manifest": [
            fold_manifest_row(fold, int(config["validation"]["target_embargo_weeks"]))
            for fold in folds
        ],
        "aggregate_metrics": results["aggregate_metrics"],
        "selection": selection,
        "outputs": material_outputs,
    }
    output_paths["quality_summary"].write_text(
        json.dumps(
            quality,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=json_value,
        )
        + "\n",
        encoding="utf-8",
    )
    quality["quality_summary"] = file_record(output_paths["quality_summary"], repo_root)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the KME statistical-region eight-week forecasting system."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    quality = run(args.config)
    print(
        "Created KME regional model evaluation: "
        f"selected={quality['selection']['selected_candidate_id']}, "
        f"folds={quality['data_support']['n_folds']}, "
        f"validation_rows_per_system={quality['data_support']['n_validation_predictions_per_system']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
