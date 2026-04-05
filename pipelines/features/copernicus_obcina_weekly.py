from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_SOURCE_DIR = Path("data/interim/features/copernicus/era5land_slovenia/hourly")
DEFAULT_GEOJSON_PATH = Path("data/raw/gurs/obcine-gurs-rpe.geojson")
DEFAULT_OVERLAY_OUTPUT = Path(
    "data/interim/features/copernicus/era5land_slovenia/obcina_grid_overlay.csv"
)
DEFAULT_DAILY_OUTPUT = Path(
    "data/interim/features/copernicus/era5land_slovenia/obcina_daily_weather.csv"
)
DEFAULT_WEEKLY_OUTPUT = Path("data/processed/training/obcina_weekly_weather_features.csv")
DEFAULT_MANIFEST_OUTPUT = Path(
    "data/processed/training/obcina_weekly_weather_features_manifest.json"
)
OVERLAY_CRS = "EPSG:3794"
GRID_KEY_PRECISION = 4
WEEK_START_TO_PERIOD = {
    "MON": "W-SUN",
    "TUE": "W-MON",
    "WED": "W-TUE",
    "THU": "W-WED",
    "FRI": "W-THU",
    "SAT": "W-FRI",
    "SUN": "W-SAT",
}
HOURLY_VARIABLES = [
    "air_temperature_c",
    "relative_humidity_pct",
    "precipitation_hourly_mm",
    "soil_temperature_level_1_c",
    "soil_temperature_level_2_c",
    "soil_water_layer_1_m3_m3",
    "soil_water_layer_2_m3_m3",
]
LAG_FEATURE_COLUMNS = [
    "air_temperature_c_mean",
    "relative_humidity_pct_mean",
    "precipitation_sum_mm",
    "soil_water_layer_1_m3_m3_mean",
    "tick_activity_window_hours_sum",
]


class ProcessingDependencyError(RuntimeError):
    """Raised when optional processing dependencies are missing."""


@dataclass(frozen=True)
class OverlayBuildSummary:
    overlay_rows: int
    municipality_count: int
    grid_cell_count: int
    coverage_min_pct: float
    coverage_max_pct: float


@dataclass(frozen=True)
class WeatherFeatureTables:
    overlay: Any
    municipality_daily: Any
    municipality_weekly: Any
    manifest: dict[str, Any]


def ensure_processing_dependencies() -> None:
    missing: list[str] = []
    for module_name in ("numpy", "pandas", "pyproj", "shapely", "xarray"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)

    if missing:
        raise ProcessingDependencyError(
            "Missing dependencies: "
            + ", ".join(sorted(missing))
            + ". Install with: python3 -m pip install -r scripts/data/copernicus/requirements.txt"
        )


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def resolve_week_period(week_start_day: str) -> str:
    normalized = week_start_day.strip().upper()
    if normalized not in WEEK_START_TO_PERIOD:
        supported = ", ".join(sorted(WEEK_START_TO_PERIOD))
        raise ValueError(f"Unsupported week start day '{week_start_day}'. Use one of: {supported}.")
    return WEEK_START_TO_PERIOD[normalized]


def list_feature_files(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.glob("*.nc") if path.is_file())


def make_grid_key(latitude: float, longitude: float) -> str:
    return f"{float(latitude):.{GRID_KEY_PRECISION}f}|{float(longitude):.{GRID_KEY_PRECISION}f}"


def normalize_obcina_properties(properties: Mapping[str, object]) -> dict[str, str]:
    sifra = properties.get("SIFRA")
    naziv = properties.get("NAZIV")
    if sifra in (None, ""):
        raise ValueError("GeoJSON feature is missing SIFRA.")
    if naziv in (None, ""):
        raise ValueError("GeoJSON feature is missing NAZIV.")

    normalized = {
        "obcina_sifra": str(sifra).strip(),
        "obcina_naziv": str(naziv).strip(),
        "eid_obcina": str(properties.get("EID_OBCINA", "")).strip(),
        "ob_mid": str(properties.get("OB_MID", "")).strip(),
    }
    return normalized


