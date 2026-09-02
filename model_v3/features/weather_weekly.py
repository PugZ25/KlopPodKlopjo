from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import netCDF4
import numpy as np
import pyproj
import shapely
import xarray as xr
from pyproj import Transformer
from scipy import sparse
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

from model_v3.features.static_geography import canonical_code
from model_v3.models.non_ml_baselines import file_record


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "era5_land_weekly_weather.json"
)
FILE_PATTERN = re.compile(r"^era5land_slovenia_(\d{4})_(\d{2})\.nc$")
SOURCE_VARIABLES = ("t2m", "d2m", "tp", "stl1", "stl2", "swvl1", "swvl2")
OUTPUT_VARIABLES = (
    "t2m_mean_c",
    "d2m_mean_c",
    "tp_sum_mm",
    "stl1_mean_c",
    "stl2_mean_c",
    "swvl1_mean_m3_m3",
    "swvl2_mean_m3_m3",
)
EXPECTED_UNITS = {
    "t2m": "K",
    "d2m": "K",
    "tp": "m",
    "stl1": "K",
    "stl2": "K",
    "swvl1": "m**3 m**-3",
    "swvl2": "m**3 m**-3",
}
MEAN_OUTPUTS = set(OUTPUT_VARIABLES) - {"tp_sum_mm"}
WEEKLY_COLUMNS = (
    "municipality_code",
    "week_start",
    "week_end",
    "weather_status",
    "source_hour_count",
    "minimum_present_hours",
    *OUTPUT_VARIABLES,
)
WEIGHT_COLUMNS = (
    "municipality_code",
    "grid_cell_index",
    "latitude",
    "longitude",
    "intersection_area_m2",
    "normalized_intersection_weight",
)


