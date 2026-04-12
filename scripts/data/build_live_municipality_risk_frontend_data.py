from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catboost import CatBoostClassifier, Pool

from ml.training.config import load_config


FRONTEND_ENVIRONMENTAL_RISK_PATH = (
    REPO_ROOT / "frontend" / "src" / "data" / "environmentalRisk.ts"
)
FRONTEND_LIVE_RISK_PATH = (
    REPO_ROOT / "frontend" / "src" / "data" / "liveMunicipalityRisk.ts"
)
TRAINING_DATASET_PATH = (
    REPO_ROOT / "data" / "processed" / "training" / "obcina_weekly_tick_borne_catboost_ready.csv"
)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT_SECONDS = 45
MAX_FETCH_WORKERS = 8
OPEN_METEO_MAX_ATTEMPTS = 5
OPEN_METEO_BASE_BACKOFF_SECONDS = 2.0

OPEN_METEO_HOURLY_COLUMNS = {
    "temperature_2m": "air_temperature_c",
    "relative_humidity_2m": "relative_humidity_pct",
    "precipitation": "precipitation_hourly_mm",
    "soil_temperature_6cm": "soil_temperature_level_1_c",
    "soil_temperature_18cm": "soil_temperature_level_2_c",
    "soil_moisture_3_to_9cm": "soil_water_layer_1_m3_m3",
}
OPEN_METEO_HOURLY_QUERY = ",".join(OPEN_METEO_HOURLY_COLUMNS)

WEATHER_BASE_COLUMNS = [
    "air_temperature_c_mean",
    "relative_humidity_pct_mean",
    "precipitation_sum_mm",
    "soil_temperature_level_1_c_mean",
    "soil_temperature_level_2_c_mean",
    "soil_water_layer_1_m3_m3_mean",
    "humidity_hours_ge_80_sum",
    "wet_hours_ge_0_1mm_sum",
    "tick_activity_window_hours_sum",
    "growing_degree_hours_base_5_c_sum",
    "rainy_days_ge_1mm_count",
    "humid_days_ge_16h_count",
    "tick_favorable_days_ge_6h_count",
]
LAG_FEATURE_COLUMNS = [
    "air_temperature_c_mean",
    "relative_humidity_pct_mean",
    "precipitation_sum_mm",
    "soil_water_layer_1_m3_m3_mean",
    "tick_activity_window_hours_sum",
]
CALENDAR_FEATURE_COLUMNS = ["week_of_year_sin", "week_of_year_cos"]
DYNAMIC_FEATURE_COLUMNS = set(WEATHER_BASE_COLUMNS + CALENDAR_FEATURE_COLUMNS)
for lag_column in LAG_FEATURE_COLUMNS:
    DYNAMIC_FEATURE_COLUMNS.add(f"{lag_column}_lag_1w")
    DYNAMIC_FEATURE_COLUMNS.add(f"{lag_column}_lag_2w")
    DYNAMIC_FEATURE_COLUMNS.add(f"{lag_column}_lag_4w")
    DYNAMIC_FEATURE_COLUMNS.add(f"{lag_column}_rolling_4w_mean")

MODULE_HEADER = """export type RiskLevel = 'Nizko' | 'Srednje' | 'Visoko'

export type DiseaseModelKey = 'borelioza' | 'kme'

export type LiveMunicipalityRiskLocation = {
  id: string
  municipalityCode: string
  municipalityName: string
  score: number
  level: RiskLevel
  trendDeltaScore: number
  trendLabel: string
  weekStart: string
  weekEnd: string
  coordinates: [number, number]
}

export type LiveMunicipalityRiskModel = {
  key: DiseaseModelKey
  diseaseLabel: string
  modelId: string
  legacyResearchModelId: string
  asOfDate: string
  generatedAt: string
  referenceWeekStart: string
  referenceWeekEnd: string
  snapshotLabel: string
  weatherSource: string
  methodologyNote: string
  purpose: string
  disclaimer: string
  scoreExplanation: string
  topDrivers: string[]
  thresholds: {
    lowUpper: number
    mediumUpper: number
  }
  locations: LiveMunicipalityRiskLocation[]
  featuredLocations: Array<{
    municipalityName: string
    municipalityCode: string
    level: RiskLevel
    score: number
    id: string
  }>
}

export const liveMunicipalityRiskModels: Record<DiseaseModelKey, LiveMunicipalityRiskModel> = """


