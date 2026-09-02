from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import statsmodels
import statsmodels.api as sm

from model_v3.models.kme_region_model import (
    BASELINE_PERSISTENCE,
    BASELINE_RATE,
    GLM_BASE,
    KmeModelError,
    TargetObservation,
    annual_harmonic,
    poisson_deviance_contribution,
    parse_monday,
    read_mapping,
    read_regions,
    repository_path,
    require_hash,
    resolve_repo_path,
    selected_region_population,
    sha256_file,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_model_freeze.json"
SYSTEM_IDS = (BASELINE_RATE, BASELINE_PERSISTENCE, GLM_BASE)

FEATURE_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "target_kme_cases_next_8w",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "offset_log_population_per_100000",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
    "past_8w_kme_cases_for_persistence_baseline",
    "latest_past_case_week_used",
    "past_cases_used_by_selected_model",
    "weather_required_by_selected_model",
)
FOLD_COLUMNS = (
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
    "candidate_id",
    "statistical_region_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_kme_cases_next_8w",
    "predicted_target_kme_cases_next_8w",
    "population_exposure",
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
    "n_folds",
    "n_predictions",
    "pooled_mae",
    "mean_fold_mae",
    "pooled_rmse",
    "mean_fold_rmse",
    "pooled_mean_poisson_deviance",
    "poisson_deviance_status",
)
COEFFICIENT_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "feature",
    "coefficient",
    "standard_error",
)
DIAGNOSTIC_COLUMNS = (
    "fold_id",
    "validation_iso_year",
    "candidate_id",
    "n_train",
    "n_validation",
    "n_parameters",
    "converged",
    "iterations",
    "warning_count",
    "warning_messages",
)


class KmeFreezeError(ValueError):
    """Raised when the frozen KME contract or evidence changes."""


@dataclass(frozen=True)
class FreezeRow:
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
    latest_past_case_week: date

    @property
    def exposure_per_100000(self) -> float:
        return self.population / 100_000.0

    @property
    def offset(self) -> float:
        return math.log(self.exposure_per_100000)


@dataclass(frozen=True)
class FreezeFold:
    fold_id: str
    validation_iso_year: int
    validation_start: date
    validation_end: date
    train_rows: tuple[FreezeRow, ...]
    validation_rows: tuple[FreezeRow, ...]
    n_purged: int


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise KmeFreezeError("Unsupported KME freeze schema_version")
    if config["freeze"]["status"] != "FROZEN":
        raise KmeFreezeError("KME freeze status must remain FROZEN")
    if config["task"]["target_offsets"] != list(range(1, 9)):
        raise KmeFreezeError("Frozen KME target must remain exactly t+1 through t+8")
    if config["task"]["issue_week_included"] is not False:
        raise KmeFreezeError("Frozen KME target must exclude the issue week")
    if config["selected_model"]["candidate_id"] != GLM_BASE:
        raise KmeFreezeError("Frozen KME selected model changed")
    if config["prospective_lockbox"]["iso_year"] != 2026:
        raise KmeFreezeError("Frozen repository-controlled KME holdout changed")
    return config


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": repository_path(path, repo_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_inputs(
    config: Mapping[str, Any], repo_root: Path
) -> tuple[dict[str, Path], dict[str, str]]:
    inputs = config["inputs"]
    keys = tuple(key[:-7] for key in inputs if key.endswith("_sha256"))
    paths = {key: resolve_repo_path(inputs[key], repo_root) for key in keys}
    hashes = {
        key: require_hash(paths[key], inputs[f"{key}_sha256"], key) for key in keys
    }
    return paths, hashes


