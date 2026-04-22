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
from typing import TYPE_CHECKING, Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.training.config import load_config

if TYPE_CHECKING:
    from catboost import CatBoostClassifier, CatBoostRegressor


FRONTEND_LIVE_RISK_PATH = (
    REPO_ROOT / "frontend" / "src" / "data" / "liveMunicipalityRisk.ts"
)
LIVE_REFERENCE_ASSET_DIR = REPO_ROOT / "data" / "reference" / "live_snapshot"
MUNICIPALITY_STATIC_FEATURES_PATH = (
    LIVE_REFERENCE_ASSET_DIR / "municipality_static_features.json"
)
MUNICIPALITY_COORDINATES_PATH = (
    LIVE_REFERENCE_ASSET_DIR / "municipality_coordinates.json"
)
LEGACY_TRAINING_DATASET_PATH = (
    REPO_ROOT / "data" / "processed" / "training" / "obcina_weekly_tick_borne_catboost_ready.csv"
)
LEGACY_GURS_MUNICIPALITY_GEOJSON_PATH = (
    REPO_ROOT / "data" / "raw" / "gurs" / "obcine-gurs-rpe.geojson"
)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT_SECONDS = 45
MAX_FETCH_WORKERS = 8
OPEN_METEO_MAX_ATTEMPTS = 5
OPEN_METEO_BASE_BACKOFF_SECONDS = 2.0

FEATURE_LABELS = {
    "week_of_year_cos": "sezonski signal",
    "week_of_year_sin": "sezonski signal",
    "urban_cover_pct": "urbaniziranost",
    "air_temperature_c_mean_rolling_4w_mean": "temperaturni trend",
    "elevation_m_std": "razgiban relief",
    "elevation_m_range": "visinska raznolikost",
    "elevation_m_mean": "nadmorska visina",
    "forest_cover_pct": "gozdna pokrovnost",
    "mixed_forest_cover_pct": "mesani gozd",
    "broad_leaved_forest_cover_pct": "listnati gozd",
    "coniferous_forest_cover_pct": "iglasti gozd",
    "dominant_clc_cover_pct": "tip rabe tal",
    "agricultural_cover_pct": "kmetijska krajina",
    "shrub_transitional_cover_pct": "grmisca in prehodni habitat",
    "soil_temperature_level_1_c_mean": "temperatura tal",
    "soil_temperature_level_2_c_mean": "temperatura globljih tal",
    "wet_hours_ge_0_1mm_sum": "mokri dnevi",
}

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
    disease_label: str
    model_id: str
    legacy_research_model_id: str
    config_path: Path
    model_path: Path
    holdout_values_path: Path
    metadata_path: Path


MODEL_SPECS = (
    ModelSpec(
        key="borelioza",
        disease_label="Borelioza",
        model_id="catboost_tick_borne_lyme_env_v2",
        legacy_research_model_id="catboost_tick_borne_lyme_env_per100k_v1",
        config_path=REPO_ROOT
        / "ml"
        / "training"
        / "example_tick_borne_lyme_env_v2_config.json",
        model_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_lyme_env_v2"
        / "model.cbm",
        holdout_values_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_lyme_env_v2"
        / "holdout_values.json",
        metadata_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_lyme_env_v2"
        / "metadata.json",
    ),
    ModelSpec(
        key="kme",
        disease_label="KME",
        model_id="catboost_tick_borne_kme_env_v2",
        legacy_research_model_id="catboost_tick_borne_kme_env_per100k_v1",
        config_path=REPO_ROOT
        / "ml"
        / "training"
        / "example_tick_borne_kme_env_v2_config.json",
        model_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_kme_env_v2"
        / "model.cbm",
        holdout_values_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_kme_env_v2"
        / "holdout_values.json",
        metadata_path=LIVE_REFERENCE_ASSET_DIR
        / "catboost_tick_borne_kme_env_v2"
        / "metadata.json",
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
        default=MAX_FETCH_WORKERS,
        help="Maximum concurrent Open-Meteo requests.",
    )
    parser.add_argument(
        "--output-path",
        default=str(FRONTEND_LIVE_RISK_PATH),
        help="Output TypeScript module path.",
    )
    return parser


def build_coordinate_lookup_from_gurs(path: Path) -> dict[str, tuple[float, float]]:
    try:
        from shapely.geometry import shape
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "shapely is required only for the legacy GURS fallback. "
            "Use the committed data/reference/live_snapshot asset pack or install shapely."
        ) from exc

    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    if not features:
        raise ValueError(f"No municipality features found in {path}.")

    lookup: dict[str, tuple[float, float]] = {}
    for feature in features:
        properties = feature.get("properties", {})
        municipality_code = str(properties.get("SIFRA", "")).strip()
        if not municipality_code:
            raise ValueError("GURS municipality feature is missing SIFRA.")

        representative_point = shape(feature["geometry"]).representative_point()
        lookup[municipality_code] = (
            float(representative_point.y),
            float(representative_point.x),
        )
    return lookup