@dataclass(frozen=True)
class ModelSpec:
    key: str
    config_path: Path
    model_path: Path
    holdout_predictions_path: Path


MODEL_SPECS = (
    ModelSpec(
        key="borelioza",
        config_path=REPO_ROOT / "ml" / "training" / "example_tick_borne_lyme_env_v2_config.json",
        model_path=REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_lyme_env_v2"
        / "model.cbm",
        holdout_predictions_path=REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_lyme_env_v2"
        / "holdout_predictions.csv",
    ),
    ModelSpec(
        key="kme",
        config_path=REPO_ROOT / "ml" / "training" / "example_tick_borne_kme_env_v2_config.json",
        model_path=REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_kme_env_v2"
        / "model.cbm",
        holdout_predictions_path=REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_kme_env_v2"
        / "holdout_predictions.csv",
    ),
)


@dataclass(frozen=True)
class ReferenceWindow:
    as_of_date: date
    history_start: date
    reference_week_start: date
    reference_week_end: date


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate live municipality risk frontend data from env_v2 CatBoost models "
            "and Open-Meteo weather history for the latest completed hackathon snapshot."
        )
    )
    parser.add_argument(
        "--as-of-date",
        help="Reference date in YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Maximum concurrent Open-Meteo requests.",
    )
    parser.add_argument(
        "--output-path",
        default=str(FRONTEND_LIVE_RISK_PATH),
        help="Output TypeScript module path.",
    )
    return parser


def load_existing_environmental_risk_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    marker = "export const environmentalRiskModels"
    start = text.index("{", text.index(marker))
    return json.loads(text[start:])