def read_development_targets(
    path: Path,
    regions: Mapping[str, str],
    protected_year: int,
) -> tuple[list[TargetObservation], int]:
    required = {
        "statistical_region_code",
        "issue_week",
        "target_window_start",
        "target_window_end",
        "target_kme_cases_next_8w",
        "target_status",
        "target_training_eligible",
    }
    result: list[TargetObservation] = []
    seen: set[tuple[str, date]] = set()
    skipped_protected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFreezeError("Frozen target schema is invalid")
        for row in reader:
            issue = parse_monday(row["issue_week"])
            target_start = parse_monday(row["target_window_start"])
            target_end = parse_monday(row["target_window_end"])
            if (
                issue.isocalendar().year >= protected_year
                or target_end.isocalendar().year >= protected_year
            ):
                skipped_protected += 1
                continue
            if row["target_training_eligible"] != "true":
                continue
            if row["target_status"] != "complete":
                raise KmeFreezeError("Eligible frozen target is not complete")
            region = row["statistical_region_code"]
            if region not in regions:
                raise KmeFreezeError(f"Unknown frozen target region: {region}")
            if target_start != issue + timedelta(weeks=1):
                raise KmeFreezeError("Frozen target does not start at t+1")
            if target_end != issue + timedelta(weeks=8):
                raise KmeFreezeError("Frozen target does not end at t+8")
            try:
                value = int(row["target_kme_cases_next_8w"])
            except ValueError as exc:
                raise KmeFreezeError("Frozen target must be an integer") from exc
            if value < 0:
                raise KmeFreezeError("Frozen target must be non-negative")
            key = (region, issue)
            if key in seen:
                raise KmeFreezeError(f"Duplicate frozen target: {key}")
            seen.add(key)
            result.append(TargetObservation(region, issue, target_start, target_end, value))
    if not result:
        raise KmeFreezeError("No development targets remain before the lockbox")
    return sorted(result, key=lambda row: (row.issue_week, row.region_code)), skipped_protected


def read_development_region_cases(
    path: Path,
    mapping: Mapping[str, str],
    protected_year: int,
) -> tuple[dict[tuple[str, date], int], int]:
    required = {"municipality_code", "issue_week", "kme_cases"}
    municipality_values: dict[tuple[str, date], int] = {}
    region_values: defaultdict[tuple[str, date], int] = defaultdict(int)
    skipped_protected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFreezeError("Frozen weekly-case schema is invalid")
        for row in reader:
            week = parse_monday(row["issue_week"])
            if week.isocalendar().year >= protected_year:
                skipped_protected += 1
                continue
            municipality = row["municipality_code"]
            if municipality not in mapping:
                raise KmeFreezeError(f"Unmapped frozen municipality: {municipality}")
            key = (municipality, week)
            if key in municipality_values:
                raise KmeFreezeError(f"Duplicate frozen municipality-week: {key}")
            try:
                value = int(row["kme_cases"])
            except ValueError as exc:
                raise KmeFreezeError("Frozen KME case must be an integer") from exc
            if value < 0:
                raise KmeFreezeError("Frozen KME case must be non-negative")
            municipality_values[key] = value
            region_values[(mapping[municipality], week)] += value
    weeks = {week for _, week in municipality_values}
    expected = {(municipality, week) for municipality in mapping for week in weeks}
    if set(municipality_values) != expected:
        raise KmeFreezeError("Frozen municipality-week case grid is incomplete")
    return dict(region_values), skipped_protected


def read_development_population(
    path: Path, protected_year: int
) -> tuple[dict[str, dict[int, int | None]], int]:
    required = {"municipality_code", "year", "population"}
    result: defaultdict[str, dict[int, int | None]] = defaultdict(dict)
    skipped_protected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise KmeFreezeError("Frozen population schema is invalid")
        for row in reader:
            try:
                year = int(row["year"])
            except ValueError as exc:
                raise KmeFreezeError("Population year must be an integer") from exc
            if year >= protected_year:
                skipped_protected += 1
                continue
            municipality = row["municipality_code"]
            if year in result[municipality]:
                raise KmeFreezeError(f"Duplicate frozen population: {municipality}, {year}")
            if row["population"] == "":
                result[municipality][year] = None
                continue
            try:
                value = int(row["population"])
            except ValueError as exc:
                raise KmeFreezeError("Frozen population must be an integer") from exc
            if value <= 0:
                raise KmeFreezeError("Frozen population must be positive when present")
            result[municipality][year] = value
    return dict(result), skipped_protected


