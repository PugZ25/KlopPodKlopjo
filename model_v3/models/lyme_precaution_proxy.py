from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import tempfile
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import catboost
import numpy as np
from catboost import CatBoostRegressor, Pool

from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS
from model_v3.models.non_ml_baselines import (
    file_record,
    parse_code,
    parse_monday,
    resolve_repo_path,
    validate_manifest_matches_folds,
    write_csv_rows,
)
from model_v3.models.seasonal_count_models import (
    build_population_history,
    read_development_population,
    read_development_target_metadata,
    read_selected_development_target_values,
    seasonal_terms,
    select_population_exposure,
)
from model_v3.models.weather_ablation import (
    IssueWeather,
    WeeklyWeather,
    WeatherScaler,
    fit_weather_scaler,
    issue_weather_features,
    read_weekly_weather,
)
from model_v3.validation.rolling_origin import (
    RollingOriginFold,
    TargetWindowRow,
    generate_rolling_origin_folds,
    load_config as load_validation_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "lyme_precaution_proxy.json"

NO_WEATHER_ID = "catboost_no_case_seasonal_municipality_offset"
COMPACT_WEATHER_ID = "catboost_no_case_compact_weather_offset"
CANDIDATE_IDS = (NO_WEATHER_ID, COMPACT_WEATHER_ID)
BASE_FEATURES = (
    "municipality_code",
    "seasonal_sin_annual",
    "seasonal_cos_annual",
)
COMPACT_WEATHER_FEATURES = (
    "t2m_mean_c_previous_4w_mean",
    "tp_sum_mm_previous_4w_sum",
    "stl1_mean_c_previous_4w_mean",
)

PREDICTION_COLUMNS = (
    "evaluation_scope",
    "fold_id",
    "validation_year",
    "candidate_id",
    "municipality_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "actual_target_lyme_cases_next_4w",
    "predicted_target_lyme_cases_next_4w",
    "population_exposure",
    "population_year",
    "actual_incidence_per_100000",
    "predicted_incidence_per_100000",
    "weather_used",
    "latest_weather_week_used",
)

FOLD_METRIC_COLUMNS = (
    "evaluation_scope",
    "fold_id",
    "validation_year",
    "candidate_id",
    "n_predictions",
    "mae",
    "rmse",
    "mean_poisson_deviance",
)

AGGREGATE_METRIC_COLUMNS = (
    "evaluation_scope",
    "candidate_id",
    "n_folds",
    "n_predictions",
    "pooled_mae",
    "pooled_rmse",
    "pooled_mean_poisson_deviance",
)


class LymePrecautionProxyError(ValueError):
    """Raised when the no-current-cases proxy contract is violated."""


@dataclass(frozen=True)
class ProxyRow:
    municipality_code: str
    issue_week: date
    target_window_start: date
    target_window_end: date
    target_value: int
    population: int
    population_year: int
    seasonal_sin: float
    seasonal_cos: float
    weather: IssueWeather | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catboost_structure_sha256(model: CatBoostRegressor) -> str:
    """Hash model structure while excluding CatBoost's volatile build metadata."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "model.json"
        model.save_model(str(path), format="json")
        payload = json.loads(path.read_text(encoding="utf-8"))
    model_info = payload.get("model_info", {})
    if not isinstance(model_info, dict):
        raise LymePrecautionProxyError("CatBoost structural model_info is invalid")
    for volatile_key in ("model_guid", "train_finish_time"):
        model_info.pop(volatile_key, None)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise LymePrecautionProxyError("Configuration must remain inside the repository")
    config = json.loads(resolved.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise LymePrecautionProxyError("Configuration schema_version must equal 1")
    if config.get("purpose", {}).get("runtime_case_inputs_allowed") is not False:
        raise LymePrecautionProxyError("Runtime case inputs must remain forbidden")
    if config.get("purpose", {}).get("direct_tick_observation_target_available") is not False:
        raise LymePrecautionProxyError("Direct tick target availability changed")
    candidates = config.get("candidates", {})
    if candidates.get("no_weather", {}).get("candidate_id") != NO_WEATHER_ID:
        raise LymePrecautionProxyError("No-weather candidate ID changed")
    if candidates.get("compact_weather", {}).get("candidate_id") != COMPACT_WEATHER_ID:
        raise LymePrecautionProxyError("Compact-weather candidate ID changed")
    expected_weather = [f"z_{name}" for name in COMPACT_WEATHER_FEATURES]
    if candidates["compact_weather"].get("features") != [*BASE_FEATURES, *expected_weather]:
        raise LymePrecautionProxyError("Compact weather feature contract changed")
    deployment = config.get("deployment_policy", {})
    if (
        deployment.get("weather_required_by_product") is not True
        or deployment.get("evidence_selected_candidate") != NO_WEATHER_ID
        or deployment.get("deployed_candidate") != COMPACT_WEATHER_ID
        or deployment.get("claim_that_weather_improved_validation_allowed") is not False
    ):
        raise LymePrecautionProxyError("Reviewed weather deployment policy changed")
    bridge = deployment.get("operational_source_bridge", {})
    increments = bridge.get("open_meteo_reported_increment", {})
    if (
        bridge.get("model_inputs") != list(COMPACT_WEATHER_FEATURES)
        or bridge.get("fail_closed_outside_final_training_support") is not True
        or set(increments) != set(COMPACT_WEATHER_FEATURES)
        or not all(float(increments[name]) > 0 for name in COMPACT_WEATHER_FEATURES)
        or bridge.get("support_tolerance_rule")
        != "half_reported_increment_for_means_and_half_hourly_increment_times_672_for_four_week_precipitation_sum"
        or not bridge.get("soil_moisture_excluded_reason")
    ):
        raise LymePrecautionProxyError("Operational weather source bridge changed")
    if config.get("final_fit", {}).get("runtime_recent_cases_required") is not False:
        raise LymePrecautionProxyError("Final runtime must not require recent cases")
    if config["final_fit"].get("runtime_weather_used_by_ai_score") is not True:
        raise LymePrecautionProxyError("Reviewed live score must use operational weather")
    return config


def _read_opened_2025_rows(
    path: Path,
) -> tuple[list[TargetWindowRow], dict[tuple[str, date], int]]:
    rows: list[TargetWindowRow] = []
    values: dict[tuple[str, date], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "system_type",
            "municipality_code",
            "issue_week",
            "target_window_start",
            "target_window_end",
            "actual_target_lyme_cases_next_4w",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise LymePrecautionProxyError("Opened 2025 prediction schema is incomplete")
        for index, source in enumerate(reader, start=1):
            if source["system_type"] != "final_selected_model":
                continue
            code = parse_code(source["municipality_code"], context=f"opened row {index}")
            issue = parse_monday(source["issue_week"], context=f"opened row {index}")
            start = date.fromisoformat(source["target_window_start"])
            end = date.fromisoformat(source["target_window_end"])
            if issue.year != 2025 or start != issue + timedelta(weeks=1):
                raise LymePrecautionProxyError("Opened 2025 target timing changed")
            if end != issue + timedelta(weeks=4) or end.year != 2025:
                raise LymePrecautionProxyError("Opened 2025 target horizon changed")
            try:
                value = int(source["actual_target_lyme_cases_next_4w"])
            except ValueError as exc:
                raise LymePrecautionProxyError("Opened 2025 target is not an integer") from exc
            if value < 0:
                raise LymePrecautionProxyError("Opened 2025 target is negative")
            key = (code, issue)
            if key in values:
                raise LymePrecautionProxyError(f"Duplicate opened 2025 target: {key}")
            values[key] = value
            rows.append(TargetWindowRow(code, issue, start, end, "complete", True))
    rows.sort(key=lambda row: (row.issue_week, row.municipality_code))
    if len(rows) != 47 * 212 or len({row.issue_week for row in rows}) != 47:
        raise LymePrecautionProxyError("Opened 2025 support is not 47 weeks x 212 municipalities")
    return rows, values


def _read_weather_extension(
    path: Path, quality_path: Path
) -> dict[tuple[str, date], WeeklyWeather]:
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if quality.get("status") != "pass":
        raise LymePrecautionProxyError("Weather extension quality did not pass")
    if quality.get("weekly_dataset", {}).get("sha256") != _sha256(path):
        raise LymePrecautionProxyError("Weather extension hash does not match quality record")
    result: dict[tuple[str, date], WeeklyWeather] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEEKLY_COLUMNS:
            raise LymePrecautionProxyError("Weather extension columns changed")
        for index, source in enumerate(reader, start=1):
            code = parse_code(source["municipality_code"], context=f"weather row {index}")
            week_start = parse_monday(source["week_start"], context=f"weather row {index}")
            week_end = date.fromisoformat(source["week_end"])
            status = source["weather_status"]
            if week_end != week_start + timedelta(days=6):
                raise LymePrecautionProxyError("Weather extension week_end changed")
            if status == "complete":
                values = {name: float(source[name]) for name in OUTPUT_VARIABLES}
                if not all(math.isfinite(value) for value in values.values()):
                    raise LymePrecautionProxyError("Weather extension contains non-finite values")
            elif status == "incomplete_source_week":
                values = None
            else:
                raise LymePrecautionProxyError(f"Unknown weather status: {status}")
            key = (code, week_start)
            if key in result:
                raise LymePrecautionProxyError(f"Duplicate extension weather row: {key}")
            result[key] = WeeklyWeather(code, week_start, week_end, status, values)
    return result


def _merge_weather(
    development: Mapping[tuple[str, date], WeeklyWeather],
    extension: Mapping[tuple[str, date], WeeklyWeather],
) -> dict[tuple[str, date], WeeklyWeather]:
    merged = dict(development)
    for key, new in extension.items():
        old = merged.get(key)
        if old is None or (old.status != "complete" and new.status == "complete"):
            merged[key] = new
        elif old.status == "complete" and new.status == "complete":
            if old.values is None or new.values is None:
                raise LymePrecautionProxyError("Complete weather overlap is empty")
            if any(
                not math.isclose(old.values[name], new.values[name], rel_tol=1e-12, abs_tol=1e-12)
                for name in OUTPUT_VARIABLES
            ):
                raise LymePrecautionProxyError(f"Weather overlap differs for {key}")
    return merged


def prepare_rows(
    metadata: Sequence[TargetWindowRow],
    targets: Mapping[tuple[str, date], int],
    population: Mapping[tuple[str, int], int],
) -> list[ProxyRow]:
    history = build_population_history(population)
    rows: list[ProxyRow] = []
    for source in metadata:
        key = (source.municipality_code, source.issue_week)
        if key not in targets:
            raise LymePrecautionProxyError(f"Target value is missing: {key}")
        exposure = select_population_exposure(
            history,
            municipality_code=source.municipality_code,
            issue_week=source.issue_week,
        )
        annual_sin, annual_cos = seasonal_terms(source.issue_week)
        rows.append(
            ProxyRow(
                municipality_code=source.municipality_code,
                issue_week=source.issue_week,
                target_window_start=source.target_window_start,
                target_window_end=source.target_window_end,
                target_value=targets[key],
                population=exposure.population,
                population_year=exposure.year,
                seasonal_sin=annual_sin,
                seasonal_cos=annual_cos,
            )
        )
    return sorted(rows, key=lambda row: (row.issue_week, row.municipality_code))


def attach_complete_weather(
    rows: Sequence[ProxyRow],
    weekly_weather: Mapping[tuple[str, date], WeeklyWeather],
) -> tuple[list[ProxyRow], int]:
    attached: list[ProxyRow] = []
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
        attached.append(replace(row, weather=weather))
    return attached, excluded


def feature_names(candidate_id: str) -> tuple[str, ...]:
    if candidate_id == NO_WEATHER_ID:
        return BASE_FEATURES
    if candidate_id == COMPACT_WEATHER_ID:
        return (*BASE_FEATURES, *(f"z_{name}" for name in COMPACT_WEATHER_FEATURES))
    raise LymePrecautionProxyError(f"Unknown candidate: {candidate_id}")


def _feature_matrix(
    rows: Sequence[ProxyRow], candidate_id: str, scaler: WeatherScaler | None
) -> list[list[object]]:
    matrix: list[list[object]] = []
    for row in rows:
        values: list[object] = [row.municipality_code, row.seasonal_sin, row.seasonal_cos]
        if candidate_id == COMPACT_WEATHER_ID:
            if row.weather is None or scaler is None:
                raise LymePrecautionProxyError("Compact-weather row or scaler is missing")
            values.extend(
                (row.weather.values[name] - scaler.means[name])
                / scaler.standard_deviations[name]
                for name in COMPACT_WEATHER_FEATURES
            )
        matrix.append(values)
    return matrix


def build_pool(
    rows: Sequence[ProxyRow],
    candidate_id: str,
    scaler: WeatherScaler | None,
    *,
    include_labels: bool,
) -> Pool:
    if not rows:
        raise LymePrecautionProxyError("CatBoost pool cannot be empty")
    names = feature_names(candidate_id)
    return Pool(
        data=_feature_matrix(rows, candidate_id, scaler),
        label=[row.target_value for row in rows] if include_labels else None,
        cat_features=[names.index("municipality_code")],
        feature_names=list(names),
        baseline=[math.log(row.population / 100000.0) for row in rows],
        timestamp=[row.issue_week.toordinal() for row in rows],
    )


def fit_model(
    rows: Sequence[ProxyRow],
    candidate_id: str,
    scaler: WeatherScaler | None,
    parameters: Mapping[str, Any],
) -> CatBoostRegressor:
    constructor = dict(parameters)
    prediction_type = constructor.pop("prediction_type")
    if prediction_type != "Exponent":
        raise LymePrecautionProxyError("Prediction type changed")
    model = CatBoostRegressor(eval_metric=constructor["loss_function"], **constructor)
    model.fit(build_pool(rows, candidate_id, scaler, include_labels=True))
    return model


def predict_model(
    model: CatBoostRegressor,
    rows: Sequence[ProxyRow],
    candidate_id: str,
    scaler: WeatherScaler | None,
) -> np.ndarray:
    values = np.asarray(
        model.predict(
            build_pool(rows, candidate_id, scaler, include_labels=False),
            prediction_type="Exponent",
        ),
        dtype=np.float64,
    )
    if values.shape != (len(rows),) or np.any(values <= 0) or not np.isfinite(values).all():
        raise LymePrecautionProxyError("Candidate returned invalid predictions")
    return values


def summarize(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    if actual.shape != predicted.shape or actual.ndim != 1 or len(actual) == 0:
        raise LymePrecautionProxyError("Metric arrays are invalid")
    positive = actual > 0
    contributions = predicted.copy()
    contributions[positive] = (
        actual[positive] * np.log(actual[positive] / predicted[positive])
        - actual[positive]
        + predicted[positive]
    )
    return {
        "n_predictions": len(actual),
        "mae": float(np.mean(np.abs(actual - predicted))),
        "rmse": float(np.sqrt(np.mean(np.square(actual - predicted)))),
        "mean_poisson_deviance": float(np.mean(2.0 * contributions)),
    }


def _prediction_records(
    rows: Sequence[ProxyRow],
    predictions: np.ndarray,
    *,
    evaluation_scope: str,
    fold_id: str,
    validation_year: int,
    candidate_id: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row, prediction in zip(rows, predictions, strict=True):
        records.append(
            {
                "evaluation_scope": evaluation_scope,
                "fold_id": fold_id,
                "validation_year": validation_year,
                "candidate_id": candidate_id,
                "municipality_code": row.municipality_code,
                "issue_week": row.issue_week,
                "target_window_start": row.target_window_start,
                "target_window_end": row.target_window_end,
                "actual_target_lyme_cases_next_4w": row.target_value,
                "predicted_target_lyme_cases_next_4w": float(prediction),
                "population_exposure": row.population,
                "population_year": row.population_year,
                "actual_incidence_per_100000": row.target_value / row.population * 100000.0,
                "predicted_incidence_per_100000": float(prediction) / row.population * 100000.0,
                "weather_used": candidate_id == COMPACT_WEATHER_ID,
                "latest_weather_week_used": (
                    row.weather.latest_week_start if row.weather is not None else None
                ),
            }
        )
    return records


def _quantiles(values: Sequence[float], count: int) -> list[dict[str, float]]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) == 0 or not np.isfinite(array).all():
        raise LymePrecautionProxyError("Display calibration values are invalid")
    probabilities = np.linspace(0.0, 1.0, count)
    return [
        {"percentile": float(probability * 100.0), "value": float(value)}
        for probability, value in zip(probabilities, np.quantile(array, probabilities), strict=True)
    ]


def _empirical_score(value: float, sorted_reference: np.ndarray) -> float:
    return float(np.searchsorted(sorted_reference, value, side="right") / len(sorted_reference) * 100.0)


def _display_level(score: float, low_upper: float, medium_upper: float) -> str:
    return "Nizko" if score <= low_upper else "Srednje" if score <= medium_upper else "Visoko"


def _read_kme_reference_incidence(path: Path) -> list[float]:
    values: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"candidate_id", "predicted_target_kme_cases_next_8w", "population_exposure"}
        if not required.issubset(reader.fieldnames or ()):
            raise LymePrecautionProxyError("KME fold prediction schema is incomplete")
        for source in reader:
            if source["candidate_id"] != "glm_seasonal_region_offset":
                continue
            prediction = float(source["predicted_target_kme_cases_next_8w"])
            population = int(source["population_exposure"])
            if prediction <= 0 or population <= 0:
                raise LymePrecautionProxyError("KME calibration input is invalid")
            values.append(prediction / population * 100000.0)
    if len(values) != 4236:
        raise LymePrecautionProxyError("KME calibration support changed")
    return values


def build_precaution_proxy(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    paths = {key: resolve_repo_path(value) for key, value in config["inputs"].items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise LymePrecautionProxyError(f"Required inputs are missing: {missing}")

    validation_config = load_validation_config(paths["validation_config"])
    policy = validation_config["policy"]
    target_path = resolve_repo_path(validation_config["input"]["path"])
    if target_path != paths["target"]:
        raise LymePrecautionProxyError("Validation and proxy target paths differ")
    development_metadata = read_development_target_metadata(
        target_path,
        development_start_year=policy["development_start_year"],
        development_end_year=policy["development_end_year"],
    )
    folds = generate_rolling_origin_folds(
        development_metadata,
        development_start_year=policy["development_start_year"],
        development_end_year=policy["development_end_year"],
        lockbox_year=policy["lockbox_year"],
    )
    validate_manifest_matches_folds(paths["validation_manifest"], folds)

    development_keys = {
        (row.municipality_code, row.issue_week)
        for fold in folds
        for row in (*fold.train_rows, *fold.validation_rows)
    }
    final_development_metadata = [
        row
        for row in development_metadata
        if row.target_training_eligible and row.target_window_end < date(2025, 1, 1)
    ]
    development_keys.update(
        (row.municipality_code, row.issue_week) for row in final_development_metadata
    )
    targets = read_selected_development_target_values(
        target_path, development_keys, lockbox_year=2025
    )
    opened_rows, opened_values = _read_opened_2025_rows(paths["opened_2025_predictions"])
    if set(targets).intersection(opened_values):
        raise LymePrecautionProxyError("Development and opened 2025 target keys overlap")
    targets.update(opened_values)
    population = read_development_population(paths["population"], lockbox_year=2026)

    development_weather, _ = read_weekly_weather(
        paths["development_weather"],
        paths["development_weather_quality"],
        lockbox_year=2026,
    )
    extension = _read_weather_extension(
        paths["weather_extension"], paths["weather_extension_quality"]
    )
    weekly_weather = _merge_weather(development_weather, extension)
    parameters = config["candidates"]["shared_parameters"]

    prediction_records: list[dict[str, Any]] = []
    fold_metrics: list[dict[str, Any]] = []
    development_fold_pairs: list[tuple[str, float, float]] = []

    evaluation_folds: list[tuple[str, str, int, Sequence[TargetWindowRow], Sequence[TargetWindowRow]]] = [
        (
            "development_rolling_origin",
            fold.fold_id,
            fold.validation_start.year,
            fold.train_rows,
            fold.validation_rows,
        )
        for fold in folds
    ]
    evaluation_folds.append(
        (
            "opened_2025_retrospective_audit",
            "opened_2025",
            2025,
            tuple(final_development_metadata),
            tuple(opened_rows),
        )
    )

    for scope, fold_id, validation_year, train_metadata, validation_metadata in evaluation_folds:
        base_train = prepare_rows(train_metadata, targets, population)
        base_validation = prepare_rows(validation_metadata, targets, population)
        train_rows, excluded_train = attach_complete_weather(base_train, weekly_weather)
        validation_rows, excluded_validation = attach_complete_weather(
            base_validation, weekly_weather
        )
        if excluded_validation or len(validation_rows) != len(base_validation):
            raise LymePrecautionProxyError(f"{fold_id} validation weather support is incomplete")
        if max(row.target_window_end for row in train_rows) >= min(
            row.issue_week for row in validation_rows
        ):
            raise LymePrecautionProxyError(f"{fold_id} training target reaches validation")
        if excluded_train < 0:
            raise LymePrecautionProxyError("Invalid excluded training count")
        scaler = fit_weather_scaler(train_rows)
        fold_candidate_mae: dict[str, float] = {}
        for candidate_id in CANDIDATE_IDS:
            model = fit_model(train_rows, candidate_id, scaler, parameters)
            predictions = predict_model(
                model, validation_rows, candidate_id, scaler
            )
            actual = np.asarray([row.target_value for row in validation_rows], dtype=np.float64)
            summary = summarize(actual, predictions)
            fold_candidate_mae[candidate_id] = float(summary["mae"])
            fold_metrics.append(
                {
                    "evaluation_scope": scope,
                    "fold_id": fold_id,
                    "validation_year": validation_year,
                    "candidate_id": candidate_id,
                    **summary,
                }
            )
            prediction_records.extend(
                _prediction_records(
                    validation_rows,
                    predictions,
                    evaluation_scope=scope,
                    fold_id=fold_id,
                    validation_year=validation_year,
                    candidate_id=candidate_id,
                )
            )
        if scope == "development_rolling_origin":
            development_fold_pairs.append(
                (
                    fold_id,
                    fold_candidate_mae[NO_WEATHER_ID],
                    fold_candidate_mae[COMPACT_WEATHER_ID],
                )
            )

    aggregate_metrics: list[dict[str, Any]] = []
    for scope in ("development_rolling_origin", "opened_2025_retrospective_audit"):
        for candidate_id in CANDIDATE_IDS:
            selected = [
                row
                for row in prediction_records
                if row["evaluation_scope"] == scope and row["candidate_id"] == candidate_id
            ]
            actual = np.asarray(
                [row["actual_target_lyme_cases_next_4w"] for row in selected], dtype=np.float64
            )
            predicted = np.asarray(
                [row["predicted_target_lyme_cases_next_4w"] for row in selected], dtype=np.float64
            )
            summary = summarize(actual, predicted)
            aggregate_metrics.append(
                {
                    "evaluation_scope": scope,
                    "candidate_id": candidate_id,
                    "n_folds": len(
                        {
                            row["fold_id"]
                            for row in selected
                        }
                    ),
                    "n_predictions": summary["n_predictions"],
                    "pooled_mae": summary["mae"],
                    "pooled_rmse": summary["rmse"],
                    "pooled_mean_poisson_deviance": summary["mean_poisson_deviance"],
                }
            )

    aggregate_index = {
        (row["evaluation_scope"], row["candidate_id"]): row for row in aggregate_metrics
    }
    dev_no_weather = aggregate_index[("development_rolling_origin", NO_WEATHER_ID)]
    dev_weather = aggregate_index[("development_rolling_origin", COMPACT_WEATHER_ID)]
    audit_no_weather = aggregate_index[("opened_2025_retrospective_audit", NO_WEATHER_ID)]
    audit_weather = aggregate_index[("opened_2025_retrospective_audit", COMPACT_WEATHER_ID)]
    metric_names = ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance")
    improved_folds = sum(weather < baseline for _, baseline, weather in development_fold_pairs)
    weather_selected = (
        all(float(dev_weather[name]) < float(dev_no_weather[name]) for name in metric_names)
        and improved_folds
        >= config["selection_rule"]["weather_candidate_minimum_improved_development_folds"]
        and all(float(audit_weather[name]) < float(audit_no_weather[name]) for name in metric_names)
    )
    evidence_selected_candidate = COMPACT_WEATHER_ID if weather_selected else NO_WEATHER_ID
    deployment = config["deployment_policy"]
    if evidence_selected_candidate != deployment["evidence_selected_candidate"]:
        raise LymePrecautionProxyError(
            "Recorded deployment override no longer matches the evaluation evidence"
        )
    selected_candidate = deployment["deployed_candidate"]
    selection = {
        "selected_candidate_id": selected_candidate,
        "evidence_selected_candidate_id": evidence_selected_candidate,
        "deployed_candidate_id": selected_candidate,
        "weather_candidate_passed_evidence_gate": weather_selected,
        "weather_required_by_product": deployment["weather_required_by_product"],
        "deployment_override_reason": deployment["override_reason"],
        "claim_that_weather_improved_validation_allowed": deployment[
            "claim_that_weather_improved_validation_allowed"
        ],
        "development_weather_improved_fold_count": improved_folds,
        "development_fold_count": len(development_fold_pairs),
        "rule": config["selection_rule"],
        "evidence_reason": (
            "compact_weather_passed_every_predeclared_gate"
            if weather_selected
            else "compact_weather_failed_stability_and_or_opened_2025_gates"
        ),
        "runtime_recent_cases_required": False,
        "runtime_weather_used_by_ai_score": True,
        "untouched_lockbox_status": "none_remaining_after_2025_was_opened",
    }

    selected_development_predictions = [
        row
        for row in prediction_records
        if row["evaluation_scope"] == "development_rolling_origin"
        and row["candidate_id"] == selected_candidate
    ]
    reference_incidence = np.asarray(
        [row["predicted_incidence_per_100000"] for row in selected_development_predictions],
        dtype=np.float64,
    )
    sorted_reference = np.sort(reference_incidence)
    calibration_config = config["display_calibration"]
    low_upper = float(calibration_config["low_upper_percentile"])
    medium_upper = float(calibration_config["medium_upper_percentile"])
    band_rows: dict[str, list[dict[str, Any]]] = {label: [] for label in calibration_config["labels"]}
    for row in selected_development_predictions:
        score = _empirical_score(float(row["predicted_incidence_per_100000"]), sorted_reference)
        band_rows[_display_level(score, low_upper, medium_upper)].append(row)
    band_summary = []
    for label in calibration_config["labels"]:
        rows = band_rows[label]
        band_summary.append(
            {
                "label": label,
                "n": len(rows),
                "mean_actual_incidence_per_100000": statistics.fmean(
                    float(row["actual_incidence_per_100000"]) for row in rows
                ),
                "mean_predicted_incidence_per_100000": statistics.fmean(
                    float(row["predicted_incidence_per_100000"]) for row in rows
                ),
            }
        )
    observed_means = [row["mean_actual_incidence_per_100000"] for row in band_summary]
    if observed_means != sorted(observed_means) or len(set(observed_means)) != 3:
        raise LymePrecautionProxyError("Display bands are not monotonic in development evidence")
    kme_reference = _read_kme_reference_incidence(paths["kme_fold_predictions"])
    display_calibration = {
        "schema_version": 1,
        "interpretation": "relative_percentile_not_absolute_or_personal_risk",
        "lyme": {
            "reference_scope": calibration_config["reference"],
            "reference_n": len(reference_incidence),
            "quantiles": _quantiles(
                reference_incidence, int(calibration_config["quantile_grid_points"])
            ),
            "low_upper_percentile": low_upper,
            "medium_upper_percentile": medium_upper,
            "development_band_summary": band_summary,
        },
        "kme": {
            "reference_scope": "selected_KME_model_rolling_origin_predictions_2018_through_2025",
            "reference_n": len(kme_reference),
            "quantiles": _quantiles(
                kme_reference, int(calibration_config["quantile_grid_points"])
            ),
            "low_upper_percentile": low_upper,
            "medium_upper_percentile": medium_upper,
            "spatial_scope": "statistical_region_not_municipality",
        },
    }

    all_final_metadata = [*final_development_metadata, *opened_rows]
    final_base_rows = prepare_rows(all_final_metadata, targets, population)
    final_rows, final_rows_excluded_incomplete_weather = attach_complete_weather(
        final_base_rows, weekly_weather
    )
    if len({row.municipality_code for row in final_rows}) != 212:
        raise LymePrecautionProxyError("Final fit does not contain 212 municipalities")
    final_scaler = fit_weather_scaler(final_rows)
    final_model = fit_model(final_rows, selected_candidate, final_scaler, parameters)

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    output_paths = {
        key: output_directory / filename
        for key, filename in config["outputs"].items()
        if key not in {"directory", "report"}
    }
    if any(path.parent != output_directory for path in output_paths.values()):
        raise LymePrecautionProxyError("Output filename contains a path")
    final_model.save_model(str(output_paths["model"]))
    compact_scaler = {
        "schema_version": 1,
        "feature_order": list(COMPACT_WEATHER_FEATURES),
        "fit_scope": "all_eligible_2016_2025_rows_with_complete_ERA5_Land_t_minus_4_through_t_minus_1",
        "means": {
            name: final_scaler.means[name] for name in COMPACT_WEATHER_FEATURES
        },
        "standard_deviations": {
            name: final_scaler.standard_deviations[name]
            for name in COMPACT_WEATHER_FEATURES
        },
        "training_support_minimums": {
            name: min(row.weather.values[name] for row in final_rows if row.weather is not None)
            for name in COMPACT_WEATHER_FEATURES
        },
        "training_support_maximums": {
            name: max(row.weather.values[name] for row in final_rows if row.weather is not None)
            for name in COMPACT_WEATHER_FEATURES
        },
        "operational_support_tolerances": {
            name: float(deployment["operational_source_bridge"][
                "open_meteo_reported_increment"
            ][name])
            / 2.0
            * (672 if name == "tp_sum_mm_previous_4w_sum" else 1)
            for name in COMPACT_WEATHER_FEATURES
        },
        "operational_support_tolerance_rule": deployment[
            "operational_source_bridge"
        ]["support_tolerance_rule"],
    }
    _write_json(output_paths["weather_scaler"], compact_scaler)
    _write_json(output_paths["display_calibration"], display_calibration)
    write_csv_rows(output_paths["fold_predictions"], PREDICTION_COLUMNS, prediction_records)
    write_csv_rows(output_paths["fold_metrics"], FOLD_METRIC_COLUMNS, fold_metrics)
    write_csv_rows(output_paths["aggregate_metrics"], AGGREGATE_METRIC_COLUMNS, aggregate_metrics)
    _write_json(output_paths["selection"], selection)

    model_manifest = {
        "schema_version": 1,
        "status": "sealed_for_no_current_case_inference",
        "selected_candidate_id": selected_candidate,
        "model_sha256": _sha256(output_paths["model"]),
        "weather_scaler_sha256": _sha256(output_paths["weather_scaler"]),
        "model_structural_sha256_excluding_volatile_metadata": (
            _catboost_structure_sha256(final_model)
        ),
        "feature_names": list(feature_names(selected_candidate)),
        "population_baseline": "log(population/100000)",
        "training_period": {
            "first_issue_week": min(row.issue_week for row in final_rows).isoformat(),
            "last_issue_week": max(row.issue_week for row in final_rows).isoformat(),
            "rows": len(final_rows),
            "rows_excluded_incomplete_weather": final_rows_excluded_incomplete_weather,
            "includes_opened_2025_outcomes": True,
        },
        "runtime_contract": {
            "recent_cases_required": False,
            "weather_used_by_ai_score": True,
            "runtime_weather_source": "Open-Meteo DWD ICON mapped to the frozen ERA5-Land compact feature schema",
            "source_bridge_validation_status": "mapped_variables_and_units_with_training_support_guard_without_completed_cross_source_bias_calibration",
            "operational_weather_features": list(COMPACT_WEATHER_FEATURES),
            "soil_moisture_excluded_from_score": "DWD_ICON_soil_moisture_was_outside_ERA5_Land_training_support_in_live_2026_08_31_audit",
            "weather_displayed_as_separate_context": True,
            "output_is_personal_risk": False,
            "output_is_direct_tick_measurement": False,
        },
        "catboost_version": catboost.__version__,
        "parameters": parameters,
        "code": file_record(Path(__file__).resolve()),
        "input_sources": {key: file_record(path) for key, path in paths.items()},
        "configuration": file_record(config_path),
        "feature_importance": [
            {"feature": name, "importance": float(value)}
            for name, value in zip(
                feature_names(selected_candidate),
                final_model.get_feature_importance(
                    build_pool(
                        final_rows,
                        selected_candidate,
                        final_scaler,
                        include_labels=True,
                    )
                ),
                strict=True,
            )
        ],
    }
    _write_json(output_paths["model_manifest"], model_manifest)
    quality_summary = {
        "schema_version": 1,
        "status": "pass",
        "selection": selection,
        "checks": {
            "runtime_case_features_absent": True,
            "runtime_weather_deployment_override_is_explicit": (
                selected_candidate == COMPACT_WEATHER_ID
                and evidence_selected_candidate == NO_WEATHER_ID
                and deployment["claim_that_weather_improved_validation_allowed"] is False
            ),
            "runtime_weather_training_support_bounds_recorded": all(
                compact_scaler["training_support_minimums"][name]
                < compact_scaler["training_support_maximums"][name]
                for name in COMPACT_WEATHER_FEATURES
            ),
            "runtime_weather_source_resolution_tolerances_recorded": all(
                compact_scaler["operational_support_tolerances"][name] > 0
                for name in COMPACT_WEATHER_FEATURES
            ),
            "development_rolling_origin_used": True,
            "four_week_target_embargo_preserved": True,
            "opened_2025_labelled_retrospective_not_lockbox": True,
            "display_bands_monotonic_in_development_evidence": True,
            "personal_risk_output_absent": True,
            "direct_tick_measurement_claim_absent": True,
        },
        "outputs": {
            key: file_record(path)
            for key, path in output_paths.items()
            if key != "quality_summary" and path.is_file()
        },
    }
    _write_json(output_paths["quality_summary"], quality_summary)

    report_path = resolve_repo_path(config["outputs"]["report"])
    report_path.write_text(
        "# No-current-cases precaution proxy\n\n"
        "This phase evaluates a public-facing precaution proxy whose weekly inference does not use recent case reports. "
        "The training target remains reported Lyme cases in t+1..t+4, so the output is a relative disease-burden proxy, not a direct tick count, infection probability, diagnosis, or personal risk.\n\n"
        f"Evidence-selected candidate: `{evidence_selected_candidate}`.\n\n"
        f"Deployed candidate under the reviewed weather-required product policy: `{selected_candidate}`.\n\n"
        f"Compact weather improved MAE in {improved_folds}/{len(development_fold_pairs)} development folds. "
        f"Weather passed the predictive evidence gate: **{str(weather_selected).lower()}**. "
        "The weather candidate remains deployed only because weather was explicitly made a product requirement; this is an override, not a claim of improved validation.\n\n"
        "Operational inputs are four-week air temperature, precipitation, and shallow-soil temperature. "
        "DWD ICON soil moisture is excluded from the score because the live audit placed it outside ERA5-Land training support. "
        "Inference fails closed when a scored operational weather feature is outside its final training range; cross-source bias calibration remains incomplete.\n\n"
        "The display score is the selected model's predicted incidence percentile against rolling-origin development predictions from 2017-2024. Low/medium/high are relative communication bands and never mean safe/unsafe.\n",
        encoding="utf-8",
    )
    return quality_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the no-current-cases Lyme precaution proxy")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_precaution_proxy(args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