def build_coordinate_lookup(existing_data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    lookup: dict[str, tuple[float, float]] = {}
    for model_payload in existing_data.values():
        for location in model_payload["locations"]:
            lookup[str(location["municipalityCode"])] = tuple(location["coordinates"])
    return lookup


def percentile_threshold(sorted_values: list[float], percentile: float) -> float:
    index = (len(sorted_values) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[lower]
    lower_weight = upper - index
    upper_weight = index - lower
    return (sorted_values[lower] * lower_weight) + (sorted_values[upper] * upper_weight)


def classify_level(value: float, low_upper: float, medium_upper: float) -> str:
    if value < low_upper:
        return "Nizko"
    if value < medium_upper:
        return "Srednje"
    return "Visoko"


def score_percentile(sorted_values: list[float], value: float) -> int:
    rank = bisect.bisect_right(sorted_values, value)
    return round((100 * rank) / len(sorted_values))


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def resolve_reference_window(as_of_date: date) -> ReferenceWindow:
    days_since_sunday = (as_of_date.weekday() + 1) % 7
    reference_week_end = as_of_date - timedelta(days=days_since_sunday)
    reference_week_start = reference_week_end - timedelta(days=6)
    history_start = reference_week_start - timedelta(days=35)
    return ReferenceWindow(
        as_of_date=as_of_date,
        history_start=history_start,
        reference_week_start=reference_week_start,
        reference_week_end=reference_week_end,
    )


def build_calendar_features(week_start_value: date) -> dict[str, float]:
    iso_year, iso_week, _ = week_start_value.isocalendar()
    angle = (2.0 * math.pi * iso_week) / 52.1775
    return {
        "week_of_year_sin": math.sin(angle),
        "week_of_year_cos": math.cos(angle),
    }


def load_static_feature_lookup(
    dataset_path: Path,
    *,
    required_columns: set[str],
) -> dict[str, dict[str, object]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Training dataset is missing a header row.")

        missing = sorted(required_columns - set(reader.fieldnames))
        if missing:
            raise ValueError(
                "Training dataset is missing required static columns: " + ", ".join(missing)
            )

        lookup: dict[str, dict[str, object]] = {}
        for row in reader:
            municipality_code = str(row["obcina_sifra"]).strip()
            feature_values: dict[str, object] = {
                "obcina_naziv": str(row["obcina_naziv"]).strip(),
            }
            for column in required_columns:
                if column in {"obcina_sifra", "obcina_naziv"}:
                    continue
                raw_value = row[column].strip()
                if column == "dominant_clc_code":
                    feature_values[column] = raw_value or "__MISSING__"
                    continue
                feature_values[column] = float(raw_value) if raw_value else math.nan
            lookup[municipality_code] = feature_values

    if not lookup:
        raise ValueError(f"No municipality rows found in training dataset {dataset_path}.")
    return lookup


def load_holdout_values(path: Path) -> list[float]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        values = sorted(
            float(row["prediction_probability"])
            for row in rows
            if row["split"] in {"validation", "test"}
        )
    if not values:
        raise ValueError(f"No holdout prediction probabilities found in {path}.")
    return values


def build_open_meteo_url(*, latitude: float, longitude: float, start_date: date, end_date: date) -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": OPEN_METEO_HOURLY_QUERY,
            "models": "best_match",
            "timezone": "GMT",
        }
    )
    return f"{OPEN_METEO_FORECAST_URL}?{query}"


def fetch_open_meteo_hourly(
    *,
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    request = urllib.request.Request(
        build_open_meteo_url(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        ),
        headers={"User-Agent": "KlopPodKlopjo/1.0"},
    )
    for attempt in range(1, OPEN_METEO_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=OPEN_METEO_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == OPEN_METEO_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Open-Meteo request failed for {latitude:.4f}, {longitude:.4f}: {exc}"
                ) from exc
            retry_after = exc.headers.get("Retry-After")
            backoff_seconds = (
                float(retry_after)
                if retry_after and retry_after.isdigit()
                else OPEN_METEO_BASE_BACKOFF_SECONDS * attempt
            )
            time.sleep(backoff_seconds)
        except urllib.error.URLError as exc:
            if attempt == OPEN_METEO_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Open-Meteo request failed for {latitude:.4f}, {longitude:.4f}: {exc}"
                ) from exc
            time.sleep(OPEN_METEO_BASE_BACKOFF_SECONDS * attempt)

    raise RuntimeError(
        f"Open-Meteo request failed for {latitude:.4f}, {longitude:.4f} after retries."
    )


def build_daily_rows_from_hourly(payload: dict[str, Any]) -> list[dict[str, object]]:
    hourly = payload.get("hourly")
    if not hourly:
        raise ValueError("Open-Meteo response is missing 'hourly'.")

    required_columns = ["time", *OPEN_METEO_HOURLY_COLUMNS]
    missing = [column for column in required_columns if column not in hourly]
    if missing:
        raise ValueError(
            "Open-Meteo response is missing required hourly columns: " + ", ".join(missing)
        )

    daily_buckets: dict[date, dict[str, float]] = {}
    for index, timestamp_text in enumerate(hourly["time"]):
        timestamp = datetime.fromisoformat(timestamp_text)
        day = timestamp.date()
        bucket = daily_buckets.setdefault(
            day,
            {
                "hour_count": 0.0,
                "air_temperature_sum": 0.0,
                "relative_humidity_sum": 0.0,
                "precipitation_sum_mm": 0.0,
                "soil_temperature_level_1_sum": 0.0,
                "soil_temperature_level_2_sum": 0.0,
                "soil_water_layer_1_sum": 0.0,
                "humidity_hours_ge_80_sum": 0.0,
                "humidity_hours_ge_90_sum": 0.0,
                "wet_hours_ge_0_1mm_sum": 0.0,
                "tick_activity_window_hours_sum": 0.0,
                "growing_degree_hours_base_5_c_sum": 0.0,
            },
        )

        temperature = _coerce_required_float(hourly["temperature_2m"][index], "temperature_2m")
        humidity = _coerce_required_float(
            hourly["relative_humidity_2m"][index],
            "relative_humidity_2m",
        )
        precipitation = _coerce_required_float(hourly["precipitation"][index], "precipitation")
        soil_temperature_level_1 = _coerce_required_float(
            hourly["soil_temperature_6cm"][index],
            "soil_temperature_6cm",
        )
        soil_temperature_level_2 = _coerce_required_float(
            hourly["soil_temperature_18cm"][index],
            "soil_temperature_18cm",
        )
        soil_water_layer_1 = _coerce_required_float(
            hourly["soil_moisture_3_to_9cm"][index],
            "soil_moisture_3_to_9cm",
        )

        bucket["hour_count"] += 1.0
        bucket["air_temperature_sum"] += temperature
        bucket["relative_humidity_sum"] += humidity
        bucket["precipitation_sum_mm"] += precipitation
        bucket["soil_temperature_level_1_sum"] += soil_temperature_level_1
        bucket["soil_temperature_level_2_sum"] += soil_temperature_level_2
        bucket["soil_water_layer_1_sum"] += soil_water_layer_1
        bucket["humidity_hours_ge_80_sum"] += 1.0 if humidity >= 80.0 else 0.0
        bucket["humidity_hours_ge_90_sum"] += 1.0 if humidity >= 90.0 else 0.0
        bucket["wet_hours_ge_0_1mm_sum"] += 1.0 if precipitation >= 0.1 else 0.0
        bucket["tick_activity_window_hours_sum"] += (
            1.0 if 7.0 <= temperature <= 25.0 and humidity >= 80.0 else 0.0
        )
        bucket["growing_degree_hours_base_5_c_sum"] += max(temperature - 5.0, 0.0)

    daily_rows: list[dict[str, object]] = []
    for day, bucket in sorted(daily_buckets.items()):
        hour_count = bucket["hour_count"]
        if hour_count <= 0:
            continue
        daily_rows.append(
            {
                "date": day,
                "air_temperature_c_mean": bucket["air_temperature_sum"] / hour_count,
                "relative_humidity_pct_mean": bucket["relative_humidity_sum"] / hour_count,
                "precipitation_sum_mm": bucket["precipitation_sum_mm"],
                "soil_temperature_level_1_c_mean": bucket["soil_temperature_level_1_sum"]
                / hour_count,
                "soil_temperature_level_2_c_mean": bucket["soil_temperature_level_2_sum"]
                / hour_count,
                "soil_water_layer_1_m3_m3_mean": bucket["soil_water_layer_1_sum"] / hour_count,
                "humidity_hours_ge_80_sum": bucket["humidity_hours_ge_80_sum"],
                "humidity_hours_ge_90_sum": bucket["humidity_hours_ge_90_sum"],
                "wet_hours_ge_0_1mm_sum": bucket["wet_hours_ge_0_1mm_sum"],
                "tick_activity_window_hours_sum": bucket["tick_activity_window_hours_sum"],
                "growing_degree_hours_base_5_c_sum": bucket["growing_degree_hours_base_5_c_sum"],
            }
        )

    return daily_rows


def _coerce_required_float(value: object, column: str) -> float:
    if value is None:
        raise ValueError(f"Open-Meteo hourly column '{column}' contains null values.")
    return float(value)


def build_weekly_rows_from_daily(
    daily_rows: list[dict[str, object]],
    *,
    history_start: date,
) -> list[dict[str, object]]:
    buckets: dict[date, list[dict[str, object]]] = {}
    for row in daily_rows:
        current_date = row["date"]
        if not isinstance(current_date, date):
            raise ValueError("Daily row is missing a valid date.")
        week_start = current_date - timedelta(days=current_date.weekday())
        buckets.setdefault(week_start, []).append(row)

    weekly_rows: list[dict[str, object]] = []
    for week_start, rows in sorted(buckets.items()):
        if week_start < history_start:
            continue
        if len(rows) != 7:
            raise ValueError(
                f"Expected 7 daily rows for week {week_start.isoformat()}, got {len(rows)}."
            )

        rows = sorted(rows, key=lambda row: row["date"])
        temperature_values = [float(row["air_temperature_c_mean"]) for row in rows]
        humidity_values = [float(row["relative_humidity_pct_mean"]) for row in rows]
        precipitation_values = [float(row["precipitation_sum_mm"]) for row in rows]

        weekly_row = {
            "week_start": week_start,
            "week_end": week_start + timedelta(days=6),
            "air_temperature_c_mean": sum(temperature_values) / len(temperature_values),
            "relative_humidity_pct_mean": sum(humidity_values) / len(humidity_values),
            "precipitation_sum_mm": sum(precipitation_values),
            "soil_temperature_level_1_c_mean": _mean_for_rows(
                rows,
                "soil_temperature_level_1_c_mean",
            ),
            "soil_temperature_level_2_c_mean": _mean_for_rows(
                rows,
                "soil_temperature_level_2_c_mean",
            ),
            "soil_water_layer_1_m3_m3_mean": _mean_for_rows(
                rows,
                "soil_water_layer_1_m3_m3_mean",
            ),
            "humidity_hours_ge_80_sum": _sum_for_rows(rows, "humidity_hours_ge_80_sum"),
            "wet_hours_ge_0_1mm_sum": _sum_for_rows(rows, "wet_hours_ge_0_1mm_sum"),
            "tick_activity_window_hours_sum": _sum_for_rows(
                rows,
                "tick_activity_window_hours_sum",
            ),
            "growing_degree_hours_base_5_c_sum": _sum_for_rows(
                rows,
                "growing_degree_hours_base_5_c_sum",
            ),
            "rainy_days_ge_1mm_count": sum(1 for value in precipitation_values if value >= 1.0),
            "humid_days_ge_16h_count": sum(
                1 for row in rows if float(row["humidity_hours_ge_80_sum"]) >= 16.0
            ),
            "tick_favorable_days_ge_6h_count": sum(
                1 for row in rows if float(row["tick_activity_window_hours_sum"]) >= 6.0
            ),
        }
        weekly_row.update(build_calendar_features(week_start))
        weekly_rows.append(weekly_row)

    for lag_column in LAG_FEATURE_COLUMNS:
        values = [float(row[lag_column]) for row in weekly_rows]
        for index, row in enumerate(weekly_rows):
            row[f"{lag_column}_lag_1w"] = values[index - 1] if index >= 1 else math.nan
            row[f"{lag_column}_lag_2w"] = values[index - 2] if index >= 2 else math.nan
            row[f"{lag_column}_lag_4w"] = values[index - 4] if index >= 4 else math.nan
            previous_values = values[max(0, index - 4) : index]
            row[f"{lag_column}_rolling_4w_mean"] = (
                sum(previous_values) / len(previous_values) if previous_values else math.nan
            )

    return weekly_rows


def _sum_for_rows(rows: list[dict[str, object]], column: str) -> float:
    return sum(float(row[column]) for row in rows)


def _mean_for_rows(rows: list[dict[str, object]], column: str) -> float:
    values = [float(row[column]) for row in rows]
    return sum(values) / len(values)


def fetch_dynamic_feature_lookup(
    *,
    coordinate_lookup: dict[str, tuple[float, float]],
    reference_window: ReferenceWindow,
    max_workers: int,
) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                build_dynamic_snapshot_for_municipality,
                municipality_code=municipality_code,
                coordinates=coordinates,
                reference_window=reference_window,
            ): municipality_code
            for municipality_code, coordinates in coordinate_lookup.items()
        }
        for future in as_completed(futures):
            municipality_code = futures[future]
            lookup[municipality_code] = future.result()
    return lookup


