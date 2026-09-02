from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
from catboost import CatBoostRegressor, Pool

from model_v3.evaluation.lockbox_evaluation import (
    load_config as load_lockbox_config,
    verify_frozen_hashes,
    verify_runtime_versions,
)
from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS
from model_v3.models.catboost_challenger import (
    CHALLENGER_ID,
    FEATURE_COLUMNS,
    attach_weather,
    build_pool,
    load_config as load_catboost_config,
    validate_feature_availability,
)
from model_v3.models.non_ml_baselines import (
    parse_code,
    parse_monday,
    parse_nonnegative_integer,
    read_development_weekly_cases,
    resolve_repo_path,
)
from model_v3.models.seasonal_count_models import (
    PastIncidence,
    build_population_history,
    calculate_past_incidence,
    prepare_model_rows,
    read_development_population,
    read_development_target_metadata,
    read_selected_development_target_values,
    seasonal_terms,
    select_population_exposure,
)
from model_v3.models.weather_ablation import (
    IssueWeather,
    WEATHER_FEATURE_COLUMNS,
    WeeklyWeather,
    WeatherScaler,
    fit_weather_scaler,
    issue_weather_features,
    read_weekly_weather,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "lyme_operational_prediction.json"
)

PREDICTION_COLUMNS = (
    "model_id",
    "municipality_code",
    "municipality_name",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "predicted_reported_lyme_cases_next_4w",
    "prediction_status",
    "population_exposure",
    "population_year",
    "past_4w_lyme_cases",
    "past_4w_lyme_incidence_per_100000",
    "latest_case_week_used",
    "latest_weather_week_used",
    "weather_vintage",
    "interval_status",
    "risk_category_status",
)


class LymeOperationalError(ValueError):
    """Raised when operational Lyme prediction violates the frozen contract."""


@dataclass(frozen=True)
class OperationalRow:
    municipality_code: str
    municipality_name: str
    issue_week: date
    population: int
    population_year: int
    seasonal_sin: float
    seasonal_cos: float
    past_incidence: PastIncidence
    weather: IssueWeather


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(value: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _path_record(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    try:
        label = str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _catboost_structure_sha256(path: Path) -> str:
    model = CatBoostRegressor()
    model.load_model(str(path))
    with tempfile.TemporaryDirectory() as directory:
        json_path = Path(directory) / "model.json"
        model.save_model(str(json_path), format="json")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    model_info = payload.get("model_info", {})
    if not isinstance(model_info, dict):
        raise LymeOperationalError("CatBoost structural model_info is invalid")
    for volatile_key in ("model_guid", "train_finish_time"):
        model_info.pop(volatile_key, None)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREDICTION_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in PREDICTION_COLUMNS})


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise LymeOperationalError("Operational prediction config must be in repository")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise LymeOperationalError("Operational prediction schema_version must equal 1")
    frozen = config.get("frozen_model", {})
    if frozen.get("selected_model_id") != CHALLENGER_ID:
        raise LymeOperationalError("Operational selected model differs from frozen model")
    contract = config.get("prediction_contract", {})
    if contract.get("past_case_weeks") != [4, 3, 2, 1]:
        raise LymeOperationalError("Past case window must be t-4 through t-1")
    if contract.get("weather_weeks") != [4, 3, 2, 1]:
        raise LymeOperationalError("Weather window must be t-4 through t-1")
    if contract.get("missing_input_rule") != "block_prediction_do_not_fill_or_zero":
        raise LymeOperationalError("Missing operational inputs must block prediction")
    if contract.get("current_or_future_cases_allowed") is not False:
        raise LymeOperationalError("Current/future cases cannot be model inputs")
    if contract.get("current_or_future_weather_allowed") is not False:
        raise LymeOperationalError("Current/future weather cannot be model inputs")
    if config.get("bridge", {}).get("promotion_thresholds") is not None:
        raise LymeOperationalError("Bridge thresholds require a reviewed config version")
    return config


def _verify_file_hash(path: Path, expected: str, *, label: str) -> None:
    if not path.is_file():
        raise LymeOperationalError(f"{label} is missing: {path}")
    actual = _sha256(path)
    if actual != expected:
        raise LymeOperationalError(
            f"{label} SHA-256 mismatch: expected={expected}, actual={actual}"
        )