def load_coordinate_lookup_from_reference(path: Path) -> dict[str, tuple[float, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"Municipality coordinates payload is empty: {path}.")

    lookup: dict[str, tuple[float, float]] = {}
    for municipality_code, coordinates in payload.items():
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            raise ValueError(
                f"Municipality coordinates must be a two-item list for {municipality_code}."
            )
        lookup[str(municipality_code)] = (float(coordinates[0]), float(coordinates[1]))
    return lookup


def load_coordinate_lookup() -> dict[str, tuple[float, float]]:
    if MUNICIPALITY_COORDINATES_PATH.exists():
        return load_coordinate_lookup_from_reference(MUNICIPALITY_COORDINATES_PATH)
    return build_coordinate_lookup_from_gurs(LEGACY_GURS_MUNICIPALITY_GEOJSON_PATH)


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


def format_feature_label(feature_name: str) -> str:
    return FEATURE_LABELS.get(feature_name, feature_name.replace("_", " "))


def load_static_feature_lookup_from_training_dataset(
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


def load_static_feature_lookup_from_reference(
    path: Path,
    *,
    required_columns: set[str],
) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"Static feature payload is empty: {path}.")

    lookup: dict[str, dict[str, object]] = {}
    for municipality_code, raw_values in payload.items():
        if not isinstance(raw_values, dict):
            raise ValueError(f"Static feature row must be an object for {municipality_code}.")
        missing = sorted((required_columns - {"obcina_sifra"}) - set(raw_values))
        if missing:
            raise ValueError(
                f"Static feature row for {municipality_code} is missing columns: {', '.join(missing)}"
            )

        feature_values: dict[str, object] = {
            "obcina_naziv": str(raw_values["obcina_naziv"]).strip(),
        }
        for column in required_columns:
            if column in {"obcina_sifra", "obcina_naziv"}:
                continue
            current_value = raw_values.get(column)
            if column == "dominant_clc_code":
                feature_values[column] = (
                    str(current_value).strip() if current_value not in {"", None} else "__MISSING__"
                )
                continue
            feature_values[column] = math.nan if current_value is None else float(current_value)

        lookup[str(municipality_code)] = feature_values

    return lookup


def load_static_feature_lookup(
    *,
    required_columns: set[str],
) -> dict[str, dict[str, object]]:
    if MUNICIPALITY_STATIC_FEATURES_PATH.exists():
        return load_static_feature_lookup_from_reference(
            MUNICIPALITY_STATIC_FEATURES_PATH,
            required_columns=required_columns,
        )
    return load_static_feature_lookup_from_training_dataset(
        LEGACY_TRAINING_DATASET_PATH,
        required_columns=required_columns,
    )


def load_holdout_values(path: Path, *, prediction_column: str) -> list[float]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"Holdout values payload is empty: {path}.")
        return sorted(float(value) for value in payload)

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        values = sorted(
            float(row[prediction_column])
            for row in rows
            if row["split"] in {"validation", "test"}
        )
    if not values:
        raise ValueError(f"No holdout prediction values found in {path}.")
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
        except (urllib.error.URLError, TimeoutError) as exc:
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


def predict_value(
    *,
    model: CatBoostClassifier | CatBoostRegressor,
    feature_columns: tuple[str, ...],
    categorical_columns: tuple[str, ...],
    feature_vector: list[object],
    problem_type: str,
) -> float:
    try:
        from catboost import Pool
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "catboost is required to generate live municipality scores. "
            "Install ml/training/requirements.txt before running this script."
        ) from exc

    cat_feature_indices = [
        feature_columns.index(column) for column in categorical_columns if column in feature_columns
    ]
    pool = Pool(
        data=[feature_vector],
        cat_features=cat_feature_indices,
        feature_names=list(feature_columns),
    )
    if problem_type == "binary_classification":
        return float(model.predict_proba(pool)[0][-1])

    prediction = model.predict(pool)
    if hasattr(prediction, "tolist"):
        prediction = prediction.tolist()
    if isinstance(prediction, list):
        first_value = prediction[0]
        if isinstance(first_value, list):
            return float(first_value[0])
        return float(first_value)
    return float(prediction)


def format_trend_label(delta_score: int) -> str:
    if delta_score > 0:
        return f"+{delta_score} točk glede na prejšnji teden"
    if delta_score < 0:
        return f"{delta_score} točk glede na prejšnji teden"
    return "brez spremembe glede na prejšnji teden"


