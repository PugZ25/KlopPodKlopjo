from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import xarray as xr
from scipy import sparse

from model_v3.features.weather_weekly import (
    EXPECTED_UNITS,
    MEAN_OUTPUTS,
    OUTPUT_VARIABLES,
    SOURCE_VARIABLES,
    WEEKLY_COLUMNS,
    deaccumulate_precipitation,
    datetime64_to_utc,
    monday_week_start,
    spatial_weighted_mean,
    write_csv_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "era5_land_operational.json"
GRIB_TO_SOURCE_VARIABLE = {
    "2t": "t2m",
    "2d": "d2m",
    "tp": "tp",
    "stl1": "stl1",
    "stl2": "stl2",
    "swvl1": "swvl1",
    "swvl2": "swvl2",
}


class OperationalWeatherError(ValueError):
    """Raised when operational weather violates its source or feature contract."""


@dataclass(frozen=True)
class WeatherWindow:
    issue_week: date
    weather_start: date
    weather_end: date
    source_context_start: date


@dataclass(frozen=True)
class SourceFile:
    latitudes: np.ndarray
    longitudes: np.ndarray
    times: tuple[datetime, ...]
    expver: str
    values: Mapping[str, np.ndarray]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(value: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def repository_path(path: Path, repo_root: Path = REPO_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def parse_utc_datetime(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise OperationalWeatherError(f"Invalid {label}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise OperationalWeatherError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def parse_monday(value: str | date, *, label: str = "issue_week") -> date:
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise OperationalWeatherError(f"Invalid {label}: {value!r}") from exc
    if parsed.weekday() != 0:
        raise OperationalWeatherError(f"{label} must be a Monday: {parsed}")
    return parsed


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise OperationalWeatherError("Operational weather config must be in repository")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise OperationalWeatherError("Operational weather schema_version must equal 1")
    source = config.get("source", {})
    if source.get("dataset") != "reanalysis-era5-land":
        raise OperationalWeatherError("Operational source must be reanalysis-era5-land")
    if tuple(source.get("allowed_expver", ())) != ("0001", "0005"):
        raise OperationalWeatherError("Allowed ERA5-Land expver contract changed")
    if source.get("data_format") != "grib":
        raise OperationalWeatherError(
            "Operational ERA5-Land must use GRIB so expver provenance is retained"
        )
    if source.get("variables") != [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "total_precipitation",
        "soil_temperature_level_1",
        "soil_temperature_level_2",
        "volumetric_soil_water_layer_1",
        "volumetric_soil_water_layer_2",
    ]:
        raise OperationalWeatherError("Operational ERA5-Land variable contract changed")
    if config.get("feature_contract", {}).get("required_completed_weather_weeks") != [4, 3, 2, 1]:
        raise OperationalWeatherError("Operational weather window must be t-4 through t-1")
    if config.get("bridge", {}).get("promotion_thresholds") is not None:
        raise OperationalWeatherError(
            "Bridge thresholds require a separately reviewed configuration version"
        )
    return config


def weather_window(issue_week: str | date) -> WeatherWindow:
    issue = parse_monday(issue_week)
    weather_start = issue - timedelta(weeks=4)
    weather_end = issue - timedelta(days=1)
    return WeatherWindow(
        issue_week=issue,
        weather_start=weather_start,
        weather_end=weather_end,
        source_context_start=weather_start - timedelta(days=1),
    )


def nominal_available_through(as_of: datetime, *, lag_days: int) -> date:
    if as_of.tzinfo is None:
        raise OperationalWeatherError("as_of must be timezone-aware")
    if isinstance(lag_days, bool) or not isinstance(lag_days, int) or lag_days < 0:
        raise OperationalWeatherError("nominal availability lag must be a non-negative integer")
    return as_of.astimezone(timezone.utc).date() - timedelta(days=lag_days)


def latest_ready_issue_week(as_of: datetime, *, lag_days: int) -> date:
    available = nominal_available_through(as_of, lag_days=lag_days)
    candidate = as_of.astimezone(timezone.utc).date()
    candidate -= timedelta(days=candidate.weekday())
    while candidate - timedelta(days=1) > available:
        candidate -= timedelta(weeks=1)
    return candidate


def _month_chunks(start: date, end: date) -> list[tuple[int, int, list[str]]]:
    if start > end:
        raise OperationalWeatherError("CDS request start is after end")
    chunks: list[tuple[int, int, list[str]]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        month_end = date(
            cursor.year,
            cursor.month,
            calendar.monthrange(cursor.year, cursor.month)[1],
        )
        selected_start = max(start, cursor)
        selected_end = min(end, month_end)
        days = [f"{day:02d}" for day in range(selected_start.day, selected_end.day + 1)]
        chunks.append((cursor.year, cursor.month, days))
        cursor = month_end + timedelta(days=1)
    return chunks


def build_cds_requests(
    config: Mapping[str, Any], issue_week: str | date
) -> tuple[WeatherWindow, list[dict[str, Any]]]:
    window = weather_window(issue_week)
    source = config["source"]
    requests: list[dict[str, Any]] = []
    for year, month, days in _month_chunks(window.source_context_start, window.weather_end):
        request = {
            "variable": list(source["variables"]),
            "year": f"{year:04d}",
            "month": f"{month:02d}",
            "day": days,
            "time": list(source["hours_utc"]),
            "area": list(source["area_north_west_south_east"]),
            "data_format": source["data_format"],
            "download_format": source["download_format"],
        }
        requests.append(
            {
                "request": request,
                "filename": (
                    f"era5land_operational_{year:04d}_{month:02d}_"
                    f"{days[0]}-{days[-1]}.grib"
                ),
            }
        )
    return window, requests


def _retrieval_id(issue_week: date, retrieved_at: datetime) -> str:
    timestamp = retrieved_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"issue_{issue_week.isoformat()}__retrieved_{timestamp}"


def sync_operational_weather(
    config: Mapping[str, Any],
    *,
    issue_week: str | date,
    retrieved_at: datetime,
    client: Any | None = None,
    repo_root: Path = REPO_ROOT,
) -> Path:
    issue = parse_monday(issue_week)
    source = config["source"]
    available = nominal_available_through(
        retrieved_at, lag_days=int(source["nominal_availability_lag_days"])
    )
    window, requests = build_cds_requests(config, issue)
    if window.weather_end > available:
        raise OperationalWeatherError(
            "Required t-1 weather is not nominally available: "
            f"required_through={window.weather_end}, available_through={available}"
        )
    if client is None:
        try:
            import cdsapi
        except ImportError as exc:
            raise OperationalWeatherError("cdsapi is required for operational sync") from exc
        client = cdsapi.Client()

    retrieval_root = resolve_repo_path(config["outputs"]["retrieval_root"], repo_root)
    retrieval_id = _retrieval_id(issue, retrieved_at)
    retrieval_directory = retrieval_root / retrieval_id
    retrieval_directory.mkdir(parents=True, exist_ok=False)
    file_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    for index, planned in enumerate(requests, start=1):
        target = retrieval_directory / planned["filename"]
        temporary_target = target.with_suffix(target.suffix + ".part")
        result = client.retrieve(source["dataset"], planned["request"])
        result.download(str(temporary_target))
        if not temporary_target.is_file() or temporary_target.stat().st_size <= 0:
            raise OperationalWeatherError(f"CDS returned an empty file for request {index}")
        temporary_target.replace(target)
        file_rows.append(
            {
                "path": target.name,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )
        request_rows.append(
            {
                "dataset": source["dataset"],
                "request": planned["request"],
                "target": target.name,
            }
        )

    manifest = {
        "schema_version": 1,
        "retrieval_id": retrieval_id,
        "retrieved_at_utc": retrieved_at.astimezone(timezone.utc).isoformat(),
        "issue_week": issue.isoformat(),
        "requested_weather_start": window.weather_start.isoformat(),
        "requested_weather_end": window.weather_end.isoformat(),
        "source_context_start": window.source_context_start.isoformat(),
        "nominal_available_through": available.isoformat(),
        "dataset": source["dataset"],
        "data_format": source["data_format"],
        "requests": request_rows,
        "files": file_rows,
    }
    manifest_path = retrieval_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _normalise_expver(value: Any) -> str:
    text = str(value)
    if text.startswith("b'") and text.endswith("'"):
        text = text[2:-1]
    try:
        return f"{int(text):04d}"
    except ValueError:
        if len(text) == 4 and text.isdigit():
            return text
        raise OperationalWeatherError(f"Invalid ERA5-Land expver: {value!r}")


def _load_weight_matrix(
    path: Path,
    *,
    expected_sha256: str,
    municipality_path: Path,
    municipality_sha256: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> tuple[tuple[str, ...], sparse.csr_matrix, int]:
    if sha256_file(path) != expected_sha256:
        raise OperationalWeatherError("Frozen weather weight SHA-256 mismatch")
    if sha256_file(municipality_path) != municipality_sha256:
        raise OperationalWeatherError("Canonical municipality SHA-256 mismatch")
    with municipality_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "municipality_code" not in reader.fieldnames:
            raise OperationalWeatherError("Canonical municipality schema is invalid")
        codes = tuple(row["municipality_code"] for row in reader)
    if not codes or len(set(codes)) != len(codes):
        raise OperationalWeatherError("Canonical municipality codes are empty or duplicated")

    grid_size = int(len(latitudes) * len(longitudes))
    code_index = {code: index for index, code in enumerate(codes)}
    matrix = sparse.lil_matrix((len(codes), grid_size), dtype=np.float64)
    row_count = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "municipality_code",
            "grid_cell_index",
            "latitude",
            "longitude",
            "normalized_intersection_weight",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise OperationalWeatherError("Frozen weather weight schema is invalid")
        for row in reader:
            code = row["municipality_code"]
            if code not in code_index:
                raise OperationalWeatherError(f"Weight contains unknown municipality: {code}")
            grid_index = int(row["grid_cell_index"])
            if grid_index < 0 or grid_index >= grid_size:
                raise OperationalWeatherError("Weight grid_cell_index is outside downloaded grid")
            latitude_index, longitude_index = divmod(grid_index, len(longitudes))
            if not math.isclose(
                float(row["latitude"]), float(latitudes[latitude_index]), rel_tol=0.0, abs_tol=1e-12
            ) or not math.isclose(
                float(row["longitude"]), float(longitudes[longitude_index]), rel_tol=0.0, abs_tol=1e-12
            ):
                raise OperationalWeatherError(
                    "Downloaded ERA5-Land coordinates do not match frozen weight grid"
                )
            weight = float(row["normalized_intersection_weight"])
            if not math.isfinite(weight) or weight <= 0:
                raise OperationalWeatherError("Spatial weight must be finite and positive")
            matrix[code_index[code], grid_index] = weight
            row_count += 1
    result = matrix.tocsr()
    if not np.allclose(result.sum(axis=1), 1.0, rtol=0.0, atol=1e-12):
        raise OperationalWeatherError("Frozen municipality weights do not sum to one")
    return codes, result, row_count


def _read_manifest(path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise OperationalWeatherError("Unsupported operational retrieval manifest")
    required = set(config["provenance"]["required_manifest_fields"])
    missing = sorted(required - set(manifest))
    if missing:
        raise OperationalWeatherError(f"Retrieval manifest is missing fields: {missing}")
    if manifest["dataset"] != config["source"]["dataset"]:
        raise OperationalWeatherError("Retrieval dataset differs from operational config")
    if manifest["data_format"] != config["source"]["data_format"]:
        raise OperationalWeatherError("Retrieval format differs from operational config")
    parse_monday(manifest["issue_week"])
    parse_utc_datetime(manifest["retrieved_at_utc"], label="retrieved_at_utc")
    return manifest


def _read_netcdf_source(path: Path) -> SourceFile:
    with xr.open_dataset(path) as dataset:
        if set(dataset.sizes) != {"valid_time", "latitude", "longitude"}:
            raise OperationalWeatherError(f"Unexpected NetCDF dimensions in {path.name}")
        latitudes = np.asarray(dataset["latitude"].values, dtype=np.float64)
        longitudes = np.asarray(dataset["longitude"].values, dtype=np.float64)
        values: dict[str, np.ndarray] = {}
        for variable in SOURCE_VARIABLES:
            if variable not in dataset:
                raise OperationalWeatherError(f"{path.name} lacks {variable}")
            array = dataset[variable]
            if array.dims != ("valid_time", "latitude", "longitude"):
                raise OperationalWeatherError(f"Unexpected {variable} dimensions")
            if array.attrs.get("units") != EXPECTED_UNITS[variable]:
                raise OperationalWeatherError(
                    f"Unexpected {variable} unit: {array.attrs.get('units')!r}"
                )
            values[variable] = np.asarray(array.values, dtype=np.float64)
        if "expver" not in dataset:
            raise OperationalWeatherError(
                "NetCDF lacks expver; operational retrievals must use provenance-preserving GRIB"
            )
        observed_expver = {
            _normalise_expver(value) for value in np.unique(dataset["expver"].values)
        }
        if len(observed_expver) != 1:
            raise OperationalWeatherError(
                f"Source contains mixed expver values: {sorted(observed_expver)}"
            )
        times = tuple(
            datetime64_to_utc(value) for value in dataset["valid_time"].values
        )
    return SourceFile(
        latitudes=latitudes,
        longitudes=longitudes,
        times=times,
        expver=next(iter(observed_expver)),
        values=values,
    )


def _read_grib_source(path: Path) -> SourceFile:
    try:
        from eccodes import (
            codes_get,
            codes_get_array,
            codes_get_values,
            codes_grib_new_from_file,
            codes_release,
        )
    except ImportError as exc:
        raise OperationalWeatherError(
            "eccodes is required for provenance-preserving operational GRIB"
        ) from exc

    message_values: dict[tuple[str, datetime], np.ndarray] = {}
    variable_times: dict[str, list[datetime]] = defaultdict(list)
    reference_latitudes: np.ndarray | None = None
    reference_longitudes: np.ndarray | None = None
    expver_values: set[str] = set()
    with path.open("rb") as handle:
        while True:
            message = codes_grib_new_from_file(handle)
            if message is None:
                break
            try:
                grib_short_name = str(codes_get(message, "shortName"))
                short_name = GRIB_TO_SOURCE_VARIABLE.get(grib_short_name)
                if short_name is None:
                    raise OperationalWeatherError(
                        f"Unexpected GRIB variable in {path.name}: {grib_short_name}"
                    )
                unit = str(codes_get(message, "units"))
                if unit != EXPECTED_UNITS[short_name]:
                    raise OperationalWeatherError(
                        f"Unexpected {short_name} GRIB unit in {path.name}: {unit!r}"
                    )
                expver_values.add(
                    _normalise_expver(codes_get(message, "experimentVersionNumber"))
                )
                valid_date = int(codes_get(message, "validityDate"))
                valid_time = int(codes_get(message, "validityTime"))
                timestamp = datetime.strptime(
                    f"{valid_date:08d}{valid_time:04d}", "%Y%m%d%H%M"
                ).replace(tzinfo=timezone.utc)
                raw_latitudes = np.asarray(
                    codes_get_array(message, "latitudes"), dtype=np.float64
                )
                raw_longitudes = np.asarray(
                    codes_get_array(message, "longitudes"), dtype=np.float64
                )
                raw_values = np.asarray(codes_get_values(message), dtype=np.float64)
                if not (
                    raw_latitudes.shape == raw_longitudes.shape == raw_values.shape
                ):
                    raise OperationalWeatherError("GRIB coordinates and values differ in size")
                latitudes = np.asarray(
                    sorted(set(raw_latitudes.tolist()), reverse=True), dtype=np.float64
                )
                longitudes = np.asarray(
                    sorted(set(raw_longitudes.tolist())), dtype=np.float64
                )
                if len(latitudes) * len(longitudes) != len(raw_values):
                    raise OperationalWeatherError("GRIB source is not a complete regular grid")
                if reference_latitudes is None:
                    reference_latitudes = latitudes
                    reference_longitudes = longitudes
                elif not np.array_equal(latitudes, reference_latitudes) or not np.array_equal(
                    longitudes, reference_longitudes
                ):
                    raise OperationalWeatherError("GRIB grid changes between messages")
                latitude_index = {
                    round(float(value), 10): index for index, value in enumerate(latitudes)
                }
                longitude_index = {
                    round(float(value), 10): index for index, value in enumerate(longitudes)
                }
                grid = np.full((len(latitudes), len(longitudes)), np.nan, dtype=np.float64)
                try:
                    missing_value = float(codes_get(message, "missingValue"))
                except Exception:
                    missing_value = math.nan
                for latitude, longitude, value in zip(
                    raw_latitudes, raw_longitudes, raw_values, strict=True
                ):
                    if math.isfinite(missing_value) and value == missing_value:
                        value = math.nan
                    grid[
                        latitude_index[round(float(latitude), 10)],
                        longitude_index[round(float(longitude), 10)],
                    ] = value
                key = (short_name, timestamp)
                if key in message_values:
                    raise OperationalWeatherError(f"Duplicate GRIB message: {key}")
                message_values[key] = grid
                variable_times[short_name].append(timestamp)
            finally:
                codes_release(message)
    if reference_latitudes is None or reference_longitudes is None:
        raise OperationalWeatherError(f"GRIB source is empty: {path.name}")
    if set(variable_times) != set(SOURCE_VARIABLES):
        raise OperationalWeatherError(
            f"GRIB variables differ from contract: {sorted(variable_times)}"
        )
    reference_times = tuple(sorted(variable_times[SOURCE_VARIABLES[0]]))
    if not reference_times:
        raise OperationalWeatherError(f"GRIB source has no valid times: {path.name}")
    values = {}
    for variable in SOURCE_VARIABLES:
        times = tuple(sorted(variable_times[variable]))
        if times != reference_times:
            raise OperationalWeatherError(
                f"GRIB valid-time support differs for {variable} in {path.name}"
            )
        values[variable] = np.stack(
            [message_values[(variable, timestamp)] for timestamp in reference_times]
        )
    if len(expver_values) != 1:
        raise OperationalWeatherError(
            f"GRIB source contains mixed expver values: {sorted(expver_values)}"
        )
    return SourceFile(
        latitudes=reference_latitudes,
        longitudes=reference_longitudes,
        times=reference_times,
        expver=next(iter(expver_values)),
        values=values,
    )


def _read_source_file(path: Path, *, data_format: str) -> SourceFile:
    if data_format == "grib":
        return _read_grib_source(path)
    if data_format == "netcdf":
        return _read_netcdf_source(path)
    raise OperationalWeatherError(f"Unsupported operational source format: {data_format}")


def build_operational_weekly_weather(
    config: Mapping[str, Any],
    manifest_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path, Path]:
    manifest_path = manifest_path.resolve()
    manifest = _read_manifest(manifest_path, config)
    issue = parse_monday(manifest["issue_week"])
    window = weather_window(issue)
    if manifest["requested_weather_start"] != window.weather_start.isoformat():
        raise OperationalWeatherError("Manifest requested_weather_start is inconsistent")
    if manifest["requested_weather_end"] != window.weather_end.isoformat():
        raise OperationalWeatherError("Manifest requested_weather_end is inconsistent")
    if manifest["source_context_start"] != window.source_context_start.isoformat():
        raise OperationalWeatherError("Manifest source_context_start is inconsistent")

    file_paths: list[Path] = []
    for record in manifest["files"]:
        path = manifest_path.parent / record["path"]
        if not path.is_file() or path.stat().st_size != int(record["bytes"]):
            raise OperationalWeatherError(f"Raw operational weather file is missing: {path}")
        if sha256_file(path) != record["sha256"]:
            raise OperationalWeatherError(f"Raw operational weather hash mismatch: {path}")
        file_paths.append(path)
    if not file_paths:
        raise OperationalWeatherError("Retrieval manifest contains no raw files")

    reference_latitudes: np.ndarray | None = None
    reference_longitudes: np.ndarray | None = None
    municipality_codes: tuple[str, ...] | None = None
    weights: sparse.csr_matrix | None = None
    weight_row_count = 0
    weekly_sums: dict[date, np.ndarray] = {}
    weekly_counts: dict[date, np.ndarray] = {}
    weekly_times: dict[date, set[datetime]] = defaultdict(set)
    all_times: list[datetime] = []
    expver_values: set[str] = set()
    previous_time: datetime | None = None
    previous_tp: np.ndarray | None = None
    precipitation_corrections = 0

    spatial_config = config["spatial_contract"]
    for path in file_paths:
            source_file = _read_source_file(
                path, data_format=str(manifest["data_format"])
            )
            latitudes = source_file.latitudes
            longitudes = source_file.longitudes
            if reference_latitudes is None:
                reference_latitudes = latitudes
                reference_longitudes = longitudes
                municipality_codes, weights, weight_row_count = _load_weight_matrix(
                    resolve_repo_path(spatial_config["weights"], repo_root),
                    expected_sha256=spatial_config["weights_sha256"],
                    municipality_path=resolve_repo_path(spatial_config["municipality"], repo_root),
                    municipality_sha256=spatial_config["municipality_sha256"],
                    latitudes=latitudes,
                    longitudes=longitudes,
                )
            elif not np.array_equal(latitudes, reference_latitudes) or not np.array_equal(
                longitudes, reference_longitudes
            ):
                raise OperationalWeatherError("ERA5-Land grid changed between raw files")
            if weights is None or municipality_codes is None:
                raise OperationalWeatherError("Operational spatial weights were not initialized")
            observed_expver = {source_file.expver}
            disallowed = observed_expver - set(config["source"]["allowed_expver"])
            if disallowed:
                raise OperationalWeatherError(f"Disallowed ERA5-Land expver: {sorted(disallowed)}")
            expver_values.update(observed_expver)

            times = list(source_file.times)
            if not times or any(
                later - earlier != timedelta(hours=1)
                for earlier, later in zip(times, times[1:])
            ):
                raise OperationalWeatherError(f"Non-hourly or empty time axis in {path.name}")
            if previous_time is not None and times[0] - previous_time != timedelta(hours=1):
                raise OperationalWeatherError(f"Gap or overlap before {path.name}")

            flattened = {
                variable: source_file.values[variable].reshape(len(times), -1)
                for variable in SOURCE_VARIABLES
            }
            hourly_tp, previous_tp, _, corrections, _ = deaccumulate_precipitation(
                flattened["tp"],
                times,
                previous_accumulated=previous_tp,
                previous_time=previous_time,
            )
            precipitation_corrections += corrections
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
            for time_index, timestamp in enumerate(times):
                week_start = monday_week_start(timestamp)
                weekly_times[week_start].add(timestamp)
                if week_start not in weekly_sums:
                    weekly_sums[week_start] = np.zeros(
                        (len(municipality_codes), len(OUTPUT_VARIABLES)), dtype=np.float64
                    )
                    weekly_counts[week_start] = np.zeros(
                        (len(municipality_codes), len(OUTPUT_VARIABLES)), dtype=np.int64
                    )
                values = stacked[time_index]
                present = np.isfinite(values)
                weekly_sums[week_start] += np.where(present, values, 0.0)
                weekly_counts[week_start] += present.astype(np.int64)
            all_times.extend(times)
            previous_time = times[-1]

    if len(expver_values) != 1:
        raise OperationalWeatherError(
            f"A retrieval must contain exactly one ERA5-Land vintage, got {sorted(expver_values)}"
        )
    if reference_latitudes is None or reference_longitudes is None or municipality_codes is None:
        raise OperationalWeatherError("Operational weather source is empty")
    expected_first = datetime.combine(window.source_context_start, datetime.min.time(), timezone.utc)
    expected_last = datetime.combine(window.weather_end, datetime.max.time(), timezone.utc).replace(
        hour=23, minute=0, second=0, microsecond=0
    )
    if all_times[0] != expected_first or all_times[-1] != expected_last:
        raise OperationalWeatherError(
            f"Operational valid-time coverage mismatch: {all_times[0]} through {all_times[-1]}"
        )
    if len(all_times) != len(set(all_times)):
        raise OperationalWeatherError("Operational valid times contain duplicates")

    required_starts = [issue - timedelta(weeks=lag) for lag in (4, 3, 2, 1)]
    rows: list[dict[str, object]] = []
    for week_start in required_starts:
        if len(weekly_times.get(week_start, set())) != 168:
            raise OperationalWeatherError(f"Required weather week is incomplete: {week_start}")
        counts = weekly_counts[week_start]
        if not bool(np.all(counts == 168)):
            raise OperationalWeatherError(
                f"Required municipality weather values are incomplete: {week_start}"
            )
        sums = weekly_sums[week_start]
        for municipality_index, code in enumerate(municipality_codes):
            row: dict[str, object] = {
                "municipality_code": code,
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "weather_status": "complete",
                "source_hour_count": 168,
                "minimum_present_hours": 168,
            }
            for variable_index, output in enumerate(OUTPUT_VARIABLES):
                value = sums[municipality_index, variable_index]
                row[output] = value / 168.0 if output in MEAN_OUTPUTS else value
            rows.append(row)

    derived_directory = manifest_path.parent / "derived"
    derived_directory.mkdir(parents=True, exist_ok=False)
    weekly_path = derived_directory / config["outputs"]["weekly_weather"]
    quality_path = derived_directory / config["outputs"]["quality_summary"]
    write_csv_rows(weekly_path, WEEKLY_COLUMNS, rows)
    expver = next(iter(expver_values))
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.features.weather_operational",
        "status": "pass",
        "issue_week": issue.isoformat(),
        "retrieval_id": manifest["retrieval_id"],
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "weather_vintage": config["source"]["vintage_labels"][expver],
        "expver": expver,
        "source_valid_time_start": all_times[0].isoformat(),
        "source_valid_time_end": all_times[-1].isoformat(),
        "weather_feature_week_start": required_starts[0].isoformat(),
        "weather_feature_week_end": (required_starts[-1] + timedelta(days=6)).isoformat(),
        "municipality_count": len(municipality_codes),
        "complete_week_count": 4,
        "row_count": len(rows),
        "grid_shape": [len(reference_latitudes), len(reference_longitudes)],
        "grid_sha256": hashlib.sha256(
            reference_latitudes.tobytes() + reference_longitudes.tobytes()
        ).hexdigest(),
        "spatial_weight_row_count": weight_row_count,
        "precipitation_roundoff_negative_corrections": precipitation_corrections,
        "sources": {
            "manifest": {
                "path": repository_path(manifest_path, repo_root),
                "sha256": sha256_file(manifest_path),
            },
            "raw_files": manifest["files"],
            "frozen_weights_sha256": spatial_config["weights_sha256"],
            "canonical_municipality_sha256": spatial_config["municipality_sha256"],
        },
        "weekly_dataset": {
            "path": repository_path(weekly_path, repo_root),
            "sha256": sha256_file(weekly_path),
            "columns": list(WEEKLY_COLUMNS),
            "primary_key": ["municipality_code", "week_start"],
        },
        "checks": {
            "single_expver_vintage": True,
            "downloaded_grid_matches_frozen_weights": True,
            "spatial_weights_sum_to_one": True,
            "exactly_four_completed_pre_issue_weeks": True,
            "all_weeks_have_168_hours": True,
            "missing_weather_never_filled_or_zeroed": True,
            "current_and_future_weather_excluded": True,
            "raw_file_hashes_verified": True,
        },
    }
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return weekly_path, quality_path


def _read_complete_weekly(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    result: dict[tuple[str, str], dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEEKLY_COLUMNS:
            raise OperationalWeatherError("Bridge weekly weather schema is invalid")
        for row in reader:
            if row["weather_status"] != "complete":
                raise OperationalWeatherError("Bridge accepts complete weather rows only")
            key = (row["municipality_code"], row["week_start"])
            if key in result:
                raise OperationalWeatherError(f"Duplicate bridge weather row: {key}")
            values = {column: float(row[column]) for column in OUTPUT_VARIABLES}
            if not all(math.isfinite(value) for value in values.values()):
                raise OperationalWeatherError("Bridge weather contains non-finite values")
            result[key] = values
    if not result:
        raise OperationalWeatherError("Bridge weather input is empty")
    return result


def build_bridge_summary(
    config: Mapping[str, Any],
    preliminary_path: Path,
    final_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    preliminary = _read_complete_weekly(preliminary_path)
    final = _read_complete_weekly(final_path)
    if set(preliminary) != set(final):
        missing_preliminary = sorted(set(final) - set(preliminary))[:20]
        missing_final = sorted(set(preliminary) - set(final))[:20]
        raise OperationalWeatherError(
            "Bridge inputs have different municipality-week support: "
            f"missing_preliminary={missing_preliminary}, missing_final={missing_final}"
        )
    metrics: dict[str, dict[str, float | int]] = {}
    for column in OUTPUT_VARIABLES:
        differences = np.asarray(
            [preliminary[key][column] - final[key][column] for key in sorted(preliminary)],
            dtype=np.float64,
        )
        metrics[column] = {
            "n": int(len(differences)),
            "mean_signed_difference_preliminary_minus_final": float(np.mean(differences)),
            "mae": float(np.mean(np.abs(differences))),
            "rmse": float(np.sqrt(np.mean(np.square(differences)))),
            "maximum_absolute_difference": float(np.max(np.abs(differences))),
        }
    payload = {
        "schema_version": 1,
        "pipeline": "model_v3.features.weather_operational.bridge",
        "status": config["bridge"]["status_without_thresholds"],
        "promotion_authorized": False,
        "promotion_thresholds": None,
        "comparison_row_count": len(preliminary),
        "preliminary": {
            "path": str(preliminary_path),
            "sha256": sha256_file(preliminary_path),
        },
        "final": {"path": str(final_path), "sha256": sha256_file(final_path)},
        "metrics": metrics,
        "unresolved": [
            "Predeclared bridge tolerances have not been approved.",
            "Prediction-level drift must be evaluated after both vintages are run through the frozen model.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operational ERA5-Land ingestion and features")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Print the deterministic CDS request plan")
    plan.add_argument("--issue-week")
    plan.add_argument("--as-of")

    sync = subparsers.add_parser("sync", help="Download an immutable ERA5-Land retrieval")
    sync.add_argument("--issue-week")
    sync.add_argument("--retrieved-at")

    build = subparsers.add_parser("build", help="Build municipality-week features")
    build.add_argument("--manifest", type=Path, required=True)

    bridge = subparsers.add_parser("bridge", help="Compare preliminary and final features")
    bridge.add_argument("--preliminary", type=Path, required=True)
    bridge.add_argument("--final", type=Path, required=True)
    bridge.add_argument("--output", type=Path, required=True)
    return parser


def _resolve_issue_week(
    config: Mapping[str, Any], issue_week_value: str | None, as_of: datetime
) -> date:
    if issue_week_value:
        return parse_monday(issue_week_value)
    return latest_ready_issue_week(
        as_of, lag_days=int(config["source"]["nominal_availability_lag_days"])
    )


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_config(config_path)
    if args.command == "plan":
        as_of = (
            parse_utc_datetime(args.as_of, label="as_of")
            if args.as_of
            else datetime.now(timezone.utc)
        )
        issue = _resolve_issue_week(config, args.issue_week, as_of)
        window, requests = build_cds_requests(config, issue)
        print(
            json.dumps(
                {
                    "issue_week": issue.isoformat(),
                    "weather_start": window.weather_start.isoformat(),
                    "weather_end": window.weather_end.isoformat(),
                    "source_context_start": window.source_context_start.isoformat(),
                    "nominal_available_through": nominal_available_through(
                        as_of, lag_days=int(config["source"]["nominal_availability_lag_days"])
                    ).isoformat(),
                    "requests": requests,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "sync":
        retrieved_at = (
            parse_utc_datetime(args.retrieved_at, label="retrieved_at")
            if args.retrieved_at
            else datetime.now(timezone.utc)
        )
        issue = _resolve_issue_week(config, args.issue_week, retrieved_at)
        path = sync_operational_weather(
            config, issue_week=issue, retrieved_at=retrieved_at
        )
        print(path)
        return 0
    if args.command == "build":
        manifest = args.manifest if args.manifest.is_absolute() else REPO_ROOT / args.manifest
        weekly, quality = build_operational_weekly_weather(config, manifest)
        print(json.dumps({"weekly_weather": str(weekly), "quality": str(quality)}))
        return 0
    if args.command == "bridge":
        preliminary = args.preliminary if args.preliminary.is_absolute() else REPO_ROOT / args.preliminary
        final = args.final if args.final.is_absolute() else REPO_ROOT / args.final
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        build_bridge_summary(config, preliminary, final, output)
        print(output)
        return 0
    raise OperationalWeatherError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