def build_dynamic_snapshot_for_municipality(
    *,
    municipality_code: str,
    coordinates: tuple[float, float],
    reference_window: ReferenceWindow,
) -> dict[str, object]:
    latitude, longitude = coordinates
    payload = fetch_open_meteo_hourly(
        latitude=latitude,
        longitude=longitude,
        start_date=reference_window.history_start,
        end_date=reference_window.reference_week_end,
    )
    daily_rows = build_daily_rows_from_hourly(payload)
    weekly_rows = build_weekly_rows_from_daily(
        daily_rows,
        history_start=reference_window.history_start,
    )
    if len(weekly_rows) < 6:
        raise ValueError(
            f"Expected at least 6 weekly rows for municipality {municipality_code}, got {len(weekly_rows)}."
        )

    current_week = weekly_rows[-1]
    previous_week = weekly_rows[-2]
    if current_week["week_start"] != reference_window.reference_week_start:
        raise ValueError(
            "Live weather weekly aggregation drifted from the expected reference week: "
            f"{municipality_code} -> {current_week['week_start']!s}"
        )

    return {
        "current": {column: current_week[column] for column in DYNAMIC_FEATURE_COLUMNS},
        "previous": {column: previous_week[column] for column in DYNAMIC_FEATURE_COLUMNS},
        "week_start": current_week["week_start"].isoformat(),
        "week_end": current_week["week_end"].isoformat(),
    }