def _artifact_paths(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> dict[str, Path]:
    frozen = config["frozen_model"]
    directory = _repo_path(frozen["artifact_directory"], repo_root)
    return {
        "directory": directory,
        "model": directory / frozen["model_file"],
        "scaler": directory / frozen["weather_scaler_file"],
        "manifest": directory / frozen["manifest_file"],
    }


def _verify_existing_artifact(
    config: Mapping[str, Any], repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    paths = _artifact_paths(config, repo_root)
    if not all(paths[key].is_file() for key in ("model", "scaler", "manifest")):
        raise LymeOperationalError("Sealed model directory is absent or incomplete")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if manifest.get("status") != "sealed":
        raise LymeOperationalError("Operational model manifest is not sealed")
    if manifest.get("selected_model_id") != config["frozen_model"]["selected_model_id"]:
        raise LymeOperationalError("Sealed model ID differs from operational config")
    if manifest.get("training_period") != config["frozen_model"]["training_period"]:
        raise LymeOperationalError("Sealed model training period differs from config")
    if manifest.get("fit_rule") != config["frozen_model"]["fit_rule"]:
        raise LymeOperationalError("Sealed model fit rule differs from config")
    for key in ("model", "scaler"):
        expected = manifest.get("artifacts", {}).get(key, {}).get("sha256")
        if not isinstance(expected, str) or _sha256(paths[key]) != expected:
            raise LymeOperationalError(f"Sealed {key} artifact hash mismatch")
    expected_structure = manifest.get("artifacts", {}).get("model", {}).get(
        "structural_sha256_excluding_volatile_metadata"
    )
    if (
        not isinstance(expected_structure, str)
        or _catboost_structure_sha256(paths["model"]) != expected_structure
    ):
        raise LymeOperationalError("Sealed model structural hash mismatch")
    return manifest


def seal_frozen_model(
    config: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    paths = _artifact_paths(config, repo_root)
    if paths["directory"].exists():
        return _verify_existing_artifact(config, repo_root)

    frozen = config["frozen_model"]
    lockbox_path = _repo_path(frozen["lockbox_config"], repo_root)
    catboost_path = _repo_path(frozen["selected_model_config"], repo_root)
    _verify_file_hash(
        lockbox_path, frozen["lockbox_config_sha256"], label="Frozen lockbox config"
    )
    _verify_file_hash(
        catboost_path,
        frozen["selected_model_config_sha256"],
        label="Frozen selected-model config",
    )
    lockbox = load_lockbox_config(lockbox_path)
    frozen_records = verify_frozen_hashes(lockbox)
    runtime_versions = verify_runtime_versions()
    input_paths = {
        key: resolve_repo_path(value) for key, value in lockbox["inputs"].items()
    }
    freeze = lockbox["freeze"]
    target_rows = read_development_target_metadata(
        input_paths["development_target"],
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
        raise LymeOperationalError("No frozen development rows are eligible")
    selected_keys = {(row.municipality_code, row.issue_week) for row in development_rows}
    target_values = read_selected_development_target_values(
        input_paths["development_target"],
        selected_keys,
        lockbox_year=freeze["lockbox_year"],
    )
    population = read_development_population(
        input_paths["population"], lockbox_year=freeze["lockbox_year"]
    )
    weekly_cases = read_development_weekly_cases(
        input_paths["weekly_cases"], lockbox_year=freeze["lockbox_year"]
    )
    phase9_rows = prepare_model_rows(
        development_rows, target_values, population, weekly_cases
    )
    complete_past_rows = [
        row for row in phase9_rows if row.past_incidence.status == "available"
    ]
    weekly_weather, _ = read_weekly_weather(
        input_paths["development_weather"],
        input_paths["development_weather_quality"],
        lockbox_year=freeze["lockbox_year"],
    )
    training_rows, incomplete_weather = attach_weather(
        complete_past_rows, weekly_weather
    )
    validate_feature_availability(training_rows)
    expected_count = int(config["prediction_contract"]["expected_municipality_count"])
    training_codes = {row.municipality_code for row in training_rows}
    if len(training_codes) != expected_count:
        raise LymeOperationalError(
            f"Frozen training support has {len(training_codes)} municipalities, "
            f"expected {expected_count}"
        )
    scaler = fit_weather_scaler(training_rows)
    catboost_config = load_catboost_config(catboost_path)
    challenger = catboost_config["challenger"]
    model = CatBoostRegressor(
        loss_function=challenger["loss_function"],
        eval_metric=challenger["loss_function"],
        has_time=challenger["ordering"]["has_time"],
        **challenger["parameters"],
    )
    model.fit(build_pool(training_rows, scaler, include_labels=True))

    paths["directory"].parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".lyme_v1_sealing_", dir=paths["directory"].parent)
    )
    try:
        temporary_model = temporary / frozen["model_file"]
        temporary_scaler = temporary / frozen["weather_scaler_file"]
        temporary_manifest = temporary / frozen["manifest_file"]
        model.save_model(str(temporary_model))
        scaler_payload = {
            "schema_version": 1,
            "feature_order": list(WEATHER_FEATURE_COLUMNS),
            "fit_scope": "all_eligible_2016_2024_frozen_development_training_rows",
            "means": dict(scaler.means),
            "standard_deviations": dict(scaler.standard_deviations),
        }
        _write_json(temporary_scaler, scaler_payload)
        manifest = {
            "schema_version": 1,
            "status": "sealed",
            "selected_model_id": CHALLENGER_ID,
            "training_period": frozen["training_period"],
            "fit_rule": frozen["fit_rule"],
            "frozen_lockbox_config": _path_record(lockbox_path, repo_root),
            "frozen_selected_model_config": _path_record(catboost_path, repo_root),
            "frozen_input_records": frozen_records,
            "runtime_versions": runtime_versions,
            "catboost_version": catboost.__version__,
            "feature_columns": list(FEATURE_COLUMNS),
            "weather_feature_columns": list(WEATHER_FEATURE_COLUMNS),
            "training": {
                "eligible_target_rows": len(development_rows),
                "rows_after_past_case_completeness": len(complete_past_rows),
                "rows_excluded_incomplete_weather": incomplete_weather,
                "final_training_rows": len(training_rows),
                "municipality_count": len(training_codes),
                "first_issue_week": min(row.issue_week for row in training_rows).isoformat(),
                "last_issue_week": max(row.issue_week for row in training_rows).isoformat(),
                "latest_target_window_end": max(
                    row.target_window_end for row in training_rows
                ).isoformat(),
            },
            "artifacts": {
                "model": {
                    **_path_record(temporary_model, temporary),
                    "structural_sha256_excluding_volatile_metadata": (
                        _catboost_structure_sha256(temporary_model)
                    ),
                },
                "scaler": _path_record(temporary_scaler, temporary),
            },
            "operational_retraining_allowed": False,
        }
        _write_json(temporary_manifest, manifest)
        os.replace(temporary, paths["directory"])
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return _verify_existing_artifact(config, repo_root)


def _read_municipalities(
    path: Path, *, expected_count: int
) -> dict[str, str]:
    names: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != (
            "municipality_code",
            "municipality_name",
        ):
            raise LymeOperationalError("Municipality schema is invalid")
        for index, row in enumerate(reader, start=1):
            code = parse_code(row["municipality_code"], context=f"municipality row {index}")
            name = row["municipality_name"].strip()
            if not name or code in names:
                raise LymeOperationalError("Municipality names are blank or duplicated")
            names[code] = name
    if len(names) != expected_count:
        raise LymeOperationalError(
            f"Municipality count is {len(names)}, expected {expected_count}"
        )
    return names


def _read_population(path: Path) -> dict[tuple[str, int], int]:
    result: dict[tuple[str, int], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"municipality_code", "year", "population"}
        if not required.issubset(reader.fieldnames or ()):
            raise LymeOperationalError("Population schema is invalid")
        for index, row in enumerate(reader, start=1):
            if row["population"] is None or not row["population"].strip():
                continue
            code = parse_code(row["municipality_code"], context=f"population row {index}")
            year = parse_nonnegative_integer(
                row["year"], context=f"population row {index} year"
            )
            population = parse_nonnegative_integer(
                row["population"], context=f"population row {index} population"
            )
            if population <= 0:
                raise LymeOperationalError("Population exposure must be positive")
            key = (code, year)
            if key in result:
                raise LymeOperationalError(f"Duplicate population key: {key}")
            result[key] = population
    if not result:
        raise LymeOperationalError("Population input is empty")
    return result


def _read_operational_cases(
    path: Path,
    *,
    issue_week: date,
    municipality_codes: set[str],
) -> dict[tuple[str, date], int]:
    required_weeks = {
        issue_week - timedelta(weeks=offset) for offset in (4, 3, 2, 1)
    }
    result: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"municipality_code", "issue_week", "lyme_cases"}
        if not required_columns.issubset(reader.fieldnames or ()):
            raise LymeOperationalError(
                "Operational weekly cases require municipality_code, issue_week, lyme_cases"
            )
        for index, row in enumerate(reader, start=1):
            week = parse_monday(
                row["issue_week"], context=f"operational case row {index} issue_week"
            )
            if week not in required_weeks:
                continue
            code = parse_code(
                row["municipality_code"], context=f"operational case row {index} code"
            )
            if code not in municipality_codes:
                raise LymeOperationalError(f"Operational cases contain unknown code: {code}")
            value = parse_nonnegative_integer(
                row["lyme_cases"], context=f"operational case row {index} lyme_cases"
            )
            key = (code, week)
            if key in result:
                raise LymeOperationalError(f"Duplicate operational case row: {key}")
            result[key] = value
    expected_keys = {
        (code, week) for code in municipality_codes for week in required_weeks
    }
    missing = sorted(expected_keys - set(result))
    if missing:
        raise LymeOperationalError(
            f"Operational cases are missing {len(missing)} required municipality-weeks; "
            f"first={missing[:5]}"
        )
    return result


def _read_case_provenance(path: Path, weekly_cases_path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "source_name",
        "source_url",
        "retrieved_at_utc",
        "acquisition_method",
        "source_file",
    }
    if set(payload) != required or payload.get("schema_version") != 1:
        raise LymeOperationalError("Operational case provenance schema is invalid")
    for field in ("source_name", "source_url", "acquisition_method"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise LymeOperationalError(f"Operational case provenance {field} is required")
    try:
        retrieved = datetime.fromisoformat(
            payload["retrieved_at_utc"].replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise LymeOperationalError(
            "Operational case retrieved_at_utc is invalid"
        ) from exc
    if retrieved.tzinfo is None:
        raise LymeOperationalError("Operational case retrieved_at_utc needs an offset")
    source_file = payload["source_file"]
    if set(source_file) != {"filename", "sha256"}:
        raise LymeOperationalError("Operational case source_file provenance is invalid")
    if source_file["filename"] != weekly_cases_path.name:
        raise LymeOperationalError("Operational case provenance filename mismatch")
    if source_file["sha256"] != _sha256(weekly_cases_path):
        raise LymeOperationalError("Operational case provenance SHA-256 mismatch")
    return payload


def _read_operational_weather(
    weekly_path: Path,
    quality_path: Path,
    *,
    issue_week: date,
    municipality_codes: set[str],
    allowed_vintages: set[str],
) -> tuple[dict[tuple[str, date], WeeklyWeather], dict[str, Any]]:
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if quality.get("status") != "pass":
        raise LymeOperationalError("Operational weather quality status is not pass")
    if quality.get("issue_week") != issue_week.isoformat():
        raise LymeOperationalError("Operational weather issue_week differs from prediction")
    if quality.get("weather_vintage") not in allowed_vintages:
        raise LymeOperationalError("Operational weather vintage is not allowed")
    if quality.get("weekly_dataset", {}).get("sha256") != _sha256(weekly_path):
        raise LymeOperationalError("Operational weekly weather hash mismatch")
    if quality.get("municipality_count") != len(municipality_codes):
        raise LymeOperationalError("Operational weather municipality count differs")
    if quality.get("complete_week_count") != 4:
        raise LymeOperationalError("Operational weather must contain four complete weeks")

    required_weeks = {
        issue_week - timedelta(weeks=offset) for offset in (4, 3, 2, 1)
    }
    result: dict[tuple[str, date], WeeklyWeather] = {}
    with weekly_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEEKLY_COLUMNS:
            raise LymeOperationalError("Operational weekly weather schema is invalid")
        for index, row in enumerate(reader, start=1):
            week = parse_monday(
                row["week_start"], context=f"operational weather row {index} week_start"
            )
            if week not in required_weeks:
                raise LymeOperationalError("Operational weather contains an unexpected week")
            code = parse_code(
                row["municipality_code"], context=f"operational weather row {index} code"
            )
            if code not in municipality_codes:
                raise LymeOperationalError(f"Operational weather has unknown code: {code}")
            week_end = date.fromisoformat(row["week_end"])
            if week_end != week + timedelta(days=6) or week_end >= issue_week:
                raise LymeOperationalError("Operational weather week reaches issue time")
            if row["weather_status"] != "complete":
                raise LymeOperationalError("Operational weather row is incomplete")
            if int(row["source_hour_count"]) != 168 or int(row["minimum_present_hours"]) != 168:
                raise LymeOperationalError("Operational weather row does not contain 168 hours")
            values: dict[str, float] = {}
            for column in OUTPUT_VARIABLES:
                value = float(row[column])
                if not math.isfinite(value):
                    raise LymeOperationalError("Operational weather value is non-finite")
                values[column] = value
            key = (code, week)
            if key in result:
                raise LymeOperationalError(f"Duplicate operational weather row: {key}")
            result[key] = WeeklyWeather(code, week, week_end, "complete", values)
    expected_keys = {
        (code, week) for code in municipality_codes for week in required_weeks
    }
    missing = sorted(expected_keys - set(result))
    if missing:
        raise LymeOperationalError(
            f"Operational weather is missing {len(missing)} rows; first={missing[:5]}"
        )
    return result, quality


def _load_scaler(path: Path) -> WeatherScaler:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("feature_order") != list(WEATHER_FEATURE_COLUMNS):
        raise LymeOperationalError("Sealed weather scaler feature order changed")
    means = payload.get("means", {})
    standard_deviations = payload.get("standard_deviations", {})
    if set(means) != set(WEATHER_FEATURE_COLUMNS) or set(standard_deviations) != set(
        WEATHER_FEATURE_COLUMNS
    ):
        raise LymeOperationalError("Sealed weather scaler columns changed")
    if not all(
        math.isfinite(float(means[name]))
        and math.isfinite(float(standard_deviations[name]))
        and float(standard_deviations[name]) > 0
        for name in WEATHER_FEATURE_COLUMNS
    ):
        raise LymeOperationalError("Sealed weather scaler values are invalid")
    return WeatherScaler(
        means={name: float(means[name]) for name in WEATHER_FEATURE_COLUMNS},
        standard_deviations={
            name: float(standard_deviations[name]) for name in WEATHER_FEATURE_COLUMNS
        },
    )


def _prepare_operational_rows(
    *,
    issue_week: date,
    municipality_names: Mapping[str, str],
    population_by_key: Mapping[tuple[str, int], int],
    weekly_cases: Mapping[tuple[str, date], int],
    weekly_weather: Mapping[tuple[str, date], WeeklyWeather],
) -> list[OperationalRow]:
    population_history = build_population_history(population_by_key)
    rows: list[OperationalRow] = []
    for code in sorted(municipality_names):
        exposure = select_population_exposure(
            population_history, municipality_code=code, issue_week=issue_week
        )
        past = calculate_past_incidence(
            weekly_cases,
            municipality_code=code,
            issue_week=issue_week,
            population=exposure.population,
        )
        if past.status != "available" or past.incidence_per_100000 is None:
            raise LymeOperationalError(f"Past incidence is unavailable for {code}")
        weather = issue_weather_features(
            weekly_weather, municipality_code=code, issue_week=issue_week
        )
        if weather is None:
            raise LymeOperationalError(f"Weather features are unavailable for {code}")
        seasonal_sin, seasonal_cos = seasonal_terms(issue_week)
        rows.append(
            OperationalRow(
                municipality_code=code,
                municipality_name=municipality_names[code],
                issue_week=issue_week,
                population=exposure.population,
                population_year=exposure.year,
                seasonal_sin=seasonal_sin,
                seasonal_cos=seasonal_cos,
                past_incidence=past,
                weather=weather,
            )
        )
    return rows


def _prediction_pool(rows: Sequence[OperationalRow], scaler: WeatherScaler) -> Pool:
    if not rows:
        raise LymeOperationalError("Operational prediction rows are empty")
    matrix: list[list[object]] = []
    baselines: list[float] = []
    for row in rows:
        if row.population_year >= row.issue_week.year:
            raise LymeOperationalError("Population year reaches prediction issue year")
        if row.past_incidence.latest_information_week >= row.issue_week:
            raise LymeOperationalError("Past-case feature reaches issue week")
        if row.weather.latest_week_end >= row.issue_week:
            raise LymeOperationalError("Weather feature reaches issue week")
        standardized = [
            (row.weather.values[name] - scaler.means[name])
            / scaler.standard_deviations[name]
            for name in WEATHER_FEATURE_COLUMNS
        ]
        if not all(math.isfinite(value) for value in standardized):
            raise LymeOperationalError("Standardized weather is non-finite")
        matrix.append(
            [
                row.municipality_code,
                row.seasonal_sin,
                row.seasonal_cos,
                row.past_incidence.incidence_per_100000,
                *standardized,
            ]
        )
        baselines.append(math.log(row.population / 100000.0))
    return Pool(
        data=matrix,
        cat_features=[FEATURE_COLUMNS.index("municipality_code")],
        feature_names=list(FEATURE_COLUMNS),
        baseline=np.asarray(baselines, dtype=np.float64),
        timestamp=[row.issue_week.toordinal() for row in rows],
    )


def assess_readiness(
    config: Mapping[str, Any],
    *,
    issue_week: date,
    weekly_weather_path: Path,
    weather_quality_path: Path,
    weekly_cases_path: Path | None = None,
    weekly_cases_provenance_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    try:
        parse_monday(issue_week.isoformat(), context="operational issue_week")
        checks["issue_week_is_monday"] = True
    except Exception as exc:
        checks["issue_week_is_monday"] = False
        details["issue_week_error"] = str(exc)
    paths = _artifact_paths(config, repo_root)
    checks["sealed_model_artifacts_present"] = all(
        paths[key].is_file() for key in ("model", "scaler", "manifest")
    )
    if checks["sealed_model_artifacts_present"]:
        try:
            _verify_existing_artifact(config, repo_root)
            checks["sealed_model_artifact_hashes_pass"] = True
        except Exception as exc:
            checks["sealed_model_artifact_hashes_pass"] = False
            details["sealed_model_error"] = str(exc)
    else:
        checks["sealed_model_artifact_hashes_pass"] = False
    cases_path = weekly_cases_path or _repo_path(
        config["inputs"]["operational_weekly_cases"], repo_root
    )
    cases_provenance_path = weekly_cases_provenance_path or _repo_path(
        config["inputs"]["operational_weekly_cases_provenance"], repo_root
    )
    checks["operational_weekly_cases_present"] = cases_path.is_file()
    checks["operational_weekly_cases_provenance_present"] = (
        cases_provenance_path.is_file()
    )
    if (
        checks["operational_weekly_cases_present"]
        and checks["operational_weekly_cases_provenance_present"]
    ):
        try:
            _read_case_provenance(cases_provenance_path, cases_path)
            checks["operational_weekly_cases_provenance_pass"] = True
        except Exception as exc:
            checks["operational_weekly_cases_provenance_pass"] = False
            details["weekly_cases_provenance_error"] = str(exc)
    else:
        checks["operational_weekly_cases_provenance_pass"] = False
    checks["operational_weekly_weather_present"] = weekly_weather_path.is_file()
    checks["operational_weather_quality_present"] = weather_quality_path.is_file()
    municipality_path = _repo_path(config["inputs"]["municipality"], repo_root)
    population_path = _repo_path(config["inputs"]["population"], repo_root)
    checks["canonical_municipality_present"] = municipality_path.is_file()
    checks["canonical_population_present"] = population_path.is_file()
    required_inputs_present = all(
        checks[key]
        for key in (
            "operational_weekly_cases_present",
            "operational_weekly_cases_provenance_present",
            "operational_weekly_weather_present",
            "operational_weather_quality_present",
            "canonical_municipality_present",
            "canonical_population_present",
        )
    )
    if required_inputs_present and checks["issue_week_is_monday"]:
        try:
            expected_count = int(
                config["prediction_contract"]["expected_municipality_count"]
            )
            municipalities = _read_municipalities(
                municipality_path, expected_count=expected_count
            )
            population = _read_population(population_path)
            cases = _read_operational_cases(
                cases_path,
                issue_week=issue_week,
                municipality_codes=set(municipalities),
            )
            weather, _ = _read_operational_weather(
                weekly_weather_path,
                weather_quality_path,
                issue_week=issue_week,
                municipality_codes=set(municipalities),
                allowed_vintages=set(
                    config["prediction_contract"]["allowed_weather_vintages"]
                ),
            )
            rows = _prepare_operational_rows(
                issue_week=issue_week,
                municipality_names=municipalities,
                population_by_key=population,
                weekly_cases=cases,
                weekly_weather=weather,
            )
            checks["operational_feature_contract_pass"] = len(rows) == expected_count
        except Exception as exc:
            checks["operational_feature_contract_pass"] = False
            details["operational_feature_error"] = str(exc)
    else:
        checks["operational_feature_contract_pass"] = False
    details["weekly_cases_path"] = str(cases_path)
    details["weekly_cases_provenance_path"] = str(cases_provenance_path)
    details["weekly_weather_path"] = str(weekly_weather_path)
    details["weather_quality_path"] = str(weather_quality_path)
    status = "ready" if all(checks.values()) else "blocked"
    return {
        "schema_version": 1,
        "status": status,
        "issue_week": issue_week.isoformat(),
        "checks": checks,
        "details": details,
        "missing_input_rule": config["prediction_contract"]["missing_input_rule"],
    }


def create_prediction_snapshot(
    config: Mapping[str, Any],
    *,
    issue_week: date,
    weekly_weather_path: Path,
    weather_quality_path: Path,
    weekly_cases_path: Path | None = None,
    weekly_cases_provenance_path: Path | None = None,
    generated_at: datetime | None = None,
    repo_root: Path = REPO_ROOT,
    publish_frontend: bool = True,
) -> dict[str, Any]:
    issue_week = parse_monday(issue_week.isoformat(), context="operational issue_week")
    readiness = assess_readiness(
        config,
        issue_week=issue_week,
        weekly_weather_path=weekly_weather_path,
        weather_quality_path=weather_quality_path,
        weekly_cases_path=weekly_cases_path,
        weekly_cases_provenance_path=weekly_cases_provenance_path,
        repo_root=repo_root,
    )
    output_directory = _repo_path(config["outputs"]["directory"], repo_root)
    readiness_path = output_directory / config["outputs"]["readiness"]
    _write_json(readiness_path, readiness)
    if readiness["status"] != "ready":
        raise LymeOperationalError(
            "Operational prediction is blocked; inspect prediction_readiness.json"
        )

    _verify_existing_artifact(config, repo_root)
    artifact_paths = _artifact_paths(config, repo_root)
    contract = config["prediction_contract"]
    expected_count = int(contract["expected_municipality_count"])
    municipality_path = _repo_path(config["inputs"]["municipality"], repo_root)
    population_path = _repo_path(config["inputs"]["population"], repo_root)
    cases_path = weekly_cases_path or _repo_path(
        config["inputs"]["operational_weekly_cases"], repo_root
    )
    cases_provenance_path = weekly_cases_provenance_path or _repo_path(
        config["inputs"]["operational_weekly_cases_provenance"], repo_root
    )
    municipalities = _read_municipalities(
        municipality_path, expected_count=expected_count
    )
    population = _read_population(population_path)
    weekly_cases = _read_operational_cases(
        cases_path,
        issue_week=issue_week,
        municipality_codes=set(municipalities),
    )
    case_provenance = _read_case_provenance(cases_provenance_path, cases_path)
    weekly_weather, weather_quality = _read_operational_weather(
        weekly_weather_path,
        weather_quality_path,
        issue_week=issue_week,
        municipality_codes=set(municipalities),
        allowed_vintages=set(contract["allowed_weather_vintages"]),
    )
    rows = _prepare_operational_rows(
        issue_week=issue_week,
        municipality_names=municipalities,
        population_by_key=population,
        weekly_cases=weekly_cases,
        weekly_weather=weekly_weather,
    )
    scaler = _load_scaler(artifact_paths["scaler"])
    model = CatBoostRegressor()
    model.load_model(str(artifact_paths["model"]))
    predictions = np.asarray(
        model.predict(_prediction_pool(rows, scaler), prediction_type="Exponent"),
        dtype=np.float64,
    )
    if predictions.shape != (expected_count,) or not np.isfinite(predictions).all():
        raise LymeOperationalError("Operational model returned invalid predictions")
    if bool(np.any(predictions < 0)):
        raise LymeOperationalError("Operational model returned negative predictions")

    target_start = issue_week + timedelta(weeks=1)
    target_end = issue_week + timedelta(weeks=4, days=6)
    prediction_rows: list[dict[str, Any]] = []
    for row, prediction in zip(rows, predictions, strict=True):
        prediction_rows.append(
            {
                "model_id": CHALLENGER_ID,
                "municipality_code": row.municipality_code,
                "municipality_name": row.municipality_name,
                "issue_week": issue_week.isoformat(),
                "target_window_start": target_start.isoformat(),
                "target_window_end": target_end.isoformat(),
                "predicted_reported_lyme_cases_next_4w": float(prediction),
                "prediction_status": "available",
                "population_exposure": row.population,
                "population_year": row.population_year,
                "past_4w_lyme_cases": row.past_incidence.case_count,
                "past_4w_lyme_incidence_per_100000": (
                    row.past_incidence.incidence_per_100000
                ),
                "latest_case_week_used": row.past_incidence.latest_information_week.isoformat(),
                "latest_weather_week_used": row.weather.latest_week_start.isoformat(),
                "weather_vintage": weather_quality["weather_vintage"],
                "interval_status": contract["interval_status"],
                "risk_category_status": contract["risk_category_status"],
            }
        )

    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sources = {
        "model": _path_record(artifact_paths["model"], repo_root),
        "weather_scaler": _path_record(artifact_paths["scaler"], repo_root),
        "model_manifest": _path_record(artifact_paths["manifest"], repo_root),
        "municipality": _path_record(municipality_path, repo_root),
        "population": _path_record(population_path, repo_root),
        "weekly_cases": _path_record(cases_path, repo_root),
        "weekly_cases_provenance": _path_record(cases_provenance_path, repo_root),
        "weekly_weather": _path_record(weekly_weather_path, repo_root),
        "weather_quality": _path_record(weather_quality_path, repo_root),
    }
    data_version = hashlib.sha256(
        "".join(sources[key]["sha256"] for key in sorted(sources)).encode("ascii")
    ).hexdigest()
    snapshot = {
        "schema_version": 1,
        "status": "available",
        "generated_at_utc": generated.isoformat(),
        "model_id": CHALLENGER_ID,
        "model_version": f"{CHALLENGER_ID}@{sources['model']['sha256']}",
        "data_version": data_version,
        "issue_week": issue_week.isoformat(),
        "target_window_start": target_start.isoformat(),
        "target_window_end": target_end.isoformat(),
        "horizon_weeks": 4,
        "weather_vintage": weather_quality["weather_vintage"],
        "municipality_count": len(prediction_rows),
        "interpretation": "municipality_level_expected_reported_case_count_not_personal_risk",
        "interval_status": contract["interval_status"],
        "risk_category_status": contract["risk_category_status"],
        "case_source": {
            "source_name": case_provenance["source_name"],
            "source_url": case_provenance["source_url"],
            "retrieved_at_utc": case_provenance["retrieved_at_utc"],
            "acquisition_method": case_provenance["acquisition_method"],
        },
        "sources": sources,
        "predictions": prediction_rows,
    }
    csv_path = output_directory / config["outputs"]["predictions_csv"]
    json_path = output_directory / config["outputs"]["predictions_json"]
    quality_path = output_directory / config["outputs"]["quality_summary"]
    _write_csv(csv_path, prediction_rows)
    _write_json(json_path, snapshot)
    quality = {
        "schema_version": 1,
        "status": "pass",
        "issue_week": issue_week.isoformat(),
        "municipality_count": len(prediction_rows),
        "weather_vintage": weather_quality["weather_vintage"],
        "prediction_range": {
            "minimum": float(predictions.min()),
            "maximum": float(predictions.max()),
        },
        "prediction_dataset": _path_record(csv_path, repo_root),
        "prediction_snapshot": _path_record(json_path, repo_root),
        "checks": {
            "sealed_model_hashes_pass": True,
            "all_municipalities_present": len(prediction_rows) == expected_count,
            "four_complete_past_case_weeks": True,
            "four_complete_past_weather_weeks": True,
            "latest_case_information_is_t_minus_1": True,
            "latest_weather_information_is_t_minus_1": True,
            "population_strictly_precedes_issue_year": True,
            "predictions_are_finite_and_nonnegative": True,
            "no_unvalidated_risk_categories_emitted": True,
        },
    }
    _write_json(quality_path, quality)
    if publish_frontend:
        frontend_path = _repo_path(config["outputs"]["frontend_json"], repo_root)
        _write_json(frontend_path, snapshot)
    return snapshot


def compare_prediction_snapshots(
    preliminary_path: Path, final_path: Path
) -> dict[str, Any]:
    preliminary = json.loads(preliminary_path.read_text(encoding="utf-8"))
    final = json.loads(final_path.read_text(encoding="utf-8"))
    if preliminary.get("issue_week") != final.get("issue_week"):
        raise LymeOperationalError("Bridge snapshots must have the same issue_week")
    if preliminary.get("weather_vintage") != "preliminary_era5_land_t":
        raise LymeOperationalError("Bridge preliminary snapshot has wrong weather vintage")
    if final.get("weather_vintage") != "final_era5_land":
        raise LymeOperationalError("Bridge final snapshot has wrong weather vintage")

    def indexed(payload: Mapping[str, Any]) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in payload.get("predictions", []):
            code = str(row["municipality_code"])
            if code in result:
                raise LymeOperationalError(f"Duplicate bridge prediction: {code}")
            result[code] = float(row["predicted_reported_lyme_cases_next_4w"])
        return result

    preliminary_values = indexed(preliminary)
    final_values = indexed(final)
    if set(preliminary_values) != set(final_values) or not preliminary_values:
        raise LymeOperationalError("Bridge prediction municipality support differs")
    differences = np.asarray(
        [final_values[code] - preliminary_values[code] for code in sorted(final_values)],
        dtype=np.float64,
    )
    return {
        "schema_version": 1,
        "status": "diagnostic_only_no_promotion_decision",
        "issue_week": preliminary["issue_week"],
        "municipality_count": len(differences),
        "difference_definition": "final_minus_preliminary",
        "metrics": {
            "mean_signed_difference_final_minus_preliminary": float(differences.mean()),
            "mae_final_minus_preliminary": float(np.abs(differences).mean()),
            "rmse_final_minus_preliminary": float(np.sqrt(np.square(differences).mean())),
            "maximum_absolute_difference": float(np.abs(differences).max()),
        },
        "promotion_thresholds": None,
        "automatic_promotion_allowed": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Operational Lyme prediction")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seal", help="Seal the deterministic frozen model refit")

    readiness_parser = subparsers.add_parser("readiness")
    readiness_parser.add_argument("--issue-week", required=True)
    readiness_parser.add_argument("--weekly-weather", type=Path, required=True)
    readiness_parser.add_argument("--weather-quality", type=Path, required=True)
    readiness_parser.add_argument("--weekly-cases", type=Path)
    readiness_parser.add_argument("--weekly-cases-provenance", type=Path)

    predict_parser = subparsers.add_parser("predict")
    predict_parser.add_argument("--issue-week", required=True)
    predict_parser.add_argument("--weekly-weather", type=Path, required=True)
    predict_parser.add_argument("--weather-quality", type=Path, required=True)
    predict_parser.add_argument("--weekly-cases", type=Path)
    predict_parser.add_argument("--weekly-cases-provenance", type=Path)
    predict_parser.add_argument("--no-frontend", action="store_true")

    bridge_parser = subparsers.add_parser("bridge")
    bridge_parser.add_argument("--preliminary", type=Path, required=True)
    bridge_parser.add_argument("--final", type=Path, required=True)
    bridge_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "seal":
        print(json.dumps(seal_frozen_model(config), indent=2, sort_keys=True))
        return 0
    if args.command == "readiness":
        issue = parse_monday(args.issue_week, context="operational issue_week")
        payload = assess_readiness(
            config,
            issue_week=issue,
            weekly_weather_path=args.weekly_weather,
            weather_quality_path=args.weather_quality,
            weekly_cases_path=args.weekly_cases,
            weekly_cases_provenance_path=args.weekly_cases_provenance,
        )
        output = _repo_path(config["outputs"]["directory"]) / config["outputs"]["readiness"]
        _write_json(output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "ready" else 2
    if args.command == "predict":
        issue = parse_monday(args.issue_week, context="operational issue_week")
        snapshot = create_prediction_snapshot(
            config,
            issue_week=issue,
            weekly_weather_path=args.weekly_weather,
            weather_quality_path=args.weather_quality,
            weekly_cases_path=args.weekly_cases,
            weekly_cases_provenance_path=args.weekly_cases_provenance,
            publish_frontend=not args.no_frontend,
        )
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0
    payload = compare_prediction_snapshots(args.preliminary, args.final)
    if args.output:
        _write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