def compute_axis_edges(values: Sequence[float]) -> list[float]:
    if len(values) < 2:
        raise ValueError("Need at least two coordinate values to infer grid cell edges.")

    numeric_values = [float(value) for value in values]
    edges: list[float] = [0.0] * (len(numeric_values) + 1)

    for index in range(1, len(numeric_values)):
        edges[index] = (numeric_values[index - 1] + numeric_values[index]) / 2.0

    edges[0] = numeric_values[0] + (numeric_values[0] - numeric_values[1]) / 2.0
    edges[-1] = numeric_values[-1] + (numeric_values[-1] - numeric_values[-2]) / 2.0
    return edges


def build_calendar_features(week_start_value: datetime) -> dict[str, float | int]:
    iso_year, iso_week, _ = week_start_value.isocalendar()
    midpoint = week_start_value + timedelta(days=3)
    angle = (2.0 * math.pi * iso_week) / 52.1775
    return {
        "year": week_start_value.year,
        "month": midpoint.month,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "week_of_year_sin": math.sin(angle),
        "week_of_year_cos": math.cos(angle),
    }


def _load_municipalities(geojson_path: Path) -> list[dict[str, Any]]:
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform

    with geojson_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    transformer = Transformer.from_crs("EPSG:4326", OVERLAY_CRS, always_xy=True)
    project = transformer.transform

    municipalities: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        properties = normalize_obcina_properties(feature.get("properties", {}))
        geometry_wgs84 = shape(feature["geometry"])
        geometry_projected = transform(project, geometry_wgs84)
        municipalities.append(
            {
                **properties,
                "geometry_projected": geometry_projected,
                "municipality_area_m2": float(geometry_projected.area),
            }
        )

    if not municipalities:
        raise ValueError(f"No municipality features found in {geojson_path}.")

    return municipalities


def _load_reference_grid(source_file: Path) -> tuple[list[dict[str, Any]], int]:
    import xarray as xr
    from pyproj import Transformer
    from shapely.geometry import Polygon
    from shapely.ops import transform

    with xr.open_dataset(source_file) as ds:
        latitudes = [float(value) for value in ds["latitude"].values.tolist()]
        longitudes = [float(value) for value in ds["longitude"].values.tolist()]

    latitude_edges = compute_axis_edges(latitudes)
    longitude_edges = compute_axis_edges(longitudes)

    transformer = Transformer.from_crs("EPSG:4326", OVERLAY_CRS, always_xy=True)
    project = transformer.transform

    grid_cells: list[dict[str, Any]] = []
    for lat_index, latitude in enumerate(latitudes):
        south = min(latitude_edges[lat_index], latitude_edges[lat_index + 1])
        north = max(latitude_edges[lat_index], latitude_edges[lat_index + 1])

        for lon_index, longitude in enumerate(longitudes):
            west = min(longitude_edges[lon_index], longitude_edges[lon_index + 1])
            east = max(longitude_edges[lon_index], longitude_edges[lon_index + 1])
            geometry_wgs84 = Polygon(
                [
                    (west, south),
                    (east, south),
                    (east, north),
                    (west, north),
                ]
            )
            geometry_projected = transform(project, geometry_wgs84)
            grid_cells.append(
                {
                    "grid_key": make_grid_key(latitude, longitude),
                    "latitude": latitude,
                    "longitude": longitude,
                    "geometry_projected": geometry_projected,
                    "cell_area_m2": float(geometry_projected.area),
                }
            )

    return grid_cells, len(latitudes) * len(longitudes)