def build_feature_vector(
    *,
    feature_columns: tuple[str, ...],
    categorical_columns: tuple[str, ...],
    static_feature_values: dict[str, object],
    dynamic_feature_values: dict[str, object],
) -> list[object]:
    values: list[object] = []
    for column in feature_columns:
        if column in dynamic_feature_values:
            current_value = dynamic_feature_values[column]
        else:
            current_value = static_feature_values[column]

        if column in categorical_columns:
            values.append(str(current_value) if current_value not in {"", None} else "__MISSING__")
            continue

        if current_value is None:
            values.append(math.nan)
            continue
        values.append(float(current_value))
    return values


def predict_probability(
    *,
    model: CatBoostClassifier,
    feature_columns: tuple[str, ...],
    categorical_columns: tuple[str, ...],
    feature_vector: list[object],
) -> float:
    cat_feature_indices = [
        feature_columns.index(column) for column in categorical_columns if column in feature_columns
    ]
    pool = Pool(
        data=[feature_vector],
        cat_features=cat_feature_indices,
        feature_names=list(feature_columns),
    )
    return float(model.predict_proba(pool)[0][-1])


def format_trend_label(delta_score: int) -> str:
    if delta_score > 0:
        return f"+{delta_score} tock glede na prejsnji teden"
    if delta_score < 0:
        return f"{delta_score} tock glede na prejsnji teden"
    return "brez spremembe glede na prejsnji teden"