def build_live_model_payload(
    *,
    spec: ModelSpec,
    coordinate_lookup: dict[str, tuple[float, float]],
    static_feature_lookup: dict[str, dict[str, object]],
    dynamic_feature_lookup: dict[str, dict[str, object]],
    reference_window: ReferenceWindow,
    generated_at: str,
) -> dict[str, Any]:
    config = load_config(spec.config_path)
    prediction_column = "prediction_probability"
    try:
        from catboost import CatBoostClassifier, CatBoostRegressor
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "catboost is required to generate live municipality scores. "
            "Install ml/training/requirements.txt before running this script."
        ) from exc

    model: CatBoostClassifier | CatBoostRegressor
    if config.problem_type == "regression":
        prediction_column = "prediction"
        model = CatBoostRegressor()
    else:
        model = CatBoostClassifier()

    holdout_values = load_holdout_values(
        spec.holdout_values_path,
        prediction_column=prediction_column,
    )
    model.load_model(str(spec.model_path))
    metadata = json.loads(spec.metadata_path.read_text(encoding="utf-8"))
    low_upper = percentile_threshold(holdout_values, 1 / 3)
    medium_upper = percentile_threshold(holdout_values, 2 / 3)
    top_drivers = [
        format_feature_label(item["feature"])
        for item in metadata.get("feature_importances", [])[:5]
        if item.get("feature")
    ]

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
        current_prediction = predict_value(
            model=model,
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            feature_vector=current_vector,
            problem_type=config.problem_type,
        )
        previous_prediction = predict_value(
            model=model,
            feature_columns=config.feature_columns,
            categorical_columns=config.categorical_columns,
            feature_vector=previous_vector,
            problem_type=config.problem_type,
        )

        current_score = score_percentile(holdout_values, current_prediction)
        previous_score = score_percentile(holdout_values, previous_prediction)
        delta_score = current_score - previous_score
        municipality_name = str(static_values["obcina_naziv"])
        locations.append(
            {
                "id": f"{spec.key}-{municipality_code}",
                "municipalityCode": municipality_code,
                "municipalityName": municipality_name,
                "score": current_score,
                "level": classify_level(
                    current_prediction,
                    low_upper,
                    medium_upper,
                ),
                "trendDeltaScore": delta_score,
                "trendLabel": format_trend_label(delta_score),
                "weekStart": dynamic_values["week_start"],
                "weekEnd": dynamic_values["week_end"],
                "coordinates": [coordinates[0], coordinates[1]],
                "_rawPrediction": current_prediction,
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

    disease_object_label = "boreliozo" if spec.key == "borelioza" else "KME"
    methodology_note = (
        "Live hackathon demo uporablja Open-Meteo hourly weather za zadnjih 6 tednov, "
        "tedensko agregacijo po istem feature kontraktu kot env_v2 in reprezentativno točko "
        "znotraj GURS poligona posamezne občine. Score temelji na surovi napovedi env_v2 "
        "klasifikacijskega modela in je namenjen primerjavi občin znotraj iste bolezni."
    )
    if spec.key == "kme":
        methodology_note += (
            " KME model je pri učenju dodatno utežen po velikosti populacije občine, "
            "da zemljevid ni sistematično pristranski do zelo majhnih občin."
        )

    return {
        "key": spec.key,
        "diseaseLabel": spec.disease_label,
        "modelId": spec.model_id,
        "legacyResearchModelId": spec.legacy_research_model_id,
        "asOfDate": reference_window.as_of_date.isoformat(),
        "generatedAt": generated_at,
        "referenceWeekStart": reference_window.reference_week_start.isoformat(),
        "referenceWeekEnd": reference_window.reference_week_end.isoformat(),
        "snapshotLabel": "zadnji zaključeni tedenski hackathon snapshot",
        "weatherSource": "Open-Meteo best-match hourly weather",
        "methodologyNote": methodology_note,
        "purpose": (
            "Live hackathon relativni občinski okoljski indeks za "
            f"{disease_object_label}."
        ),
        "disclaimer": (
            "To ni diagnoza ali individualna verjetnost bolezni. Gre za relativni občinski "
            "risk indeks, ki je uporaben predvsem za primerjavo lokacij znotraj iste bolezni."
        ),
        "scoreExplanation": (
            "Score je relativni občinski indeks 0-100, izračunan kot empirični percentil "
            "surove napovedi modela znotraj holdout distribucije istega env_v2 modela."
        ),
        "topDrivers": top_drivers,
        "thresholds": {
            "lowUpper": low_upper,
            "mediumUpper": medium_upper,
        },
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

    coordinate_lookup = load_coordinate_lookup()
    if not coordinate_lookup:
        raise ValueError("Could not load municipality coordinates from reference assets.")

    combined_feature_columns = {"obcina_sifra", "obcina_naziv"}
    for spec in MODEL_SPECS:
        config = load_config(spec.config_path)
        static_columns = [column for column in config.feature_columns if column not in DYNAMIC_FEATURE_COLUMNS]
        combined_feature_columns.update(static_columns)

    static_feature_lookup = load_static_feature_lookup(
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