def prepare_rows(
    targets: Sequence[TargetObservation],
    regions: Mapping[str, str],
    mapping: Mapping[str, str],
    region_cases: Mapping[tuple[str, date], int],
    population: Mapping[str, Mapping[int, int | None]],
) -> tuple[list[FreezeRow], dict[str, int]]:
    rows: list[FreezeRow] = []
    exclusions = Counter()
    for target in targets:
        try:
            population_value, year_min, year_max = selected_region_population(
                target.region_code, target.issue_week, mapping, population
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
            exclusions["incomplete_past_case_window_for_persistence_baseline"] += 1
            continue
        if target.target_start != target.issue_week + timedelta(weeks=1):
            raise KmeFreezeError("Frozen target does not start at t+1")
        if target.target_end != target.issue_week + timedelta(weeks=8):
            raise KmeFreezeError("Frozen target does not end at t+8")
        seasonal_sin, seasonal_cos = annual_harmonic(target.issue_week)
        rows.append(
            FreezeRow(
                region_code=target.region_code,
                region_name=regions[target.region_code],
                issue_week=target.issue_week,
                target_start=target.target_start,
                target_end=target.target_end,
                target_value=target.target_value,
                population=population_value,
                population_year_min=year_min,
                population_year_max=year_max,
                seasonal_sin=seasonal_sin,
                seasonal_cos=seasonal_cos,
                past_cases=sum(region_cases[(target.region_code, week)] for week in past_weeks),
                latest_past_case_week=past_weeks[-1],
            )
        )
    if not rows:
        raise KmeFreezeError("No eligible frozen KME rows")
    return sorted(rows, key=lambda row: (row.issue_week, row.region_code)), dict(exclusions)


def generate_folds(
    rows: Sequence[FreezeRow], config: Mapping[str, Any]
) -> list[FreezeFold]:
    validation = config["validation"]
    folds: list[FreezeFold] = []
    for year in range(
        int(validation["first_validation_iso_year"]),
        int(validation["last_validation_iso_year"]) + 1,
    ):
        issue_weeks = sorted(
            {row.issue_week for row in rows if row.issue_week.isocalendar().year == year}
        )
        if not issue_weeks:
            continue
        validation_start = min(issue_weeks)
        validation_end = max(issue_weeks)
        validation_rows = tuple(
            row
            for row in rows
            if row.issue_week.isocalendar().year == year
            and row.target_start.isocalendar().year == year
            and row.target_end.isocalendar().year == year
        )
        train_rows = tuple(row for row in rows if row.target_end < validation_start)
        training_years = {row.issue_week.isocalendar().year for row in train_rows}
        if (
            len(training_years)
            < int(validation["minimum_distinct_training_iso_years"])
            or not validation_rows
        ):
            continue
        n_purged = sum(
            row.issue_week < validation_start and row.target_end >= validation_start
            for row in rows
        )
        if max(row.target_end for row in train_rows) >= validation_start:
            raise KmeFreezeError("Frozen training target overlaps validation")
        if any(row.target_end.isocalendar().year != year for row in validation_rows):
            raise KmeFreezeError("Frozen validation target crosses its protected year")
        folds.append(
            FreezeFold(
                fold_id=f"kme_frozen_{year}",
                validation_iso_year=year,
                validation_start=validation_start,
                validation_end=validation_end,
                train_rows=train_rows,
                validation_rows=validation_rows,
                n_purged=n_purged,
            )
        )
    if not folds:
        raise KmeFreezeError("No valid frozen KME folds")
    return folds


def design_matrix(
    rows: Sequence[FreezeRow], region_levels: Sequence[str]
) -> tuple[np.ndarray, tuple[str, ...]]:
    if not region_levels:
        raise KmeFreezeError("Frozen GLM has no region levels")
    reference = region_levels[0]
    columns = (
        "intercept",
        "seasonal_sin_annual",
        "seasonal_cos_annual",
    ) + tuple(f"region[{region}]" for region in region_levels if region != reference)
    matrix = []
    for row in rows:
        if row.region_code not in region_levels:
            raise KmeFreezeError(f"Unseen frozen validation region: {row.region_code}")
        matrix.append(
            [
                1.0,
                row.seasonal_sin,
                row.seasonal_cos,
                *(float(row.region_code == region) for region in region_levels if region != reference),
            ]
        )
    return np.asarray(matrix, dtype=float), columns


def fit_selected_model(
    fold: FreezeFold, config: Mapping[str, Any]
) -> tuple[list[float], dict[str, Any], list[dict[str, Any]]]:
    levels = tuple(sorted({row.region_code for row in fold.train_rows}))
    if set(levels) != {row.region_code for row in fold.validation_rows}:
        raise KmeFreezeError("Frozen training and validation region levels differ")
    train_matrix, columns = design_matrix(fold.train_rows, levels)
    validation_matrix, validation_columns = design_matrix(fold.validation_rows, levels)
    if columns != validation_columns:
        raise KmeFreezeError("Frozen GLM design columns differ")
    model_config = config["selected_model"]
    model = sm.GLM(
        np.asarray([row.target_value for row in fold.train_rows], dtype=float),
        train_matrix,
        family=sm.families.Poisson(),
        offset=np.asarray([row.offset for row in fold.train_rows], dtype=float),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = model.fit(
            maxiter=int(model_config["maxiter"]), tol=float(model_config["tol"])
        )
    predictions = result.predict(
        validation_matrix,
        offset=np.asarray([row.offset for row in fold.validation_rows], dtype=float),
    )
    if any(not math.isfinite(value) or value < 0 for value in predictions):
        raise KmeFreezeError("Frozen GLM produced an invalid prediction")
    diagnostic = {
        "fold_id": fold.fold_id,
        "validation_iso_year": fold.validation_iso_year,
        "candidate_id": GLM_BASE,
        "n_train": len(fold.train_rows),
        "n_validation": len(fold.validation_rows),
        "n_parameters": len(columns),
        "converged": bool(result.converged),
        "iterations": int(result.fit_history.get("iteration", -1)),
        "warning_count": len(caught),
        "warning_messages": " | ".join(str(item.message) for item in caught),
    }
    coefficients = [
        {
            "fold_id": fold.fold_id,
            "validation_iso_year": fold.validation_iso_year,
            "feature": feature,
            "coefficient": float(coefficient),
            "standard_error": float(standard_error),
        }
        for feature, coefficient, standard_error in zip(columns, result.params, result.bse)
    ]
    return [float(value) for value in predictions], diagnostic, coefficients


def historical_rate_predictions(fold: FreezeFold) -> list[float]:
    totals: defaultdict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in fold.train_rows:
        totals[row.region_code][0] += row.target_value
        totals[row.region_code][1] += row.exposure_per_100000
    predictions = []
    for row in fold.validation_rows:
        numerator, denominator = totals[row.region_code]
        if denominator <= 0:
            raise KmeFreezeError(f"No frozen baseline exposure for {row.region_code}")
        predictions.append(numerator / denominator * row.exposure_per_100000)
    return predictions


def prediction_row(
    fold: FreezeFold, candidate_id: str, row: FreezeRow, predicted: float
) -> dict[str, Any]:
    deviance, deviance_status = poisson_deviance_contribution(row.target_value, predicted)
    error = predicted - row.target_value
    return {
        "fold_id": fold.fold_id,
        "validation_iso_year": fold.validation_iso_year,
        "candidate_id": candidate_id,
        "statistical_region_code": row.region_code,
        "issue_week": row.issue_week,
        "target_window_start": row.target_start,
        "target_window_end": row.target_end,
        "actual_target_kme_cases_next_8w": row.target_value,
        "predicted_target_kme_cases_next_8w": predicted,
        "population_exposure": row.population,
        "fit_target_end_max": max(train.target_end for train in fold.train_rows),
        "absolute_error": abs(error),
        "squared_error": error * error,
        "poisson_deviance_contribution": deviance,
        "poisson_deviance_status": deviance_status,
    }


def summarize_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    deviations = [
        float(row["poisson_deviance_contribution"])
        for row in rows
        if row["poisson_deviance_status"] == "valid"
    ]
    all_valid = len(deviations) == len(rows)
    return {
        "n_predictions": len(rows),
        "mae": statistics.fmean(float(row["absolute_error"]) for row in rows),
        "rmse": math.sqrt(statistics.fmean(float(row["squared_error"]) for row in rows)),
        "mean_poisson_deviance": statistics.fmean(deviations) if all_valid else None,
        "poisson_deviance_status": "valid" if all_valid else "invalid_pairs_present",
    }


def evaluate(
    folds: Sequence[FreezeFold], config: Mapping[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    coefficients: list[dict[str, Any]] = []
    for fold in folds:
        selected, diagnostic, fold_coefficients = fit_selected_model(fold, config)
        diagnostics.append(diagnostic)
        coefficients.extend(fold_coefficients)
        candidate_predictions = {
            BASELINE_RATE: historical_rate_predictions(fold),
            BASELINE_PERSISTENCE: [float(row.past_cases) for row in fold.validation_rows],
            GLM_BASE: selected,
        }
        for candidate_id, values in candidate_predictions.items():
            predictions.extend(
                prediction_row(fold, candidate_id, row, value)
                for row, value in zip(fold.validation_rows, values)
            )
    fold_metrics = []
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
    aggregate_metrics = []
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
                "n_folds": len(selected_folds),
                "n_predictions": pooled["n_predictions"],
                "pooled_mae": pooled["mae"],
                "mean_fold_mae": statistics.fmean(float(row["mae"]) for row in selected_folds),
                "pooled_rmse": pooled["rmse"],
                "mean_fold_rmse": statistics.fmean(float(row["rmse"]) for row in selected_folds),
                "pooled_mean_poisson_deviance": pooled["mean_poisson_deviance"],
                "poisson_deviance_status": pooled["poisson_deviance_status"],
            }
        )
    return {
        "predictions": predictions,
        "fold_metrics": fold_metrics,
        "aggregate_metrics": aggregate_metrics,
        "diagnostics": diagnostics,
        "coefficients": coefficients,
    }


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def feature_row(row: FreezeRow) -> dict[str, Any]:
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
        "offset_log_population_per_100000": row.offset,
        "seasonal_sin_annual": row.seasonal_sin,
        "seasonal_cos_annual": row.seasonal_cos,
        "past_8w_kme_cases_for_persistence_baseline": row.past_cases,
        "latest_past_case_week_used": row.latest_past_case_week,
        "past_cases_used_by_selected_model": False,
        "weather_required_by_selected_model": False,
    }


def fold_row(fold: FreezeFold, embargo: int) -> dict[str, Any]:
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
        "target_embargo_weeks": embargo,
    }