def build_live_model_payload(
    *,
    spec: ModelSpec,
    existing_model_payload: dict[str, Any],
    coordinate_lookup: dict[str, tuple[float, float]],
    static_feature_lookup: dict[str, dict[str, object]],
    dynamic_feature_lookup: dict[str, dict[str, object]],
    reference_window: ReferenceWindow,
    generated_at: str,
) -> dict[str, Any]:
    config = load_config(spec.config_path)
    holdout_values = load_holdout_values(spec.holdout_predictions_path)
    model = CatBoostClassifier()
    model.load_model(str(spec.model_path))

    locations: list[dict[str, Any]] = []
    for municipality_code, coordinates in coordinate_lookup.items():
        static_values = static_feature_lookup.get(municipality_code)
        dynamic_values = dynamic_feature_lookup.get(municipality_code)
        if static_values is None or dynamic_values is None:
            continue

        current_vector = build_feature_vector(
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            static_feature_values=static_values,
            dynamic_feature_values=dynamic_values["current"],
        )
        previous_vector = build_feature_vector(
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            static_feature_values=static_values,
            dynamic_feature_values=dynamic_values["previous"],
        )
        current_probability = predict_probability(
            model=model,
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            feature_vector=current_vector,
        )
        previous_probability = predict_probability(
            model=model,
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            feature_vector=previous_vector,
        )

        current_score = score_percentile(holdout_values, current_probability)
        previous_score = score_percentile(holdout_values, previous_probability)
        delta_score = current_score - previous_score
        municipality_name = str(static_values["obcina_naziv"])
        locations.append(
            {
                "id": f"{spec.key}-{municipality_code}",
                "municipalityCode": municipality_code,
                "municipalityName": municipality_name,
                "score": current_score,
                "level": classify_level(
                    current_probability,
                    existing_model_payload["thresholds"]["lowUpper"],
                    existing_model_payload["thresholds"]["mediumUpper"],
                ),
                "trendDeltaScore": delta_score,
                "trendLabel": format_trend_label(delta_score),
                "weekStart": dynamic_values["week_start"],
                "weekEnd": dynamic_values["week_end"],
                "coordinates": [coordinates[0], coordinates[1]],
                "_rawPrediction": current_probability,
            }
        )

    locations.sort(
        key=lambda location: (
            -location["score"],
            -location["_rawPrediction"],
            location["municipalityName"],
        )
    )

    featured_locations = [
        {
            "municipalityName": location["municipalityName"],
            "municipalityCode": location["municipalityCode"],
            "level": location["level"],
            "score": location["score"],
            "id": location["id"],
        }
        for location in locations[:8]
    ]
    for location in locations:
        location.pop("_rawPrediction", None)

    return {
        "key": spec.key,
        "diseaseLabel": existing_model_payload["diseaseLabel"],
        "modelId": existing_model_payload["modelId"],
        "legacyResearchModelId": existing_model_payload["legacyResearchModelId"],
        "asOfDate": reference_window.as_of_date.isoformat(),
        "generatedAt": generated_at,
        "referenceWeekStart": reference_window.reference_week_start.isoformat(),
        "referenceWeekEnd": reference_window.reference_week_end.isoformat(),
        "snapshotLabel": "zadnji zakljuceni tedenski hackathon snapshot",
        "weatherSource": "Open-Meteo best-match hourly weather",
        "methodologyNote": (
            "Live hackathon demo uporablja Open-Meteo hourly weather za zadnjih 6 tednov, "
            "tedensko agregacijo po istem feature kontraktu kot env_v2 in reprezentativno "
            "tocko obcine za vreme. Pragovi score/level ostanejo zamrznjeni iz holdout distribucije."
        ),
        "purpose": existing_model_payload["purpose"],
        "disclaimer": existing_model_payload["disclaimer"],
        "scoreExplanation": existing_model_payload["scoreExplanation"],
        "topDrivers": existing_model_payload["topDrivers"],
        "thresholds": existing_model_payload["thresholds"],
        "locations": locations,
        "featuredLocations": featured_locations,
    }