def build_overlay_table(source_file: Path, geojson_path: Path) -> tuple[Any, OverlayBuildSummary]:
    import pandas as pd

    municipalities = _load_municipalities(geojson_path)
    grid_cells, expected_grid_cell_count = _load_reference_grid(source_file)

    overlay_rows: list[dict[str, Any]] = []
    coverage_values: list[float] = []

    for municipality in municipalities:
        municipality_geometry = municipality["geometry_projected"]
        weighted_cells: list[dict[str, Any]] = []

        for grid_cell in grid_cells:
            if not municipality_geometry.intersects(grid_cell["geometry_projected"]):
                continue
            intersection = municipality_geometry.intersection(grid_cell["geometry_projected"])
            if intersection.is_empty:
                continue
            intersection_area_m2 = float(intersection.area)
            if intersection_area_m2 <= 0.0:
                continue
            weighted_cells.append(
                {
                    "grid_key": grid_cell["grid_key"],
                    "latitude": grid_cell["latitude"],
                    "longitude": grid_cell["longitude"],
                    "intersection_area_m2": intersection_area_m2,
                    "cell_area_m2": grid_cell["cell_area_m2"],
                }
            )

        if not weighted_cells:
            raise ValueError(
                "Municipality has no overlapping ERA5-Land cells: "
                f"{municipality['obcina_sifra']} {municipality['obcina_naziv']}"
            )

        total_intersection_area = sum(item["intersection_area_m2"] for item in weighted_cells)
        coverage_ratio = (
            total_intersection_area / municipality["municipality_area_m2"]
            if municipality["municipality_area_m2"] > 0.0
            else 0.0
        )
        coverage_values.append(coverage_ratio)

        for item in weighted_cells:
            overlay_rows.append(
                {
                    "obcina_sifra": municipality["obcina_sifra"],
                    "obcina_naziv": municipality["obcina_naziv"],
                    "eid_obcina": municipality["eid_obcina"],
                    "ob_mid": municipality["ob_mid"],
                    "grid_key": item["grid_key"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "municipality_area_m2": municipality["municipality_area_m2"],
                    "intersection_area_m2": item["intersection_area_m2"],
                    "cell_area_m2": item["cell_area_m2"],
                    "cell_weight": item["intersection_area_m2"] / total_intersection_area,
                    "coverage_ratio": coverage_ratio,
                }
            )

    overlay = pd.DataFrame(overlay_rows).sort_values(
        by=["obcina_sifra", "latitude", "longitude"]
    )
    summary = OverlayBuildSummary(
        overlay_rows=len(overlay_rows),
        municipality_count=len(municipalities),
        grid_cell_count=expected_grid_cell_count,
        coverage_min_pct=min(coverage_values) * 100.0,
        coverage_max_pct=max(coverage_values) * 100.0,
    )
    return overlay, summary


def _validate_required_variables(ds: Any, source_file: Path) -> None:
    missing = [name for name in HOURLY_VARIABLES if name not in ds.data_vars]
    if missing:
        raise ValueError(
            f"Dataset {source_file} is missing required variables: {', '.join(missing)}"
        )


def build_municipality_daily_from_month_file(
    source_file: Path,
    overlay: Any,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Any:
    import pandas as pd
    import xarray as xr

    with xr.open_dataset(source_file) as ds:
        _validate_required_variables(ds, source_file)
        hourly = ds[HOURLY_VARIABLES].to_dataframe().reset_index()

    hourly["time"] = pd.to_datetime(hourly["time"])
    if start_date is not None:
        hourly = hourly[hourly["time"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        hourly = hourly[hourly["time"] < pd.Timestamp(end_date + timedelta(days=1))]

    if hourly.empty:
        return pd.DataFrame()

    hourly["grid_key"] = hourly.apply(
        lambda row: make_grid_key(row["latitude"], row["longitude"]),
        axis=1,
    )
    hourly["date"] = hourly["time"].dt.floor("D")
    hourly["humidity_hours_ge_80"] = (hourly["relative_humidity_pct"] >= 80.0).astype(int)
    hourly["humidity_hours_ge_90"] = (hourly["relative_humidity_pct"] >= 90.0).astype(int)
    hourly["wet_hours_ge_0_1mm"] = (hourly["precipitation_hourly_mm"] >= 0.1).astype(int)
    hourly["tick_activity_window_hours"] = (
        hourly["air_temperature_c"].between(7.0, 25.0, inclusive="both")
        & (hourly["relative_humidity_pct"] >= 80.0)
    ).astype(int)
    hourly["growing_degree_hours_base_5_c"] = (hourly["air_temperature_c"] - 5.0).clip(lower=0.0)

    cell_daily = (
        hourly.groupby(["date", "grid_key"], as_index=False)
        .agg(
            air_temperature_c_mean=("air_temperature_c", "mean"),
            relative_humidity_pct_mean=("relative_humidity_pct", "mean"),
            precipitation_sum_mm=("precipitation_hourly_mm", "sum"),
            soil_temperature_level_1_c_mean=("soil_temperature_level_1_c", "mean"),
            soil_temperature_level_2_c_mean=("soil_temperature_level_2_c", "mean"),
            soil_water_layer_1_m3_m3_mean=("soil_water_layer_1_m3_m3", "mean"),
            soil_water_layer_2_m3_m3_mean=("soil_water_layer_2_m3_m3", "mean"),
            humidity_hours_ge_80_mean=("humidity_hours_ge_80", "sum"),
            humidity_hours_ge_90_mean=("humidity_hours_ge_90", "sum"),
            wet_hours_ge_0_1mm_mean=("wet_hours_ge_0_1mm", "sum"),
            tick_activity_window_hours_mean=("tick_activity_window_hours", "sum"),
            growing_degree_hours_base_5_c_sum=("growing_degree_hours_base_5_c", "sum"),
            observation_hours=("air_temperature_c", "count"),
        )
    )

    weighted = cell_daily.merge(
        overlay[
            [
                "obcina_sifra",
                "obcina_naziv",
                "grid_key",
                "cell_weight",
                "municipality_area_m2",
                "coverage_ratio",
            ]
        ],
        on="grid_key",
        how="inner",
        validate="many_to_many",
    )

    weighted_columns = [
        "air_temperature_c_mean",
        "relative_humidity_pct_mean",
        "precipitation_sum_mm",
        "soil_temperature_level_1_c_mean",
        "soil_temperature_level_2_c_mean",
        "soil_water_layer_1_m3_m3_mean",
        "soil_water_layer_2_m3_m3_mean",
        "humidity_hours_ge_80_mean",
        "humidity_hours_ge_90_mean",
        "wet_hours_ge_0_1mm_mean",
        "tick_activity_window_hours_mean",
        "growing_degree_hours_base_5_c_sum",
        "observation_hours",
    ]
    for column in weighted_columns:
        weighted[column] = weighted[column] * weighted["cell_weight"]

    municipality_daily = (
        weighted.groupby(
            ["date", "obcina_sifra", "obcina_naziv", "municipality_area_m2", "coverage_ratio"],
            as_index=False,
        )
        .agg(
            air_temperature_c_mean=("air_temperature_c_mean", "sum"),
            relative_humidity_pct_mean=("relative_humidity_pct_mean", "sum"),
            precipitation_sum_mm=("precipitation_sum_mm", "sum"),
            soil_temperature_level_1_c_mean=("soil_temperature_level_1_c_mean", "sum"),
            soil_temperature_level_2_c_mean=("soil_temperature_level_2_c_mean", "sum"),
            soil_water_layer_1_m3_m3_mean=("soil_water_layer_1_m3_m3_mean", "sum"),
            soil_water_layer_2_m3_m3_mean=("soil_water_layer_2_m3_m3_mean", "sum"),
            humidity_hours_ge_80_mean=("humidity_hours_ge_80_mean", "sum"),
            humidity_hours_ge_90_mean=("humidity_hours_ge_90_mean", "sum"),
            wet_hours_ge_0_1mm_mean=("wet_hours_ge_0_1mm_mean", "sum"),
            tick_activity_window_hours_mean=("tick_activity_window_hours_mean", "sum"),
            growing_degree_hours_base_5_c_sum=("growing_degree_hours_base_5_c_sum", "sum"),
            observation_hours_mean=("observation_hours", "sum"),
        )
    )
    return municipality_daily


def build_overlay_summary(overlay: Any) -> Any:
    import numpy as np

    summary = (
        overlay.groupby(["obcina_sifra", "obcina_naziv"], as_index=False)
        .agg(
            grid_cell_count=("grid_key", "nunique"),
            municipality_area_m2=("municipality_area_m2", "first"),
            coverage_ratio=("coverage_ratio", "first"),
        )
        .sort_values(by=["obcina_sifra"])
    )
    summary["covered_area_pct"] = summary["coverage_ratio"] * 100.0
    summary["overlay_method"] = np.where(
        summary["coverage_ratio"] >= 0.999,
        "area_weighted_polygon_overlay",
        "area_weighted_polygon_overlay_partial_coverage",
    )
    return summary


def build_municipality_weekly_features(
    municipality_daily: Any,
    overlay_summary: Any,
    *,
    week_period: str,
    keep_partial_weeks: bool,
) -> Any:
    import pandas as pd

    daily = municipality_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["week_start"] = daily["date"].dt.to_period(week_period).dt.start_time
    daily["week_end"] = daily["week_start"] + pd.Timedelta(days=6)
    daily["rainy_days_ge_1mm_flag"] = (daily["precipitation_sum_mm"] >= 1.0).astype(int)
    daily["humid_days_ge_16h_flag"] = (daily["humidity_hours_ge_80_mean"] >= 16.0).astype(int)
    daily["tick_favorable_days_ge_6h_flag"] = (
        daily["tick_activity_window_hours_mean"] >= 6.0
    ).astype(int)

    weekly = (
        daily.groupby(["week_start", "week_end", "obcina_sifra", "obcina_naziv"], as_index=False)
        .agg(
            observation_days_count=("date", "nunique"),
            air_temperature_c_mean=("air_temperature_c_mean", "mean"),
            air_temperature_c_min=("air_temperature_c_mean", "min"),
            air_temperature_c_max=("air_temperature_c_mean", "max"),
            air_temperature_c_std=("air_temperature_c_mean", "std"),
            relative_humidity_pct_mean=("relative_humidity_pct_mean", "mean"),
            relative_humidity_pct_min=("relative_humidity_pct_mean", "min"),
            relative_humidity_pct_max=("relative_humidity_pct_mean", "max"),
            precipitation_sum_mm=("precipitation_sum_mm", "sum"),
            precipitation_daily_max_mm=("precipitation_sum_mm", "max"),
            soil_temperature_level_1_c_mean=("soil_temperature_level_1_c_mean", "mean"),
            soil_temperature_level_2_c_mean=("soil_temperature_level_2_c_mean", "mean"),
            soil_water_layer_1_m3_m3_mean=("soil_water_layer_1_m3_m3_mean", "mean"),
            soil_water_layer_2_m3_m3_mean=("soil_water_layer_2_m3_m3_mean", "mean"),
            humidity_hours_ge_80_sum=("humidity_hours_ge_80_mean", "sum"),
            humidity_hours_ge_90_sum=("humidity_hours_ge_90_mean", "sum"),
            wet_hours_ge_0_1mm_sum=("wet_hours_ge_0_1mm_mean", "sum"),
            tick_activity_window_hours_sum=("tick_activity_window_hours_mean", "sum"),
            growing_degree_hours_base_5_c_sum=("growing_degree_hours_base_5_c_sum", "sum"),
            rainy_days_ge_1mm_count=("rainy_days_ge_1mm_flag", "sum"),
            humid_days_ge_16h_count=("humid_days_ge_16h_flag", "sum"),
            tick_favorable_days_ge_6h_count=("tick_favorable_days_ge_6h_flag", "sum"),
        )
    )

    weekly["air_temperature_c_std"] = weekly["air_temperature_c_std"].fillna(0.0)
    weekly["air_temperature_c_range"] = (
        weekly["air_temperature_c_max"] - weekly["air_temperature_c_min"]
    )

    if not keep_partial_weeks:
        weekly = weekly[weekly["observation_days_count"] == 7].copy()

    weekly = weekly.merge(
        overlay_summary[
            [
                "obcina_sifra",
                "obcina_naziv",
                "grid_cell_count",
                "municipality_area_m2",
                "covered_area_pct",
                "overlay_method",
            ]
        ],
        on=["obcina_sifra", "obcina_naziv"],
        how="left",
        validate="many_to_one",
    )
    weekly = weekly.sort_values(by=["obcina_sifra", "week_start"]).reset_index(drop=True)

    for column in LAG_FEATURE_COLUMNS:
        grouped = weekly.groupby("obcina_sifra", sort=False)[column]
        weekly[f"{column}_lag_1w"] = grouped.shift(1)
        weekly[f"{column}_lag_2w"] = grouped.shift(2)
        weekly[f"{column}_lag_4w"] = grouped.shift(4)
        weekly[f"{column}_rolling_4w_mean"] = grouped.transform(
            lambda series: series.shift(1).rolling(window=4, min_periods=1).mean()
        )

    calendar_records = [build_calendar_features(value.to_pydatetime()) for value in weekly["week_start"]]
    calendar_df = pd.DataFrame(calendar_records)
    weekly = pd.concat([weekly.reset_index(drop=True), calendar_df], axis=1)
    return weekly


def build_obcina_weather_feature_tables(
    *,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    geojson_path: Path = DEFAULT_GEOJSON_PATH,
    start_date: date | None = None,
    end_date: date | None = None,
    limit_files: int | None = None,
    week_start_day: str = "MON",
    keep_partial_weeks: bool = False,
) -> WeatherFeatureTables:
    import pandas as pd

    ensure_processing_dependencies()

    source_files = list_feature_files(source_dir)
    if limit_files is not None:
        source_files = source_files[:limit_files]
    if not source_files:
        raise FileNotFoundError(f"No feature NetCDF files found in {source_dir}.")

    overlay, overlay_build_summary = build_overlay_table(source_files[0], geojson_path)
    daily_frames = []
    for source_file in source_files:
        municipality_daily = build_municipality_daily_from_month_file(
            source_file,
            overlay,
            start_date=start_date,
            end_date=end_date,
        )
        if not municipality_daily.empty:
            daily_frames.append(municipality_daily)

    if not daily_frames:
        raise ValueError("No municipality daily rows were produced for the requested interval.")

    municipality_daily = (
        pd.concat(daily_frames, ignore_index=True)
        .sort_values(by=["obcina_sifra", "date"])
        .reset_index(drop=True)
    )
    overlay_summary = build_overlay_summary(overlay)
    municipality_daily = municipality_daily.merge(
        overlay_summary[
            [
                "obcina_sifra",
                "obcina_naziv",
                "grid_cell_count",
                "covered_area_pct",
                "overlay_method",
            ]
        ],
        on=["obcina_sifra", "obcina_naziv"],
        how="left",
        validate="many_to_one",
    )

    week_period = resolve_week_period(week_start_day)
    municipality_weekly = build_municipality_weekly_features(
        municipality_daily,
        overlay_summary,
        week_period=week_period,
        keep_partial_weeks=keep_partial_weeks,
    )

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(source_dir.resolve()),
        "geojson_path": str(geojson_path.resolve()),
        "source_file_count": len(source_files),
        "source_files": [str(path.resolve()) for path in source_files],
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "week_start_day": week_start_day.upper(),
        "keep_partial_weeks": keep_partial_weeks,
        "overlay_summary": {
            "overlay_rows": overlay_build_summary.overlay_rows,
            "municipality_count": overlay_build_summary.municipality_count,
            "grid_cell_count": overlay_build_summary.grid_cell_count,
            "coverage_min_pct": round(overlay_build_summary.coverage_min_pct, 6),
            "coverage_max_pct": round(overlay_build_summary.coverage_max_pct, 6),
        },
        "daily_row_count": int(len(municipality_daily)),
        "weekly_row_count": int(len(municipality_weekly)),
        "weekly_feature_columns": [column for column in municipality_weekly.columns if column not in {
            "week_start",
            "week_end",
            "obcina_sifra",
            "obcina_naziv",
        }],
    }

    return WeatherFeatureTables(
        overlay=overlay,
        municipality_daily=municipality_daily,
        municipality_weekly=municipality_weekly,
        manifest=manifest,
    )


def write_weather_feature_tables(
    tables: WeatherFeatureTables,
    *,
    overlay_output: Path = DEFAULT_OVERLAY_OUTPUT,
    daily_output: Path = DEFAULT_DAILY_OUTPUT,
    weekly_output: Path = DEFAULT_WEEKLY_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    overlay_output.parent.mkdir(parents=True, exist_ok=True)
    daily_output.parent.mkdir(parents=True, exist_ok=True)
    weekly_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.overlay.to_csv(overlay_output, index=False)
    tables.municipality_daily.to_csv(daily_output, index=False)
    tables.municipality_weekly.to_csv(weekly_output, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")