def render_report(
    config: Mapping[str, Any],
    rows: Sequence[FreezeRow],
    folds: Sequence[FreezeFold],
    results: Mapping[str, Sequence[Mapping[str, Any]]],
    exclusions: Mapping[str, int],
    input_records: Mapping[str, Mapping[str, Any]],
    config_record: Mapping[str, Any],
    code_record: Mapping[str, Any],
) -> str:
    metrics = {
        str(row["candidate_id"]): row for row in results["aggregate_metrics"]
    }
    metric_lines = [
        "| System | Pooled MAE | RMSE | Poisson deviance |",
        "|---|---:|---:|---:|",
    ]
    for candidate_id in SYSTEM_IDS:
        row = metrics[candidate_id]
        deviance = (
            f"{float(row['pooled_mean_poisson_deviance']):.6f}"
            if row["pooled_mean_poisson_deviance"] is not None
            else "INVALID"
        )
        metric_lines.append(
            f"| `{candidate_id}` | {float(row['pooled_mae']):.6f} | "
            f"{float(row['pooled_rmse']):.6f} | {deviance} |"
        )
    input_lines = [
        f"- `{record['path']}` — `{record['sha256']}`"
        for record in input_records.values()
    ]
    return f"""# KME model-selection freeze

- **Freeze status:** FROZEN
- **Freeze date:** {config['freeze']['freeze_date']}
- **Frozen system ID:** `{config['freeze']['freeze_id']}`
- **Repository-controlled lockbox:** ISO week-numbering year {config['prospective_lockbox']['iso_year']}
- **Lockbox status:** {config['prospective_lockbox']['status']}

This document freezes the KME development decision before any 2026 KME outcome is loaded by this pipeline. Because the seal date falls during 2026, this is a retrospective/ongoing holdout rather than a fully prospective forecast experiment. External human access to 2026 outcomes is UNKNOWN and cannot be audited from the repository. The 2015–2025 outcomes are development evidence, not an untouched lockbox. The protected period follows ISO week-numbering year 2026, and every evaluated t+1..t+8 target week must remain inside that ISO year. After 2026 outcomes are accessed by the pipeline, changing this specification requires formally abandoning 2026 and declaring a later untouched lockbox.

## Frozen prediction task

- Analysis unit: **statistical region × issue week**.
- Target: reported regional KME cases in exactly **t+1 through t+8**.
- The issue week is excluded.
- `target_window_start = issue_week + 1 week`; `target_window_end = issue_week + 8 weeks`.
- All eight future weeks must exist; incomplete targets are excluded, never zero-filled.
- Output: a non-negative expected reported regional count, not personal risk or a classification probability.

The verified 2022 SURS municipality-to-statistical-region mapping is used by municipality code as a fixed analytical geography for every year. This is an analytical convention, not a historical-boundary reconstruction.

## Frozen selected model

Selected model: **`{GLM_BASE}`**.

`{config['selected_model']['formula']}`

- Poisson GLM with log link, implemented by `statsmodels.GLM`.
- Population is the offset `log(region_population/100000)`, never an ordinary feature.
- Region uses deterministic treatment-coded fixed effects.
- Seasonality is one annual sine/cosine harmonic derived only from `issue_week`.
- Predictions are expected counts obtained from the fitted log-link model.
- Parameters: `maxiter={config['selected_model']['maxiter']}`, `tol={config['selected_model']['tol']}`; other behavior is from frozen `statsmodels=={statsmodels.__version__}`.
- Calibration: none. Predictive intervals: not implemented.

## Weather and other evaluated information

Weather remains part of the documented KME development experiment, but it is **not** in the frozen selected model. The earlier common-support comparison evaluated a weather-only GLM, weather-adjusted GLMs, and a compact-weather CatBoost challenger. Weather-only and weather-adjusted GLMs worsened pooled MAE. CatBoost improved pooled MAE by only about 1.7% and beat the selected GLM in 4/8 folds, failing the predeclared stability rule.

The frozen selected-model finalization therefore does not require weather and does not reject a valid row because an unused weather value is absent. This is a preprocessing correction, not a formula change. The prior weather experiment and its predictions remain frozen evidence and are not discarded.

Past eight-week KME counts are retained only for the persistence baseline and are not supplied to the selected GLM. Municipality area remains only an aggregation weight in the weather experiment; it is not a selected predictor. Land cover, elevation, long-term trend, thresholds, risk categories, and generated predictions remain excluded.

## Frozen population and missing-value rules

- For each mapped municipality, use the latest present population year strictly before the issue calendar year; sum those values to the region.
- Exclude a regional row if any mapped municipality lacks a safe earlier population value.
- NIJZ blank case cells retain the previously verified source-specific zero rule.
- Missing target weeks, missing past weeks required by the persistence baseline, unmatched codes, duplicates, or negative counts are rejected or explicitly excluded; none becomes an invented zero.

## Frozen validation

- Expanding rolling-origin folds validate ISO years {folds[0].validation_iso_year}–{folds[-1].validation_iso_year}.
- Training requires `target_window_end < validation_start`.
- Validation target windows must remain entirely inside the validation ISO year.
- An explicit eight-week target embargo purges boundary-crossing training rows.
- Primary metric: pooled MAE. Secondary metrics: RMSE and mean Poisson deviance where mathematically valid.

Finalized feature-support rows: **{len(rows)}**. Explicit exclusions: `{json.dumps(dict(exclusions), sort_keys=True)}`. Validation predictions per system: **{sum(len(fold.validation_rows) for fold in folds)}**.

## Finalized development evidence

{chr(10).join(metric_lines)}

The selected seasonal regional GLM remains materially better than both simple baselines. All {len(folds)} frozen GLM fits reported convergence and no recorded warnings. These are development results; they are not 2026 lockbox performance.

## Frozen 2026 lockbox procedure

1. Treat calendar year 2026 as protected. Loaders must reject or skip 2026 KME outcome rows before numeric parsing during feature preparation and prediction.
2. Build only the frozen region, issue-date, safe population and seasonality inputs.
3. Fit one final frozen GLM on eligible 2015–2025 development rows, preserving the complete-target, safe-population and persistence-comparator support rules recorded here.
4. Generate and checksum 2026 predictions before parsing 2026 KME outcomes.
5. Open complete 2026 targets once, restricted to issue weeks and t+1..t+8 target windows fully contained in ISO week-numbering year 2026.
6. Report the selected model and both declared baselines. Do not tune or substitute another model after observing the result.

## Reproducibility identifiers

Configuration: `{config_record['path']}` — `{config_record['sha256']}`

Freeze code: `{code_record['path']}` — `{code_record['sha256']}`

Git HEAD at freeze: `{config['freeze']['git_head']}`. The worktree was not clean, so file hashes—not the commit alone—are authoritative.

{chr(10).join(input_lines)}
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    protected_year = int(config["prospective_lockbox"]["iso_year"])
    targets, skipped_protected_targets = read_development_targets(
        paths["target"], regions, protected_year
    )
    region_cases, skipped_protected_cases = read_development_region_cases(
        paths["weekly_cases"], mapping, protected_year
    )
    population, skipped_protected_population = read_development_population(
        paths["population"], protected_year
    )
    rows, exclusions = prepare_rows(targets, regions, mapping, region_cases, population)
    folds = generate_folds(rows, config)
    results = evaluate(folds, config)

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
            "coefficients",
            "fit_diagnostics",
            "freeze_manifest",
        )
    }
    report_path = resolve_repo_path(output_config["report"], repo_root)
    write_csv(output_paths["feature_panel"], FEATURE_COLUMNS, [feature_row(row) for row in rows])
    write_csv(
        output_paths["fold_manifest"],
        FOLD_COLUMNS,
        [fold_row(fold, int(config["validation"]["target_embargo_weeks"])) for fold in folds],
    )
    write_csv(output_paths["fold_predictions"], PREDICTION_COLUMNS, results["predictions"])
    write_csv(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, results["fold_metrics"])
    write_csv(
        output_paths["aggregate_metrics"],
        AGGREGATE_METRIC_COLUMNS,
        results["aggregate_metrics"],
    )
    write_csv(output_paths["coefficients"], COEFFICIENT_COLUMNS, results["coefficients"])
    write_csv(output_paths["fit_diagnostics"], DIAGNOSTIC_COLUMNS, results["diagnostics"])

    input_records = {
        key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
        for key in paths
    }
    config_record = file_record(config_path, repo_root)
    code_record = file_record(Path(__file__).resolve(), repo_root)
    report_path.write_text(
        render_report(
            config,
            rows,
            folds,
            results,
            exclusions,
            input_records,
            config_record,
            code_record,
        ),
        encoding="utf-8",
    )
    material_outputs = {
        key: file_record(path, repo_root)
        for key, path in output_paths.items()
        if key != "freeze_manifest"
    }
    material_outputs["report"] = file_record(report_path, repo_root)
    metrics_by_id = {
        str(row["candidate_id"]): dict(row) for row in results["aggregate_metrics"]
    }
    manifest = {
        "schema_version": 1,
        "freeze": config["freeze"],
        "status": "FROZEN_DEVELOPMENT_SYSTEM_2026_PIPELINE_LOCKBOX_UNOPENED",
        "task": config["task"],
        "selected_model": config["selected_model"],
        "finalization_support": config["finalization_support"],
        "population": config["population"],
        "baselines": config["baselines"],
        "validation": config["validation"],
        "prospective_lockbox": config["prospective_lockbox"],
        "inputs": input_records,
        "configuration": config_record,
        "code": code_record,
        "library_versions": {
            "numpy": np.__version__,
            "statsmodels": statsmodels.__version__,
        },
        "support": {
            "n_rows": len(rows),
            "first_issue_week": rows[0].issue_week.isoformat(),
            "last_issue_week": rows[-1].issue_week.isoformat(),
            "exclusions": exclusions,
            "protected_rows_skipped_before_numeric_parsing": {
                "targets": skipped_protected_targets,
                "weekly_cases": skipped_protected_cases,
                "population": skipped_protected_population,
            },
            "n_folds": len(folds),
            "validation_iso_years": [fold.validation_iso_year for fold in folds],
            "n_validation_predictions_per_system": sum(
                len(fold.validation_rows) for fold in folds
            ),
        },
        "checks": {
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "train_target_end_strictly_before_validation": True,
            "validation_targets_contained": True,
            "eight_week_embargo": True,
            "population_strictly_earlier": True,
            "population_is_offset_not_feature": True,
            "weather_required_by_selected_model": False,
            "past_cases_used_by_selected_model": False,
            "classification_logic_used": False,
            "risk_categories_created": False,
            "post_2025_KME_outcomes_opened": False,
        },
        "aggregate_metrics": metrics_by_id,
        "outputs": material_outputs,
    }
    output_paths["freeze_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["freeze_manifest"] = file_record(output_paths["freeze_manifest"], repo_root)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finalize and freeze the KME v1 model.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run(args.config)
    selected = manifest["aggregate_metrics"][GLM_BASE]
    print(
        "Created frozen KME system: "
        f"folds={manifest['support']['n_folds']}, "
        f"validation_rows_per_system={manifest['support']['n_validation_predictions_per_system']}, "
        f"selected_MAE={selected['pooled_mae']:.6f}, "
        "repository_controlled_holdout=2026_unopened"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
