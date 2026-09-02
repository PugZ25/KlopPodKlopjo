from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import statsmodels
import statsmodels.api as sm

from model_v3.models.kme_model_freeze import (
    FEATURE_COLUMNS,
    FreezeRow,
    design_matrix,
    file_record,
    load_config as load_freeze_config,
    read_development_population,
)
from model_v3.models.kme_region_model import (
    BASELINE_RATE,
    GLM_BASE,
    annual_harmonic,
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
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "kme_prediction_seal.json"
PRECOMPUTED_SYSTEM_IDS = (GLM_BASE, BASELINE_RATE)
PERSISTENCE_ID = "baseline_persistence_8w"
SNAPSHOT_COLUMNS = (
    "statistical_region_code",
    "statistical_region_name",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "horizon_weeks",
    "candidate_id",
    "system_role",
    "predicted_cases",
    "predicted_incidence_per_100000",
    "population_exposure",
    "population_year_min",
    "population_year_max",
    "lower_interval",
    "upper_interval",
    "model_version",
    "data_version",
    "sealed_date",
    "data_status",
)
COEFFICIENT_COLUMNS = ("feature", "coefficient", "standard_error")
PARQUET_SCHEMA = pa.schema(
    [
        pa.field("statistical_region_code", pa.string(), nullable=False),
        pa.field("statistical_region_name", pa.string(), nullable=False),
        pa.field("issue_week", pa.date32(), nullable=False),
        pa.field("target_window_start", pa.date32(), nullable=False),
        pa.field("target_window_end", pa.date32(), nullable=False),
        pa.field("horizon_weeks", pa.int16(), nullable=False),
        pa.field("candidate_id", pa.string(), nullable=False),
        pa.field("system_role", pa.string(), nullable=False),
        pa.field("predicted_cases", pa.float64(), nullable=False),
        pa.field("predicted_incidence_per_100000", pa.float64(), nullable=False),
        pa.field("population_exposure", pa.int64(), nullable=False),
        pa.field("population_year_min", pa.int16(), nullable=False),
        pa.field("population_year_max", pa.int16(), nullable=False),
        pa.field("lower_interval", pa.float64(), nullable=True),
        pa.field("upper_interval", pa.float64(), nullable=True),
        pa.field("model_version", pa.string(), nullable=False),
        pa.field("data_version", pa.string(), nullable=False),
        pa.field("sealed_date", pa.date32(), nullable=False),
        pa.field("data_status", pa.string(), nullable=False),
    ]
)


class KmePredictionSealError(ValueError):
    """Raised when the frozen KME prediction seal would be violated."""


@dataclass(frozen=True)
class FutureRow:
    region_code: str
    region_name: str
    issue_week: date
    target_start: date
    target_end: date
    population: int
    population_year_min: int
    population_year_max: int
    seasonal_sin: float
    seasonal_cos: float

    @property
    def exposure_per_100000(self) -> float:
        return self.population / 100_000.0

    @property
    def offset(self) -> float:
        return math.log(self.exposure_per_100000)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise KmePredictionSealError("Unsupported KME prediction-seal schema_version")
    if (
        config["seal"]["status"]
        != "SEALED_WITHOUT_PIPELINE_ACCESS_TO_2026_KME_OUTCOMES"
    ):
        raise KmePredictionSealError("KME prediction seal status changed")
    period = config["prediction_period"]
    if period["issue_iso_year"] != 2026:
        raise KmePredictionSealError("KME sealed prediction ISO year changed")
    if period["target_offsets"] != list(range(1, 9)):
        raise KmePredictionSealError("KME sealed horizon must remain t+1 through t+8")
    if period["issue_week_included"] is not False:
        raise KmePredictionSealError("KME sealed target must exclude issue week")
    configured = tuple(system["candidate_id"] for system in config["systems"])
    if configured != (GLM_BASE, BASELINE_RATE, PERSISTENCE_ID):
        raise KmePredictionSealError("KME sealed system list changed")
    if config["selected_model"]["candidate_id"] != GLM_BASE:
        raise KmePredictionSealError("KME sealed selected model changed")
    if tuple(config["snapshot_schema"]["columns"]) != SNAPSHOT_COLUMNS:
        raise KmePredictionSealError("KME sealed snapshot schema changed")
    return config


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


def read_frozen_feature_panel(path: Path) -> list[FreezeRow]:
    rows: list[FreezeRow] = []
    seen: set[tuple[str, date]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(FEATURE_COLUMNS).issubset(reader.fieldnames):
            raise KmePredictionSealError("Frozen KME feature-panel schema is invalid")
        for source in reader:
            issue = parse_monday(source["issue_week"])
            target_start = parse_monday(source["target_window_start"])
            target_end = parse_monday(source["target_window_end"])
            if issue.isocalendar().year >= 2026 or target_end.isocalendar().year >= 2026:
                raise KmePredictionSealError("Protected 2026 outcome row entered frozen fit panel")
            if target_start != issue + timedelta(weeks=1):
                raise KmePredictionSealError("Frozen fit target does not start at t+1")
            if target_end != issue + timedelta(weeks=8):
                raise KmePredictionSealError("Frozen fit target does not end at t+8")
            if source["past_cases_used_by_selected_model"] != "false":
                raise KmePredictionSealError("Past cases entered frozen selected model")
            if source["weather_required_by_selected_model"] != "false":
                raise KmePredictionSealError("Weather entered frozen selected model")
            region = source["statistical_region_code"]
            key = (region, issue)
            if key in seen:
                raise KmePredictionSealError(f"Duplicate frozen fit row: {key}")
            seen.add(key)
            try:
                target = int(source["target_kme_cases_next_8w"])
                population = int(source["population_exposure"])
                population_year_min = int(source["population_year_min"])
                population_year_max = int(source["population_year_max"])
                past_cases = int(source["past_8w_kme_cases_for_persistence_baseline"])
                offset = float(source["offset_log_population_per_100000"])
                seasonal_sin = float(source["seasonal_sin_annual"])
                seasonal_cos = float(source["seasonal_cos_annual"])
            except ValueError as exc:
                raise KmePredictionSealError("Frozen fit panel has invalid numeric value") from exc
            if target < 0 or population <= 0 or past_cases < 0:
                raise KmePredictionSealError("Frozen fit panel has invalid count or exposure")
            if not math.isclose(offset, math.log(population / 100_000.0), abs_tol=1e-12):
                raise KmePredictionSealError("Frozen fit offset and population disagree")
            latest_past = parse_monday(source["latest_past_case_week_used"])
            if latest_past != issue - timedelta(weeks=1):
                raise KmePredictionSealError("Frozen persistence information does not stop at t-1")
            rows.append(
                FreezeRow(
                    region_code=region,
                    region_name=source["statistical_region_name"],
                    issue_week=issue,
                    target_start=target_start,
                    target_end=target_end,
                    target_value=target,
                    population=population,
                    population_year_min=population_year_min,
                    population_year_max=population_year_max,
                    seasonal_sin=seasonal_sin,
                    seasonal_cos=seasonal_cos,
                    past_cases=past_cases,
                    latest_past_case_week=latest_past,
                )
            )
    if not rows:
        raise KmePredictionSealError("Frozen KME fit panel is empty")
    return sorted(rows, key=lambda row: (row.issue_week, row.region_code))


def eligible_issue_weeks(iso_year: int, horizon_weeks: int) -> tuple[date, ...]:
    if horizon_weeks <= 0:
        raise KmePredictionSealError("Sealed horizon must be positive")
    result: list[date] = []
    issue = date.fromisocalendar(iso_year, 1, 1)
    while issue.isocalendar().year == iso_year:
        target_weeks = tuple(
            issue + timedelta(weeks=offset) for offset in range(1, horizon_weeks + 1)
        )
        if all(week.isocalendar().year == iso_year for week in target_weeks):
            result.append(issue)
        issue += timedelta(weeks=1)
    if not result:
        raise KmePredictionSealError("No eligible sealed issue weeks")
    return tuple(result)


def prepare_future_rows(
    config: Mapping[str, Any],
    regions: Mapping[str, str],
    mapping: Mapping[str, str],
    population: Mapping[str, Mapping[int, int | None]],
) -> list[FutureRow]:
    period = config["prediction_period"]
    iso_year = int(period["issue_iso_year"])
    horizon = int(period["horizon_weeks"])
    rows = []
    for issue in eligible_issue_weeks(iso_year, horizon):
        target_start = issue + timedelta(weeks=1)
        target_end = issue + timedelta(weeks=horizon)
        for region in sorted(regions):
            population_value, year_min, year_max = selected_region_population(
                region, issue, mapping, population
            )
            seasonal_sin, seasonal_cos = annual_harmonic(issue)
            rows.append(
                FutureRow(
                    region_code=region,
                    region_name=regions[region],
                    issue_week=issue,
                    target_start=target_start,
                    target_end=target_end,
                    population=population_value,
                    population_year_min=year_min,
                    population_year_max=year_max,
                    seasonal_sin=seasonal_sin,
                    seasonal_cos=seasonal_cos,
                )
            )
    return rows


def future_design_matrix(
    rows: Sequence[FutureRow], region_levels: Sequence[str]
) -> tuple[np.ndarray, tuple[str, ...]]:
    reference = region_levels[0]
    columns = (
        "intercept",
        "seasonal_sin_annual",
        "seasonal_cos_annual",
    ) + tuple(f"region[{region}]" for region in region_levels if region != reference)
    matrix = []
    for row in rows:
        if row.region_code not in region_levels:
            raise KmePredictionSealError(f"Unseen future region: {row.region_code}")
        matrix.append(
            [
                1.0,
                row.seasonal_sin,
                row.seasonal_cos,
                *(float(row.region_code == region) for region in region_levels if region != reference),
            ]
        )
    return np.asarray(matrix, dtype=float), columns


def fit_final_model(
    rows: Sequence[FreezeRow], config: Mapping[str, Any]
) -> tuple[Any, tuple[str, ...], dict[str, Any], list[dict[str, Any]]]:
    levels = tuple(sorted({row.region_code for row in rows}))
    matrix, columns = design_matrix(rows, levels)
    model_config = config["selected_model"]
    model = sm.GLM(
        np.asarray([row.target_value for row in rows], dtype=float),
        matrix,
        family=sm.families.Poisson(),
        offset=np.asarray([row.offset for row in rows], dtype=float),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = model.fit(
            maxiter=int(model_config["maxiter"]), tol=float(model_config["tol"])
        )
    if not result.converged:
        raise KmePredictionSealError("Frozen final GLM did not converge")
    diagnostics = {
        "candidate_id": GLM_BASE,
        "n_training_rows": len(rows),
        "n_parameters": len(columns),
        "region_levels": list(levels),
        "reference_region": levels[0],
        "converged": bool(result.converged),
        "iterations": int(result.fit_history.get("iteration", -1)),
        "warning_count": len(caught),
        "warning_messages": [str(item.message) for item in caught],
        "deviance": float(result.deviance),
        "pearson_chi2": float(result.pearson_chi2),
        "statsmodels_version": statsmodels.__version__,
    }
    coefficients = [
        {
            "feature": feature,
            "coefficient": float(coefficient),
            "standard_error": float(standard_error),
        }
        for feature, coefficient, standard_error in zip(columns, result.params, result.bse)
    ]
    return result, levels, diagnostics, coefficients


def historical_rates(rows: Sequence[FreezeRow]) -> dict[str, float]:
    totals: defaultdict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        totals[row.region_code][0] += row.target_value
        totals[row.region_code][1] += row.exposure_per_100000
    result = {}
    for region, (cases, exposure) in totals.items():
        if exposure <= 0:
            raise KmePredictionSealError(f"No historical exposure for region {region}")
        result[region] = cases / exposure
    return result


def stable_data_version(input_hashes: Mapping[str, str]) -> str:
    selected = (
        input_hashes["frozen_feature_panel"],
        input_hashes["population"],
        input_hashes["statistical_region"],
        input_hashes["municipality_statistical_region"],
    )
    digest = hashlib.sha256("|".join(selected).encode("ascii")).hexdigest()
    return f"kme_data@sha256:{digest}"


def prediction_rows(
    future_rows: Sequence[FutureRow],
    selected_predictions: Sequence[float],
    baseline_rates: Mapping[str, float],
    config: Mapping[str, Any],
    coefficient_hash: str,
    config_hash: str,
    data_version: str,
) -> list[dict[str, Any]]:
    if len(future_rows) != len(selected_predictions):
        raise KmePredictionSealError("Future row and prediction counts differ")
    sealed_date = date.fromisoformat(config["seal"]["sealed_date"])
    result = []
    for row, selected_prediction in zip(future_rows, selected_predictions):
        baseline_prediction = baseline_rates[row.region_code] * row.exposure_per_100000
        for candidate_id, role, predicted, model_version in (
            (
                GLM_BASE,
                "frozen_selected_model",
                float(selected_prediction),
                f"{GLM_BASE}@sha256:{coefficient_hash}",
            ),
            (
                BASELINE_RATE,
                "primary_simple_baseline",
                float(baseline_prediction),
                f"{BASELINE_RATE}@sha256:{config_hash}",
            ),
        ):
            if not math.isfinite(predicted) or predicted < 0:
                raise KmePredictionSealError(f"Invalid sealed prediction from {candidate_id}")
            result.append(
                {
                    "statistical_region_code": row.region_code,
                    "statistical_region_name": row.region_name,
                    "issue_week": row.issue_week,
                    "target_window_start": row.target_start,
                    "target_window_end": row.target_end,
                    "horizon_weeks": 8,
                    "candidate_id": candidate_id,
                    "system_role": role,
                    "predicted_cases": predicted,
                    "predicted_incidence_per_100000": predicted
                    / row.population
                    * 100_000.0,
                    "population_exposure": row.population,
                    "population_year_min": row.population_year_min,
                    "population_year_max": row.population_year_max,
                    "lower_interval": None,
                    "upper_interval": None,
                    "model_version": model_version,
                    "data_version": data_version,
                    "sealed_date": sealed_date,
                    "data_status": "sealed_without_pipeline_access_to_2026_KME_outcomes",
                }
            )
    return sorted(
        result,
        key=lambda item: (
            item["issue_week"],
            item["statistical_region_code"],
            item["candidate_id"],
        ),
    )


def json_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in row.items()
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow(json_row(row))


def write_coefficients(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COEFFICIENT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def render_report(
    config: Mapping[str, Any],
    training_rows: Sequence[FreezeRow],
    future_rows: Sequence[FutureRow],
    predictions: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    output_records: Mapping[str, Mapping[str, Any]],
) -> str:
    selected = [row for row in predictions if row["candidate_id"] == GLM_BASE]
    baseline = [row for row in predictions if row["candidate_id"] == BASELINE_RATE]
    return f"""# Sealed KME 2026 predictions

## Status

**SEALED WITHOUT PIPELINE ACCESS TO 2026 KME OUTCOMES.**

The frozen regional eight-week KME model was fitted once to {len(training_rows)} eligible 2015–2025 development rows. This stage did not load or create a 2026 KME target and did not parse a 2026 KME outcome.

Because the seal date is during 2026, this is a retrospective/ongoing repository-controlled holdout, not a fully prospective lockbox. Whether any person accessed 2026 outcomes outside this repository pipeline is `UNKNOWN` and cannot be audited from repository state.

## Prediction scope

- Analysis unit: statistical region × issue week.
- Issue period: ISO week-numbering year 2026.
- Horizon: exactly t+1 through t+8, excluding issue week.
- Eligible issue weeks: {len({row.issue_week for row in future_rows})}, from {min(row.issue_week for row in future_rows)} through {max(row.issue_week for row in future_rows)}.
- Regions: {len({row.region_code for row in future_rows})}.
- Sealed selected-model predictions: {len(selected)}.
- Sealed historical-rate baseline predictions: {len(baseline)}.

The final eligible issue date is chosen by date arithmetic so its t+8 week remains in ISO year 2026; no week number is manually assumed.

## Frozen model fit

- Candidate: `{GLM_BASE}`.
- Formula: `{config['selected_model']['formula']}`.
- Population is the offset and incidence denominator, not an ordinary feature.
- Fit convergence: {str(diagnostics['converged']).lower()} in {diagnostics['iterations']} iterations.
- Parameters: {diagnostics['n_parameters']}; warnings: {diagnostics['warning_count']}.
- Weather, current/past KME cases, classifications, thresholds and generated predictions are absent from the selected-model design.
- Predictive intervals are unavailable, so interval fields are null rather than fabricated.

## Persistence baseline

The persistence algorithm is sealed, but its later 2026 numeric predictions are not fabricated. It requires reported cases in t−8..t−1, including already-observed 2026 weeks for later issue dates. The immutable rule is stored in `kme_2026_persistence_baseline_contract.json`; each value must be generated sequentially before its future t+1..t+8 outcome window is accessed.

## Canonical outputs

CSV, Parquet and JSON are generated from the same sorted in-memory prediction table. Their hashes and all input, configuration, code and coefficient hashes are recorded in `kme_2026_prediction_seal_manifest.json`.

- CSV: `{output_records['prediction_csv']['sha256']}`
- Parquet: `{output_records['prediction_parquet']['sha256']}`
- JSON: `{output_records['prediction_json']['sha256']}`
- Coefficients: `{output_records['coefficients']['sha256']}`

These are sealed model outputs, not observed performance and not personal-risk estimates.
"""


def run(
    config_path: Path = DEFAULT_CONFIG_PATH, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    config = load_config(config_path)
    paths, hashes = verify_inputs(config, repo_root)
    freeze_config = load_freeze_config(paths["freeze_config"])
    if freeze_config["freeze"]["status"] != "FROZEN":
        raise KmePredictionSealError("Referenced KME freeze is not frozen")
    freeze_manifest = json.loads(paths["freeze_manifest"].read_text(encoding="utf-8"))
    if freeze_manifest["checks"]["post_2025_KME_outcomes_opened"] is not False:
        raise KmePredictionSealError("Freeze manifest does not protect 2026 outcomes")
    training_rows = read_frozen_feature_panel(paths["frozen_feature_panel"])
    regions = read_regions(paths["statistical_region"])
    mapping = read_mapping(paths["municipality_statistical_region"], regions)
    population, skipped_protected_population = read_development_population(
        paths["population"], int(config["prediction_period"]["issue_iso_year"])
    )
    fitted, levels, diagnostics, coefficients = fit_final_model(training_rows, config)
    future_rows = prepare_future_rows(config, regions, mapping, population)
    future_matrix, future_columns = future_design_matrix(future_rows, levels)
    training_matrix, training_columns = design_matrix(training_rows, levels)
    if future_columns != training_columns:
        raise KmePredictionSealError("Frozen training and future design columns differ")
    if training_matrix.shape[1] != future_matrix.shape[1]:
        raise KmePredictionSealError("Frozen training and future design widths differ")
    selected_predictions = fitted.predict(
        future_matrix,
        offset=np.asarray([row.offset for row in future_rows], dtype=float),
    )
    rates = historical_rates(training_rows)

    output_config = config["outputs"]
    output_directory = resolve_repo_path(output_config["directory"], repo_root)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / output_config[key]
        for key in (
            "coefficients",
            "fit_diagnostics",
            "prediction_csv",
            "prediction_parquet",
            "prediction_json",
            "persistence_contract",
            "seal_manifest",
        )
    }
    report_path = resolve_repo_path(output_config["report"], repo_root)
    write_coefficients(output_paths["coefficients"], coefficients)
    coefficient_hash = sha256_file(output_paths["coefficients"])
    config_hash = sha256_file(config_path)
    data_version = stable_data_version(hashes)
    predictions = prediction_rows(
        future_rows,
        selected_predictions,
        rates,
        config,
        coefficient_hash,
        config_hash,
        data_version,
    )
    expected_keys = {
        (candidate_id, row.region_code, row.issue_week)
        for candidate_id in PRECOMPUTED_SYSTEM_IDS
        for row in future_rows
    }
    actual_keys = {
        (row["candidate_id"], row["statistical_region_code"], row["issue_week"])
        for row in predictions
    }
    if actual_keys != expected_keys or len(actual_keys) != len(predictions):
        raise KmePredictionSealError("Sealed prediction key grid is incomplete or duplicated")

    write_csv(output_paths["prediction_csv"], predictions)
    serializable_predictions = [json_row(row) for row in predictions]
    output_paths["prediction_json"].write_text(
        json.dumps(serializable_predictions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    table = pa.Table.from_pylist(predictions, schema=PARQUET_SCHEMA)
    pq.write_table(table, output_paths["prediction_parquet"], compression="snappy")
    output_paths["fit_diagnostics"].write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    persistence = next(
        system for system in config["systems"] if system["candidate_id"] == PERSISTENCE_ID
    )
    persistence_contract = {
        "schema_version": 1,
        "status": "ALGORITHM_SEALED_NUMERIC_2026_VALUES_NOT_PRECOMPUTABLE",
        "candidate_id": PERSISTENCE_ID,
        "prediction_period": config["prediction_period"],
        "algorithm": persistence["sealed_algorithm"],
        "availability_rule": persistence["availability_rule"],
        "reason_values_not_present": persistence["reason"],
        "current_or_future_target_values_allowed": False,
        "missing_past_week_rule": "prediction_unavailable_not_zero",
        "seal_config_sha256": config_hash,
        "seal_code_sha256": sha256_file(Path(__file__).resolve()),
    }
    output_paths["persistence_contract"].write_text(
        json.dumps(persistence_contract, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    material_outputs = {
        key: file_record(path, repo_root)
        for key, path in output_paths.items()
        if key != "seal_manifest"
    }
    report_path.write_text(
        render_report(
            config,
            training_rows,
            future_rows,
            predictions,
            diagnostics,
            material_outputs,
        ),
        encoding="utf-8",
    )
    material_outputs["report"] = file_record(report_path, repo_root)
    input_records = {
        key: {"path": repository_path(paths[key], repo_root), "sha256": hashes[key]}
        for key in paths
    }
    counts_by_system = {
        candidate_id: sum(row["candidate_id"] == candidate_id for row in predictions)
        for candidate_id in PRECOMPUTED_SYSTEM_IDS
    }
    manifest = {
        "schema_version": 1,
        "seal": config["seal"],
        "status": "SEALED_2026_PREDICTIONS_NO_2026_KME_OUTCOME_ACCESS",
        "prediction_period": config["prediction_period"],
        "selected_model": config["selected_model"],
        "systems": config["systems"],
        "population": config["population"],
        "snapshot_schema": config["snapshot_schema"],
        "configuration": file_record(config_path, repo_root),
        "code": file_record(Path(__file__).resolve(), repo_root),
        "inputs": input_records,
        "model_fit": diagnostics,
        "model_artifact": {
            "coefficient_sha256": coefficient_hash,
            "region_levels": list(levels),
            "design_columns": list(training_columns),
        },
        "prediction_support": {
            "n_issue_weeks": len({row.issue_week for row in future_rows}),
            "first_issue_week": min(row.issue_week for row in future_rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in future_rows).isoformat(),
            "last_target_window_end": max(row.target_end for row in future_rows).isoformat(),
            "n_regions": len(regions),
            "n_rows": len(predictions),
            "rows_by_system": counts_by_system,
            "skipped_protected_population_rows_before_numeric_parsing": skipped_protected_population,
        },
        "checks": {
            "frozen_feature_panel_hash_verified": True,
            "freeze_manifest_hash_verified": True,
            "target_exactly_t_plus_1_through_t_plus_8": True,
            "issue_week_excluded": True,
            "all_issue_weeks_in_ISO_2026": True,
            "all_target_weeks_in_ISO_2026": True,
            "population_strictly_earlier_than_issue_calendar_year": True,
            "population_is_offset_not_feature": True,
            "weather_used_by_selected_model": False,
            "past_KME_used_by_selected_model": False,
            "2026_KME_outcomes_read": False,
            "2026_KME_targets_created": False,
            "classification_logic_used": False,
            "risk_categories_created": False,
            "personal_risk_language_created": False,
            "JSON_and_Parquet_same_canonical_table": True,
            "persistence_values_fabricated": False,
        },
        "data_version": data_version,
        "outputs": material_outputs,
    }
    output_paths["seal_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["seal_manifest"] = file_record(output_paths["seal_manifest"], repo_root)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fit the frozen KME model and seal repository-controlled 2026 predictions."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run(args.config)
    support = manifest["prediction_support"]
    print(
        "Sealed KME 2026 predictions: "
        f"issues={support['n_issue_weeks']}, regions={support['n_regions']}, "
        f"rows={support['n_rows']}, outcomes_read=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