def build_live_models(
    *,
    as_of_date: date,
    max_workers: int,
) -> dict[str, Any]:
    if max_workers < 1:
        raise ValueError("--max-workers must be at least 1.")

    existing_data = load_existing_environmental_risk_data(FRONTEND_ENVIRONMENTAL_RISK_PATH)
    coordinate_lookup = build_coordinate_lookup(existing_data)
    if not coordinate_lookup:
        raise ValueError("Could not load municipality coordinates from environmentalRisk.ts.")

    combined_feature_columns = {"obcina_sifra", "obcina_naziv"}
    for spec in MODEL_SPECS:
        config = load_config(spec.config_path)
        static_columns = [column for column in config.feature_columns if column not in DYNAMIC_FEATURE_COLUMNS]
        combined_feature_columns.update(static_columns)

    static_feature_lookup = load_static_feature_lookup(
        TRAINING_DATASET_PATH,
        required_columns=combined_feature_columns,
    )
    reference_window = resolve_reference_window(as_of_date)
    dynamic_feature_lookup = fetch_dynamic_feature_lookup(
        coordinate_lookup=coordinate_lookup,
        reference_window=reference_window,
        max_workers=max_workers,
    )
    generated_at = datetime.now().isoformat(timespec="seconds")

    return {
        spec.key: build_live_model_payload(
            spec=spec,
            existing_model_payload=existing_data[spec.key],
            coordinate_lookup=coordinate_lookup,
            static_feature_lookup=static_feature_lookup,
            dynamic_feature_lookup=dynamic_feature_lookup,
            reference_window=reference_window,
            generated_at=generated_at,
        )
        for spec in MODEL_SPECS
    }


def render_module(data: dict[str, Any]) -> str:
    return MODULE_HEADER + json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def write_module(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_module(data), encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    as_of_date = date.today()
    if args.as_of_date:
        as_of_date = parse_iso_date(args.as_of_date)

    live_models = build_live_models(
        as_of_date=as_of_date,
        max_workers=args.max_workers,
    )
    output_path = Path(args.output_path)
    write_module(output_path, live_models)
    print(f"Live municipality risk frontend data written to {output_path.resolve()}")
    for key, payload in live_models.items():
        print(
            f"- {key}: week {payload['referenceWeekStart']} -> {payload['referenceWeekEnd']}, "
            f"{len(payload['locations'])} municipalities"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