class WeatherWeeklyError(ValueError):
    """Raised when ERA5-Land source or weekly output violates its contract."""


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise WeatherWeeklyError(f"Configured path must be non-empty: {raw_path!r}")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise WeatherWeeklyError(f"Configured path must be repository-relative: {raw_path}")
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise WeatherWeeklyError(f"Configured path leaves repository: {raw_path}")
    return resolved


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise WeatherWeeklyError("Weather configuration must be inside repository.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise WeatherWeeklyError("Weather configuration schema_version must equal 1.")
    required_sections = {
        "schema_version",
        "sources",
        "source_contract",
        "municipality_policy",
        "spatial_aggregation",
        "weekly_aggregation",
        "variables",
        "outputs",
    }
    if set(config) != required_sections:
        raise WeatherWeeklyError("Weather configuration sections are unexpected.")
    contract = config["source_contract"]
    if contract != {
        "dataset": "reanalysis-era5-land",
        "product": "final_ERA5_Land",
        "required_expver": "0001",
        "raw_temporal_resolution": "hourly_UTC_valid_time",
        "grid": "regular_0.1_degree_latitude_longitude",
        "development_start_year": 2016,
        "development_end_year": 2024,
        "lockbox_year": 2025,
        "weather_cutoff": "2024-12-31T23:00:00Z",
        "availability_rule": (
            "weather_valid_time_is_the_cutoff_no_additional_publication_embargo"
        ),
        "post_cutoff_rule": (
            "do_not_extrapolate_impute_or_create_weather_after_cutoff"
        ),
    }:
        raise WeatherWeeklyError("ERA5-Land source contract is unsupported.")
    if config["municipality_policy"].get("fixed_analytical_zones_all_years") is not True:
        raise WeatherWeeklyError("Fixed municipality zones must apply to all years.")
    variable_pairs = [
        (row.get("source"), row.get("output"), row.get("source_unit"))
        for row in config["variables"]
    ]
    if variable_pairs != [
        (source, output, EXPECTED_UNITS[source])
        for source, output in zip(SOURCE_VARIABLES, OUTPUT_VARIABLES, strict=True)
    ]:
        raise WeatherWeeklyError("Weather variable definitions are unsupported.")
    if config["weekly_aggregation"].get("expected_hours") != 168:
        raise WeatherWeeklyError("A complete weather week must contain 168 hours.")
    return config


def discover_development_files(
    directory: Path, *, start_year: int, end_year: int, lockbox_year: int
) -> tuple[list[Path], int]:
    if not directory.is_dir():
        raise WeatherWeeklyError(f"Hourly ERA5-Land directory is missing: {directory}")
    selected: list[tuple[int, int, Path]] = []
    skipped_lockbox_or_later = 0
    for path in sorted(directory.iterdir()):
        match = FILE_PATTERN.match(path.name)
        if not match:
            continue
        year, month = map(int, match.groups())
        if year >= lockbox_year:
            skipped_lockbox_or_later += 1
            continue
        if start_year <= year <= end_year:
            selected.append((year, month, path))
    expected: list[tuple[int, int]] = []
    year, month = 2016, 3
    while (year, month) <= (end_year, 12):
        expected.append((year, month))
        month += 1
        if month == 13:
            year += 1
            month = 1
    observed = [(year, month) for year, month, _ in selected]
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise WeatherWeeklyError(
            f"Development ERA5-Land monthly files differ: missing={missing}, extra={extra}"
        )
    return [path for _, _, path in selected], skipped_lockbox_or_later


def read_canonical_codes(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("municipality_code", "municipality_name"):
            raise WeatherWeeklyError("Canonical municipality schema is unexpected.")
        codes = [canonical_code(row["municipality_code"]) for row in reader]
    if len(codes) != 212 or len(codes) != len(set(codes)):
        raise WeatherWeeklyError("Expected 212 unique canonical municipalities.")
    return sorted(codes)


def coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise WeatherWeeklyError("Grid coordinate must be finite one-dimensional data.")
    differences = np.diff(values)
    if not (np.all(differences > 0) or np.all(differences < 0)):
        raise WeatherWeeklyError("Grid coordinate must be strictly monotonic.")
    edges = np.empty(len(values) + 1, dtype=np.float64)
    edges[1:-1] = (values[:-1] + values[1:]) / 2.0
    edges[0] = values[0] - differences[0] / 2.0
    edges[-1] = values[-1] + differences[-1] / 2.0
    return edges


def build_spatial_weights(
    geometry_path: Path,
    *,
    codes: Sequence[str],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    code_property: str,
    area_crs: str,
) -> tuple[sparse.csr_matrix, list[dict[str, object]], dict[str, float]]:
    payload = json.loads(geometry_path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise WeatherWeeklyError("Municipality geometry must be a FeatureCollection.")
    features = payload.get("features")
    if not isinstance(features, list):
        raise WeatherWeeklyError("Municipality geometry has no features.")
    by_code: dict[str, Any] = {}
    for feature in features:
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise WeatherWeeklyError("Municipality feature lacks properties.")
        code = canonical_code(properties.get(code_property))
        geometry = shape(feature.get("geometry"))
        if geometry.is_empty or not geometry.is_valid:
            raise WeatherWeeklyError(f"Municipality geometry is invalid: {code}")
        if code in by_code:
            raise WeatherWeeklyError(f"Duplicate municipality geometry: {code}")
        by_code[code] = geometry
    if set(by_code) != set(codes):
        raise WeatherWeeklyError("Geometry and canonical municipality codes differ.")

    transformer = Transformer.from_crs("EPSG:4326", area_crs, always_xy=True)
    latitude_edges = coordinate_edges(latitudes)
    longitude_edges = coordinate_edges(longitudes)
    cell_geometries: list[Any] = []
    cell_metadata: list[tuple[float, float]] = []
    for latitude_index, latitude in enumerate(latitudes):
        lat_a, lat_b = latitude_edges[latitude_index : latitude_index + 2]
        for longitude_index, longitude in enumerate(longitudes):
            lon_a, lon_b = longitude_edges[longitude_index : longitude_index + 2]
            source_cell = box(min(lon_a, lon_b), min(lat_a, lat_b), max(lon_a, lon_b), max(lat_a, lat_b))
            cell_geometries.append(transform(transformer.transform, source_cell))
            cell_metadata.append((float(latitude), float(longitude)))
    grid_union = unary_union(cell_geometries)
    weights = np.zeros((len(codes), len(cell_geometries)), dtype=np.float64)
    weight_rows: list[dict[str, object]] = []
    coverage_ratios: dict[str, float] = {}
    for municipality_index, code in enumerate(codes):
        municipality = transform(transformer.transform, by_code[code])
        if municipality.is_empty or not municipality.is_valid or municipality.area <= 0:
            raise WeatherWeeklyError(f"Projected municipality is invalid: {code}")
        uncovered_area = municipality.difference(grid_union).area
        numerical_tolerance = max(1.0, municipality.area) * 1e-12
        if uncovered_area > numerical_tolerance:
            raise WeatherWeeklyError(
                f"ERA5-Land grid does not cover municipality {code}: {uncovered_area} m2"
            )
        intersections: list[tuple[int, float]] = []
        for grid_index, cell in enumerate(cell_geometries):
            if not municipality.intersects(cell):
                continue
            area = municipality.intersection(cell).area
            if area > 0:
                intersections.append((grid_index, float(area)))
        total = sum(area for _, area in intersections)
        if not math.isfinite(total) or total <= 0:
            raise WeatherWeeklyError(f"No grid intersection area for municipality {code}.")
        coverage_ratios[code] = total / float(municipality.area)
        for grid_index, area in intersections:
            normalized = area / total
            weights[municipality_index, grid_index] = normalized
            latitude, longitude = cell_metadata[grid_index]
            weight_rows.append(
                {
                    "municipality_code": code,
                    "grid_cell_index": grid_index,
                    "latitude": latitude,
                    "longitude": longitude,
                    "intersection_area_m2": area,
                    "normalized_intersection_weight": normalized,
                }
            )
    if not np.allclose(weights.sum(axis=1), 1.0, rtol=0.0, atol=1e-12):
        raise WeatherWeeklyError("Municipality spatial weights do not sum to one.")
    return sparse.csr_matrix(weights), weight_rows, coverage_ratios


def datetime64_to_utc(value: np.datetime64) -> datetime:
    seconds = int(value.astype("datetime64[s]").astype(np.int64))
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def monday_week_start(value: datetime) -> date:
    if value.tzinfo is None:
        raise WeatherWeeklyError("Weather datetime must be timezone-aware.")
    return value.date() - timedelta(days=value.weekday())


def deaccumulate_precipitation(
    accumulated: np.ndarray,
    times: Sequence[datetime],
    *,
    previous_accumulated: np.ndarray | None,
    previous_time: datetime | None,
) -> tuple[np.ndarray, np.ndarray, datetime, int, float]:
    accumulated = np.asarray(accumulated, dtype=np.float64)
    if accumulated.ndim != 2 or accumulated.shape[0] != len(times):
        raise WeatherWeeklyError("Precipitation array/time shape mismatch.")
    hourly = np.full_like(accumulated, np.nan)
    correction_count = 0
    most_negative_corrected = 0.0
    float32_epsilon = float(np.finfo(np.float32).eps)
    prior_values = previous_accumulated
    prior_time = previous_time
    for index, current_time in enumerate(times):
        current = accumulated[index]
        if current_time.hour == 1:
            increment = current.copy()
        elif (
            prior_values is not None
            and prior_time is not None
            and current_time - prior_time == timedelta(hours=1)
        ):
            increment = current - prior_values
        else:
            increment = np.full_like(current, np.nan)
        finite = np.isfinite(increment)
        negative = finite & (increment < 0)
        if negative.any():
            comparison = np.maximum(
                1.0,
                np.maximum(
                    np.abs(current),
                    np.abs(prior_values) if prior_values is not None else 0.0,
                ),
            )
            tolerance = float32_epsilon * comparison
            invalid = negative & (increment < -tolerance)
            if invalid.any():
                minimum = float(np.nanmin(increment[invalid]))
                raise WeatherWeeklyError(
                    f"Precipitation deaccumulation produced a non-roundoff negative: {minimum}"
                )
            correction_count += int(negative.sum())
            most_negative_corrected = min(
                most_negative_corrected, float(np.nanmin(increment[negative]))
            )
            increment[negative] = 0.0
        hourly[index] = increment
        prior_values = current
        prior_time = current_time
    return hourly, accumulated[-1].copy(), times[-1], correction_count, most_negative_corrected


def spatial_weighted_mean(
    values: np.ndarray, weights: sparse.csr_matrix
) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)
    numerator = weights.dot(np.nan_to_num(values, nan=0.0).T).T
    denominator = weights.dot(finite.astype(np.float64).T).T
    if np.any(np.max(denominator, axis=0) <= 0):
        raise WeatherWeeklyError(
            "Municipality has no present intersecting weather cell in source block."
        )
    result = np.full_like(numerator, np.nan, dtype=np.float64)
    np.divide(numerator, denominator, out=result, where=denominator > 0)
    return result


def write_csv_rows(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            serialized: dict[str, object] = {}
            for column in columns:
                value = row.get(column)
                if value is None:
                    serialized[column] = ""
                elif isinstance(value, (date, datetime)):
                    serialized[column] = value.isoformat()
                elif isinstance(value, float):
                    serialized[column] = format(value, ".15g")
                elif isinstance(value, bool):
                    serialized[column] = str(value).lower()
                else:
                    serialized[column] = value
            writer.writerow(serialized)


def build_weekly_weather(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    paths = {key: resolve_repo_path(value) for key, value in config["sources"].items()}
    if any(not path.exists() for path in paths.values()):
        raise WeatherWeeklyError("One or more weather inputs are missing.")
    contract = config["source_contract"]
    monthly_files, skipped_lockbox_or_later = discover_development_files(
        paths["hourly_directory"],
        start_year=contract["development_start_year"],
        end_year=contract["development_end_year"],
        lockbox_year=contract["lockbox_year"],
    )
    codes = read_canonical_codes(paths["canonical_municipality"])

    reference_latitudes: np.ndarray | None = None
    reference_longitudes: np.ndarray | None = None
    weights: sparse.csr_matrix | None = None
    weight_rows: list[dict[str, object]] = []
    coverage_ratios: dict[str, float] = {}
    weekly_sums: dict[date, np.ndarray] = {}
    weekly_counts: dict[date, np.ndarray] = {}
    weekly_source_times: dict[date, set[datetime]] = defaultdict(set)
    raw_nan_counts = {name: 0 for name in SOURCE_VARIABLES}
    expver_values: set[str] = set()
    previous_time: datetime | None = None
    previous_tp: np.ndarray | None = None
    first_time: datetime | None = None
    last_time: datetime | None = None
    precipitation_roundoff_corrections = 0
    most_negative_corrected = 0.0
    opened_files: list[Path] = []

    for path in monthly_files:
        with xr.open_dataset(path) as dataset:
            if tuple(dataset.sizes) != ("valid_time", "latitude", "longitude"):
                if set(dataset.sizes) != {"valid_time", "latitude", "longitude"}:
                    raise WeatherWeeklyError(f"Unexpected dimensions in {path.name}")
            latitudes = np.asarray(dataset["latitude"].values, dtype=np.float64)
            longitudes = np.asarray(dataset["longitude"].values, dtype=np.float64)
            if reference_latitudes is None:
                reference_latitudes = latitudes
                reference_longitudes = longitudes
                weights, weight_rows, coverage_ratios = build_spatial_weights(
                    paths["municipality_geometry"],
                    codes=codes,
                    latitudes=latitudes,
                    longitudes=longitudes,
                    code_property=config["municipality_policy"]["code_property"],
                    area_crs=config["municipality_policy"]["area_crs"],
                )
            elif not np.array_equal(latitudes, reference_latitudes) or not np.array_equal(
                longitudes, reference_longitudes
            ):
                raise WeatherWeeklyError(f"ERA5-Land grid changed in {path.name}")
            if weights is None:
                raise WeatherWeeklyError("Spatial weights were not initialized.")
            for variable in SOURCE_VARIABLES:
                if variable not in dataset:
                    raise WeatherWeeklyError(f"{path.name} lacks {variable}")
                data_array = dataset[variable]
                if data_array.dims != ("valid_time", "latitude", "longitude"):
                    raise WeatherWeeklyError(f"Unexpected {variable} dimensions in {path.name}")
                if data_array.attrs.get("units") != EXPECTED_UNITS[variable]:
                    raise WeatherWeeklyError(f"Unexpected {variable} unit in {path.name}")
            times = [datetime64_to_utc(value) for value in dataset["valid_time"].values]
            if not times or any(
                later - earlier != timedelta(hours=1)
                for earlier, later in zip(times, times[1:])
            ):
                raise WeatherWeeklyError(f"Non-hourly or empty time axis in {path.name}")
            if previous_time is not None and times[0] - previous_time != timedelta(hours=1):
                raise WeatherWeeklyError(f"Gap between ERA5-Land files before {path.name}")
            if any(time.year >= contract["lockbox_year"] for time in times):
                raise WeatherWeeklyError("A lockbox-year weather value was opened.")
            cutoff = datetime.fromisoformat(contract["weather_cutoff"].replace("Z", "+00:00"))
            if any(time > cutoff for time in times):
                raise WeatherWeeklyError("Weather data exceed the configured cutoff.")
            observed_expver = {str(value) for value in np.unique(dataset["expver"].values)}
            if observed_expver != {contract["required_expver"]}:
                raise WeatherWeeklyError(f"Unexpected expver in {path.name}: {observed_expver}")
            expver_values.update(observed_expver)

            flattened: dict[str, np.ndarray] = {}
            for variable in SOURCE_VARIABLES:
                values = np.asarray(dataset[variable].values, dtype=np.float64)
                raw_nan_counts[variable] += int(np.isnan(values).sum())
                flattened[variable] = values.reshape(len(times), -1)
            hourly_tp, previous_tp, _, corrections, corrected_minimum = (
                deaccumulate_precipitation(
                    flattened["tp"],
                    times,
                    previous_accumulated=previous_tp,
                    previous_time=previous_time,
                )
            )
            precipitation_roundoff_corrections += corrections
            most_negative_corrected = min(most_negative_corrected, corrected_minimum)
            hourly_by_output = {
                "t2m_mean_c": spatial_weighted_mean(flattened["t2m"], weights) - 273.15,
                "d2m_mean_c": spatial_weighted_mean(flattened["d2m"], weights) - 273.15,
                "tp_sum_mm": spatial_weighted_mean(hourly_tp, weights) * 1000.0,
                "stl1_mean_c": spatial_weighted_mean(flattened["stl1"], weights) - 273.15,
                "stl2_mean_c": spatial_weighted_mean(flattened["stl2"], weights) - 273.15,
                "swvl1_mean_m3_m3": spatial_weighted_mean(flattened["swvl1"], weights),
                "swvl2_mean_m3_m3": spatial_weighted_mean(flattened["swvl2"], weights),
            }
            stacked = np.stack(
                [hourly_by_output[name] for name in OUTPUT_VARIABLES], axis=2
            )
            for time_index, time in enumerate(times):
                week_start = monday_week_start(time)
                weekly_source_times[week_start].add(time)
                if week_start not in weekly_sums:
                    weekly_sums[week_start] = np.zeros(
                        (len(codes), len(OUTPUT_VARIABLES)), dtype=np.float64
                    )
                    weekly_counts[week_start] = np.zeros(
                        (len(codes), len(OUTPUT_VARIABLES)), dtype=np.int64
                    )
                values = stacked[time_index]
                present = np.isfinite(values)
                weekly_sums[week_start] += np.where(present, values, 0.0)
                weekly_counts[week_start] += present.astype(np.int64)
            first_time = first_time or times[0]
            last_time = times[-1]
            previous_time = times[-1]
            opened_files.append(path)

    if first_time != datetime(2016, 3, 30, tzinfo=timezone.utc):
        raise WeatherWeeklyError(f"Unexpected first weather time: {first_time}")
    expected_last = datetime(2024, 12, 31, 23, tzinfo=timezone.utc)
    if last_time != expected_last:
        raise WeatherWeeklyError(f"Unexpected weather cutoff: {last_time}")

    weekly_rows: list[dict[str, object]] = []
    complete_weeks = 0
    incomplete_weeks = 0
    for week_start in sorted(weekly_sums):
        source_hour_count = len(weekly_source_times[week_start])
        counts = weekly_counts[week_start]
        sums = weekly_sums[week_start]
        week_is_complete = source_hour_count == 168 and bool(np.all(counts == 168))
        if week_is_complete:
            complete_weeks += 1
        else:
            incomplete_weeks += 1
        for municipality_index, code in enumerate(codes):
            minimum_present = int(counts[municipality_index].min())
            row: dict[str, object] = {
                "municipality_code": code,
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "weather_status": (
                    "complete" if week_is_complete else "incomplete_source_week"
                ),
                "source_hour_count": source_hour_count,
                "minimum_present_hours": minimum_present,
            }
            for variable_index, output in enumerate(OUTPUT_VARIABLES):
                if not week_is_complete:
                    row[output] = None
                elif output in MEAN_OUTPUTS:
                    row[output] = sums[municipality_index, variable_index] / 168.0
                else:
                    row[output] = sums[municipality_index, variable_index]
            weekly_rows.append(row)

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    weekly_path = output_directory / config["outputs"]["weekly_weather"]
    weights_path = output_directory / config["outputs"]["spatial_weights"]
    quality_path = output_directory / config["outputs"]["quality_summary"]
    if any(path.parent != output_directory for path in (weekly_path, weights_path, quality_path)):
        raise WeatherWeeklyError("Weather output names must not contain directories.")
    write_csv_rows(weekly_path, WEEKLY_COLUMNS, weekly_rows)
    write_csv_rows(weights_path, WEIGHT_COLUMNS, weight_rows)

    source_records = [file_record(path) for path in opened_files]
    complete_rows = sum(row["weather_status"] == "complete" for row in weekly_rows)
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.features.weather_weekly",
        "status": "pass",
        "policy": {
            "availability_rule": contract["availability_rule"],
            "weather_cutoff": contract["weather_cutoff"],
            "post_cutoff_rule": contract["post_cutoff_rule"],
            "fixed_analytical_zones_all_years": True,
            "issue_feature_rule": "only_completed_weather_weeks_strictly_before_issue_week",
        },
        "sources": {
            "hourly_files": source_records,
            "raw_readme": file_record(paths["raw_readme"]),
            "municipality_geometry": file_record(paths["municipality_geometry"]),
            "canonical_municipality": file_record(paths["canonical_municipality"]),
            "config": file_record(config_path),
            "builder": file_record(Path(__file__).resolve()),
        },
        "source_audit": {
            "files_opened": len(opened_files),
            "files_from_lockbox_year_opened": 0,
            "lockbox_or_later_filenames_skipped_before_open": skipped_lockbox_or_later,
            "first_valid_time": first_time.isoformat(),
            "last_valid_time": last_time.isoformat(),
            "expver_values": sorted(expver_values),
            "grid_shape": [
                len(reference_latitudes) if reference_latitudes is not None else 0,
                len(reference_longitudes) if reference_longitudes is not None else 0,
            ],
            "raw_nan_counts": raw_nan_counts,
            "precipitation_roundoff_negative_corrections": precipitation_roundoff_corrections,
            "most_negative_precipitation_roundoff_corrected_m": most_negative_corrected,
        },
        "spatial_audit": {
            "municipality_count": len(codes),
            "weight_row_count": len(weight_rows),
            "minimum_geometry_coverage_ratio": min(coverage_ratios.values()),
            "maximum_geometry_coverage_ratio": max(coverage_ratios.values()),
            "fixed_zone_snapshot": config["municipality_policy"]["geometry_snapshot"],
        },
        "weekly_dataset": {
            **file_record(weekly_path),
            "columns": list(WEEKLY_COLUMNS),
            "primary_key": ["municipality_code", "week_start"],
            "row_count": len(weekly_rows),
            "complete_row_count": complete_rows,
            "incomplete_row_count": len(weekly_rows) - complete_rows,
            "distinct_week_count": len(weekly_sums),
            "complete_week_count": complete_weeks,
            "incomplete_week_count": incomplete_weeks,
        },
        "spatial_weights_dataset": {
            **file_record(weights_path),
            "columns": list(WEIGHT_COLUMNS),
            "row_count": len(weight_rows),
        },
        "variables": config["variables"],
        "checks": {
            "only_development_files_opened": all(
                int(FILE_PATTERN.match(path.name).group(1)) < contract["lockbox_year"]
                for path in opened_files
            ),
            "weather_cutoff_exact": last_time == expected_last,
            "no_post_cutoff_weather_created": max(weekly_sums) <= expected_last.date(),
            "all_source_expver_is_0001": expver_values == {"0001"},
            "fixed_212_municipality_zones_all_years": len(codes) == 212,
            "spatial_weights_sum_to_one": bool(
                np.allclose(weights.sum(axis=1), 1.0, rtol=0.0, atol=1e-12)
            ),
            "weekly_primary_key_unique": len(weekly_rows)
            == len({(row["municipality_code"], row["week_start"]) for row in weekly_rows}),
            "incomplete_weeks_explicit_and_values_blank": all(
                row["weather_status"] == "complete"
                or all(row[output] is None for output in OUTPUT_VARIABLES)
                for row in weekly_rows
            ),
            "missing_weather_never_converted_to_zero": True,
            "precipitation_large_negative_differences_absent": True,
        },
        "library_versions": {
            "numpy": np.__version__,
            "scipy": importlib.metadata.version("scipy"),
            "xarray": xr.__version__,
            "netCDF4": netCDF4.__version__,
            "shapely": shapely.__version__,
            "pyproj": pyproj.__version__,
        },
    }
    if not all(quality["checks"].values()):
        quality["status"] = "fail"
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if quality["status"] != "pass":
        raise WeatherWeeklyError("Weekly weather quality checks failed.")
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fixed-municipality weekly ERA5-Land weather."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_weekly_weather(config_path)
    dataset = quality["weekly_dataset"]
    print("ERA5-Land municipality-week weather built.")
    print(f"- files opened: {quality['source_audit']['files_opened']}")
    print(f"- rows: {dataset['row_count']}")
    print(f"- complete weeks: {dataset['complete_week_count']}")
    print(f"- cutoff: {quality['policy']['weather_cutoff']}")
    print("No 2025+ weather file was opened and no post-cutoff weather was created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
