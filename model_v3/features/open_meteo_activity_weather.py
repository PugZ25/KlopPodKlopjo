from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS
from model_v3.models.weather_ablation import WeeklyWeather
from model_v3.models.non_ml_baselines import parse_code


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    REPO_ROOT / "model_v3" / "config" / "open_meteo_activity_weather.json"
)

EXPECTED_UNITS = {
    "time": "iso8601",
    "temperature_2m": "°C",
    "dew_point_2m": "°C",
    "precipitation": "mm",
    "soil_temperature_6cm": "°C",
    "soil_temperature_18cm": "°C",
    "soil_moisture_3_to_9cm": "m³/m³",
    "soil_moisture_9_to_27cm": "m³/m³",
}

SOURCE_TO_OUTPUT = {
    "temperature_2m": "t2m_mean_c",
    "dew_point_2m": "d2m_mean_c",
    "precipitation": "tp_sum_mm",
    "soil_temperature_6cm": "stl1_mean_c",
    "soil_temperature_18cm": "stl2_mean_c",
    "soil_moisture_3_to_9cm": "swvl1_mean_m3_m3",
    "soil_moisture_9_to_27cm": "swvl2_mean_m3_m3",
}

SUM_OUTPUTS = frozenset({"tp_sum_mm"})

LYME_MODEL_SOURCE_VARIABLES = (
    "temperature_2m",
    "precipitation",
    "soil_temperature_6cm",
)

QUALITY_CHECK_NAMES = frozenset(
    {
        "five_complete_pre_issue_UTC_weeks",
        "period_ends_before_issue_week",
        "no_current_or_future_hours",
        "all_expected_sample_points_present",
        "all_expected_municipalities_present",
        "polygon_intersection_weights_sum_to_one",
        "weather_used_only_by_declared_lyme_model",
        "activity_thresholds_not_created",
        "raw_response_hashes_verified",
    }
)


class ActivityWeatherError(ValueError):
    """Raised when fresh operational weather violates its explicit contract."""


class ActivityWeatherHttpError(ActivityWeatherError):
    """Raised when Open-Meteo rejects a request with an HTTP response."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        super().__init__(f"Open-Meteo returned HTTP {status}: {detail}")


@dataclass(frozen=True, order=True)
class SamplePoint:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WeightRow:
    municipality_code: str
    point: SamplePoint
    weight: float


@dataclass(frozen=True)
class ActivityWeatherPlan:
    as_of_utc: datetime
    signal_issue_week: date
    period_start: date
    period_end: date
    sample_points: tuple[SamplePoint, ...]
    batches: tuple[tuple[SamplePoint, ...], ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_record(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    try:
        label = str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _repo_path(value: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ActivityWeatherError(f"Invalid UTC datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ActivityWeatherError("as_of must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ActivityWeatherError("Activity-weather config must remain in repository")
    config = json.loads(resolved.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ActivityWeatherError("Activity-weather schema_version must equal 1")
    purpose = config.get("purpose", {})
    if purpose.get("used_by_disease_model") is not True:
        raise ActivityWeatherError("Operational weather must remain a declared model input")
    if purpose.get("categorical_activity_thresholds_allowed") is not False:
        raise ActivityWeatherError("Unvalidated tick-activity thresholds are forbidden")
    source = config.get("source", {})
    if source.get("endpoint") != "https://api.open-meteo.com/v1/forecast":
        raise ActivityWeatherError("Open-Meteo endpoint changed")
    if source.get("model") != "icon_seamless":
        raise ActivityWeatherError("Operational source model changed")
    if source.get("hourly_variables") != [key for key in EXPECTED_UNITS if key != "time"]:
        raise ActivityWeatherError("Fresh-weather variable contract changed")
    if source.get("model_feature_weeks") != 4:
        raise ActivityWeatherError("Lyme weather features must use four complete weeks")
    if source.get("retrieval_history_weeks") != 5:
        raise ActivityWeatherError(
            "Operational retrieval must include five weeks for current and previous scores"
        )
    if source.get("lyme_model_input_variables") != list(LYME_MODEL_SOURCE_VARIABLES):
        raise ActivityWeatherError("Operational Lyme weather input variables changed")
    freshness = config.get("freshness_contract", {})
    if freshness.get("partial_current_day_allowed") is not False:
        raise ActivityWeatherError("Partial current day is not allowed")
    if freshness.get("future_hours_allowed") is not False:
        raise ActivityWeatherError("Future hours are not allowed in recent context")
    return config


def read_weights(
    config: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> tuple[list[WeightRow], tuple[SamplePoint, ...]]:
    spatial = config["spatial_contract"]
    path = _repo_path(spatial["weights"], repo_root)
    if not path.is_file() or _sha256(path) != spatial["weights_sha256"]:
        raise ActivityWeatherError("Frozen municipality-grid weights are missing or changed")
    rows: list[WeightRow] = []
    sums: defaultdict[str, float] = defaultdict(float)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "municipality_code",
            "latitude",
            "longitude",
            "normalized_intersection_weight",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise ActivityWeatherError("Frozen weight schema is incomplete")
        for index, source in enumerate(reader, start=1):
            code = parse_code(source["municipality_code"], context=f"weight row {index}")
            try:
                latitude = float(source["latitude"])
                longitude = float(source["longitude"])
                weight = float(source["normalized_intersection_weight"])
            except ValueError as exc:
                raise ActivityWeatherError(f"Invalid numeric weight row {index}") from exc
            if not all(math.isfinite(value) for value in (latitude, longitude, weight)):
                raise ActivityWeatherError("Weight row contains non-finite values")
            if weight <= 0:
                raise ActivityWeatherError("Intersection weights must be positive")
            point = SamplePoint(latitude, longitude)
            rows.append(WeightRow(code, point, weight))
            sums[code] += weight
    if len(rows) != int(spatial["expected_weight_row_count"]):
        raise ActivityWeatherError("Frozen weight row count changed")
    if len(sums) != int(spatial["expected_municipality_count"]):
        raise ActivityWeatherError("Frozen municipality count changed")
    if any(not math.isclose(value, 1.0, rel_tol=0.0, abs_tol=1e-9) for value in sums.values()):
        raise ActivityWeatherError("Municipality weights do not sum to one")
    points = tuple(sorted({row.point for row in rows}))
    if len(points) != int(spatial["expected_unique_sample_point_count"]):
        raise ActivityWeatherError("Frozen unique sample-point count changed")
    return rows, points


def build_plan(
    config: Mapping[str, Any], *, as_of: str | datetime, repo_root: Path = REPO_ROOT
) -> ActivityWeatherPlan:
    as_of_utc = _parse_utc(as_of)
    signal_issue_week = as_of_utc.date() - timedelta(days=as_of_utc.date().weekday())
    history_weeks = int(config["source"]["retrieval_history_weeks"])
    period_start = signal_issue_week - timedelta(weeks=history_weeks)
    period_end = signal_issue_week - timedelta(days=1)
    _, points = read_weights(config, repo_root=repo_root)
    batch_size = int(config["source"]["batch_size"])
    if batch_size < 1 or batch_size > 100:
        raise ActivityWeatherError("Open-Meteo batch_size must be between 1 and 100")
    batches = tuple(
        tuple(points[index : index + batch_size])
        for index in range(0, len(points), batch_size)
    )
    return ActivityWeatherPlan(
        as_of_utc=as_of_utc,
        signal_issue_week=signal_issue_week,
        period_start=period_start,
        period_end=period_end,
        sample_points=points,
        batches=batches,
    )


def _request_url(
    config: Mapping[str, Any], plan: ActivityWeatherPlan, points: Sequence[SamplePoint]
) -> str:
    source = config["source"]
    parameters = {
        "latitude": ",".join(format(point.latitude, ".6f") for point in points),
        "longitude": ",".join(format(point.longitude, ".6f") for point in points),
        "hourly": ",".join(source["hourly_variables"]),
        "start_date": plan.period_start.isoformat(),
        "end_date": plan.period_end.isoformat(),
        "timezone": source["timezone"],
        "models": source["model"],
        "cell_selection": source["cell_selection"],
        "elevation": ",".join(str(source["elevation"]) for _ in points),
    }
    return f"{source['endpoint']}?{urllib.parse.urlencode(parameters)}"


def _default_http_get(url: str, *, timeout: int, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ActivityWeatherHttpError(response.status, "unexpected response")
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace").strip()
        raise ActivityWeatherHttpError(exc.code, detail or "empty response") from exc


def sync_activity_weather(
    config: Mapping[str, Any],
    *,
    as_of: str | datetime,
    http_get: Callable[..., bytes] = _default_http_get,
    repo_root: Path = REPO_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Path:
    plan = build_plan(config, as_of=as_of, repo_root=repo_root)
    source = config["source"]
    retrieval_id = plan.as_of_utc.strftime("retrieved_%Y%m%dT%H%M%SZ")
    root_value = Path(config["outputs"]["retrieval_root"])
    retrieval_root = root_value if root_value.is_absolute() else repo_root / root_value
    retrieval_directory = retrieval_root / retrieval_id
    manifest_path = retrieval_directory / "manifest.json"
    if retrieval_directory.exists():
        if not manifest_path.is_file():
            raise ActivityWeatherError(
                f"Existing retrieval is incomplete and cannot be reused: {retrieval_id}"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_header = {
            "schema_version": 1,
            "pipeline": "model_v3.features.open_meteo_activity_weather",
            "retrieval_id": retrieval_id,
            "retrieved_at_utc": plan.as_of_utc.isoformat(),
            "signal_issue_week": plan.signal_issue_week.isoformat(),
            "period_start": plan.period_start.isoformat(),
            "period_end": plan.period_end.isoformat(),
            "provider": source["provider"],
            "upstream_model_provider": source["upstream_model_provider"],
            "source_model": source["model"],
            "data_status": config["purpose"]["data_status"],
            "sample_point_count": len(plan.sample_points),
        }
        if any(manifest.get(key) != value for key, value in expected_header.items()):
            raise ActivityWeatherError(
                f"Existing retrieval has incompatible provenance: {retrieval_id}"
            )
        if manifest.get("configuration", {}).get("sha256") != _sha256(
            config_path.resolve()
        ):
            raise ActivityWeatherError(
                f"Existing retrieval used a different configuration: {retrieval_id}"
            )
        request_records = manifest.get("requests")
        if not isinstance(request_records, list) or len(request_records) != len(
            plan.batches
        ):
            raise ActivityWeatherError(
                f"Existing retrieval has incomplete request support: {retrieval_id}"
            )
        for batch_index, (points, record) in enumerate(
            zip(plan.batches, request_records, strict=True), start=1
        ):
            if not isinstance(record, dict):
                raise ActivityWeatherError(
                    f"Existing retrieval batch is invalid: {batch_index}"
                )
            expected_points = [
                {"latitude": point.latitude, "longitude": point.longitude}
                for point in points
            ]
            raw_record = record.get("file", {})
            raw_path = retrieval_directory / Path(str(raw_record.get("path", ""))).name
            if (
                record.get("batch_index") != batch_index
                or record.get("url") != _request_url(config, plan, points)
                or record.get("points") != expected_points
                or not raw_path.is_file()
                or raw_record.get("sha256") != _sha256(raw_path)
            ):
                raise ActivityWeatherError(
                    f"Existing retrieval batch cannot be reused: {batch_index}"
                )
        return manifest_path

    retrieval_directory.mkdir(parents=True, exist_ok=False)
    try:
        request_records = []
        for batch_index, points in enumerate(plan.batches, start=1):
            url = _request_url(config, plan, points)
            payload: bytes | None = None
            last_error: Exception | None = None
            for attempt, delay in enumerate((0, 5, 15), start=1):
                if delay:
                    time.sleep(delay)
                try:
                    payload = http_get(
                        url,
                        timeout=int(source["request_timeout_seconds"]),
                        user_agent=source["user_agent"],
                    )
                    break
                except ActivityWeatherHttpError:
                    raise
                except (OSError, urllib.error.URLError, ActivityWeatherError) as exc:
                    last_error = exc
                    if attempt == 3:
                        raise ActivityWeatherError(
                            f"Open-Meteo batch {batch_index} failed after three attempts"
                        ) from exc
            if payload is None:
                raise ActivityWeatherError(
                    "Open-Meteo response is unexpectedly empty"
                ) from last_error
            if len(payload) > int(source["maximum_response_bytes_per_batch"]):
                raise ActivityWeatherError("Open-Meteo batch exceeds configured byte limit")
            try:
                json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ActivityWeatherError("Open-Meteo response is not valid JSON") from exc
            filename = f"batch_{batch_index:02d}.json"
            target = retrieval_directory / filename
            temporary = target.with_suffix(".json.part")
            temporary.write_bytes(payload)
            temporary.replace(target)
            request_records.append(
                {
                    "batch_index": batch_index,
                    "url": url,
                    "points": [
                        {"latitude": point.latitude, "longitude": point.longitude}
                        for point in points
                    ],
                    "file": _path_record(target, repo_root),
                }
            )
        manifest = {
            "schema_version": 1,
            "pipeline": "model_v3.features.open_meteo_activity_weather",
            "retrieval_id": retrieval_id,
            "retrieved_at_utc": plan.as_of_utc.isoformat(),
            "signal_issue_week": plan.signal_issue_week.isoformat(),
            "period_start": plan.period_start.isoformat(),
            "period_end": plan.period_end.isoformat(),
            "provider": source["provider"],
            "upstream_model_provider": source["upstream_model_provider"],
            "source_model": source["model"],
            "data_status": config["purpose"]["data_status"],
            "sample_point_count": len(plan.sample_points),
            "requests": request_records,
            "configuration": _path_record(config_path.resolve(), repo_root),
            "retrieval_code": _path_record(Path(__file__).resolve(), repo_root),
        }
        _write_json(manifest_path, manifest)
        return manifest_path
    except BaseException:
        shutil.rmtree(retrieval_directory)
        raise


def _expected_times(period_start: date, period_end: date) -> list[str]:
    hours = (period_end - period_start).days * 24 + 24
    start = datetime.combine(period_start, datetime.min.time())
    return [(start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M") for index in range(hours)]


def _validate_location_payload(
    payload: Mapping[str, Any],
    *,
    requested: SamplePoint,
    expected_times: Sequence[str],
    maximum_shift: float,
) -> dict[str, list[float]]:
    try:
        returned_latitude = float(payload["latitude"])
        returned_longitude = float(payload["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ActivityWeatherError("Open-Meteo response coordinates are invalid") from exc
    if (
        abs(returned_latitude - requested.latitude) > maximum_shift
        or abs(returned_longitude - requested.longitude) > maximum_shift
    ):
        raise ActivityWeatherError("Open-Meteo returned a grid point too far from request")
    if payload.get("utc_offset_seconds") != 0 or payload.get("timezone") != "GMT":
        raise ActivityWeatherError("Open-Meteo response is not UTC")
    if payload.get("hourly_units") != EXPECTED_UNITS:
        raise ActivityWeatherError("Open-Meteo hourly units changed")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or hourly.get("time") != list(expected_times):
        raise ActivityWeatherError("Open-Meteo hourly time axis is incomplete or changed")
    values: dict[str, list[float]] = {}
    for variable in EXPECTED_UNITS:
        if variable == "time":
            continue
        raw = hourly.get(variable)
        if not isinstance(raw, list) or len(raw) != len(expected_times):
            raise ActivityWeatherError(f"Open-Meteo {variable} support is incomplete")
        try:
            parsed = [float(value) for value in raw]
        except (TypeError, ValueError) as exc:
            raise ActivityWeatherError(f"Open-Meteo {variable} contains invalid data") from exc
        if not all(math.isfinite(value) for value in parsed):
            raise ActivityWeatherError(f"Open-Meteo {variable} contains non-finite data")
        values[variable] = parsed
    if any(value < 0 for value in values["precipitation"]):
        raise ActivityWeatherError("Open-Meteo precipitation is negative")
    for variable in ("soil_moisture_3_to_9cm", "soil_moisture_9_to_27cm"):
        if any(not 0 <= value <= 1 for value in values[variable]):
            raise ActivityWeatherError(
                f"Open-Meteo {variable} is outside physical bounds"
            )
    return values


def build_municipality_weather(
    config: Mapping[str, Any],
    manifest_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[Path, Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("pipeline") != "model_v3.features.open_meteo_activity_weather"
    ):
        raise ActivityWeatherError("Activity-weather manifest schema is invalid")
    if manifest.get("source_model") != config["source"]["model"]:
        raise ActivityWeatherError("Manifest source model differs from config")
    if (
        manifest.get("provider") != config["source"]["provider"]
        or manifest.get("upstream_model_provider")
        != config["source"]["upstream_model_provider"]
        or manifest.get("data_status") != config["purpose"]["data_status"]
    ):
        raise ActivityWeatherError("Manifest source provenance differs from config")
    configuration_record = manifest.get("configuration", {})
    if configuration_record.get("sha256") != _sha256(config_path.resolve()):
        raise ActivityWeatherError("Manifest configuration hash differs from current config")
    retrieved_at = _parse_utc(manifest["retrieved_at_utc"])
    period_start = date.fromisoformat(manifest["period_start"])
    period_end = date.fromisoformat(manifest["period_end"])
    issue_week = date.fromisoformat(manifest["signal_issue_week"])
    expected_weeks = int(config["source"]["retrieval_history_weeks"])
    if (
        period_start != issue_week - timedelta(weeks=expected_weeks)
        or period_end != issue_week - timedelta(days=1)
        or period_start.weekday() != 0
        or period_end.weekday() != 6
    ):
        raise ActivityWeatherError(
            "Manifest does not contain the required complete pre-issue weeks"
        )
    expected_days = expected_weeks * 7
    expected_times = _expected_times(period_start, period_end)
    if len(expected_times) != expected_days * 24:
        raise ActivityWeatherError("Expected hourly support changed")
    weights, points = read_weights(config, repo_root=repo_root)
    derived_directory = manifest_path.parent / "derived"
    output_path = derived_directory / config["outputs"]["municipality_weekly_weather"]
    quality_path = derived_directory / config["outputs"]["quality_summary"]
    if derived_directory.exists():
        if not output_path.is_file() or not quality_path.is_file():
            raise ActivityWeatherError("Existing derived weather is incomplete")
        existing_quality = json.loads(quality_path.read_text(encoding="utf-8"))
        existing_inputs = existing_quality.get("inputs", {})
        existing_dataset = existing_quality.get("municipality_dataset", {})
        existing_checks = existing_quality.get("checks", {})
        if (
            existing_quality.get("schema_version") != 1
            or existing_quality.get("pipeline")
            != "model_v3.features.open_meteo_activity_weather"
            or existing_quality.get("status") != "pass"
            or existing_quality.get("retrieval_id") != manifest.get("retrieval_id")
            or existing_quality.get("period_start") != period_start.isoformat()
            or existing_quality.get("period_end") != period_end.isoformat()
            or set(existing_checks) != QUALITY_CHECK_NAMES
            or not all(existing_checks.values())
            or existing_dataset.get("sha256") != _sha256(output_path)
            or existing_inputs.get("manifest", {}).get("sha256")
            != _sha256(manifest_path)
            or existing_inputs.get("weights", {}).get("sha256")
            != _sha256(_repo_path(config["spatial_contract"]["weights"], repo_root))
            or existing_inputs.get("configuration", {}).get("sha256")
            != _sha256(config_path.resolve())
            or existing_inputs.get("pipeline_code", {}).get("sha256")
            != _sha256(Path(__file__).resolve())
        ):
            raise ActivityWeatherError("Existing derived weather cannot be safely reused")
        return output_path, quality_path
    summaries: dict[SamplePoint, dict[str, list[float]]] = {}
    requests = manifest.get("requests")
    if not isinstance(requests, list):
        raise ActivityWeatherError("Manifest requests are invalid")
    for request_record in requests:
        point_records = request_record.get("points")
        file_record = request_record.get("file", {})
        if not isinstance(point_records, list) or not isinstance(file_record, dict):
            raise ActivityWeatherError("Manifest request record is invalid")
        raw_path = manifest_path.parent / Path(file_record["path"]).name
        if not raw_path.is_file() or _sha256(raw_path) != file_record.get("sha256"):
            raise ActivityWeatherError("Raw Open-Meteo response hash mismatch")
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        locations = payload if isinstance(payload, list) else [payload]
        if len(locations) != len(point_records):
            raise ActivityWeatherError("Open-Meteo location count differs from request")
        for source_point, location_payload in zip(point_records, locations, strict=True):
            point = SamplePoint(float(source_point["latitude"]), float(source_point["longitude"]))
            if point in summaries:
                raise ActivityWeatherError(f"Duplicate Open-Meteo sample point: {point}")
            if not isinstance(location_payload, dict):
                raise ActivityWeatherError("Open-Meteo location payload is not an object")
            summaries[point] = _validate_location_payload(
                location_payload,
                requested=point,
                expected_times=expected_times,
                maximum_shift=float(
                    config["spatial_contract"]["maximum_returned_coordinate_shift_degrees"]
                ),
            )
    if set(summaries) != set(points):
        raise ActivityWeatherError("Open-Meteo sample-point support is incomplete")
    grouped: defaultdict[str, list[WeightRow]] = defaultdict(list)
    for row in weights:
        grouped[row.municipality_code].append(row)
    output_rows: list[dict[str, Any]] = []
    for code in sorted(grouped):
        municipality_weights = grouped[code]
        for week_index in range(expected_weeks):
            week_start = period_start + timedelta(weeks=week_index)
            week_end = week_start + timedelta(days=6)
            start_index = week_index * 168
            stop_index = start_index + 168
            values: dict[str, float] = {}
            for source_variable, output in SOURCE_TO_OUTPUT.items():
                point_values = {
                    row.point: summaries[row.point][source_variable][start_index:stop_index]
                    for row in municipality_weights
                }
                if any(len(value) != 168 for value in point_values.values()):
                    raise ActivityWeatherError("Open-Meteo weekly slice is incomplete")
                if output in SUM_OUTPUTS:
                    values[output] = sum(
                        row.weight * sum(point_values[row.point])
                        for row in municipality_weights
                    )
                else:
                    values[output] = sum(
                        row.weight * (sum(point_values[row.point]) / 168.0)
                        for row in municipality_weights
                    )
            output_rows.append(
                {
                    "municipality_code": code,
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "weather_status": "complete",
                    "source_hour_count": 168,
                    **values,
                }
            )
    derived_directory.mkdir(parents=True, exist_ok=False)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WEEKLY_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)
    quality = {
        "schema_version": 1,
        "pipeline": "model_v3.features.open_meteo_activity_weather",
        "status": "pass",
        "retrieval_id": manifest["retrieval_id"],
        "retrieved_at_utc": retrieved_at.isoformat(),
        "signal_issue_week": manifest["signal_issue_week"],
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "feature_window": {
            "current_issue_week": issue_week.isoformat(),
            "model_feature_weeks": int(config["source"]["model_feature_weeks"]),
            "retrieval_history_weeks": expected_weeks,
            "previous_score_supported": True,
        },
        "source": {
            "provider": manifest["provider"],
            "upstream_model_provider": manifest["upstream_model_provider"],
            "model": manifest["source_model"],
            "data_status": manifest["data_status"],
        },
        "spatial": {
            "method": config["spatial_contract"]["aggregation"],
            "not_claimed": config["spatial_contract"]["not_claimed"],
            "municipality_count": len(grouped),
            "weight_row_count": len(weights),
            "unique_sample_point_count": len(points),
        },
        "hour_count_per_point": len(expected_times),
        "request_batch_count": len(requests),
        "municipality_dataset": {
            **_path_record(output_path, repo_root),
            "columns": list(WEEKLY_COLUMNS),
            "primary_key": ["municipality_code", "week_start"],
            "row_count": len(output_rows),
        },
        "inputs": {
            "manifest": _path_record(manifest_path, repo_root),
            "weights": _path_record(
                _repo_path(config["spatial_contract"]["weights"], repo_root), repo_root
            ),
            "configuration": _path_record(config_path.resolve(), repo_root),
            "pipeline_code": _path_record(Path(__file__).resolve(), repo_root),
        },
        "checks": {
            "five_complete_pre_issue_UTC_weeks": expected_weeks == 5,
            "period_ends_before_issue_week": period_end == issue_week - timedelta(days=1),
            "no_current_or_future_hours": True,
            "all_expected_sample_points_present": len(summaries)
            == int(config["spatial_contract"]["expected_unique_sample_point_count"]),
            "all_expected_municipalities_present": len(grouped)
            == int(config["spatial_contract"]["expected_municipality_count"]),
            "polygon_intersection_weights_sum_to_one": True,
            "weather_used_only_by_declared_lyme_model": config["purpose"][
                "used_by_disease_model"
            ]
            is True,
            "activity_thresholds_not_created": True,
            "raw_response_hashes_verified": True,
        },
    }
    if not all(quality["checks"].values()):
        raise ActivityWeatherError("One or more activity-weather quality checks failed")
    _write_json(quality_path, quality)
    return output_path, quality_path


def read_municipality_weather(
    municipality_weather_path: Path,
    quality_path: Path,
    *,
    issue_week: date,
    municipality_codes: set[str],
) -> tuple[dict[tuple[str, date], WeeklyWeather], dict[str, Any]]:
    """Read verified Open-Meteo weeks mapped to the ERA5-Land feature schema."""
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    checks = quality.get("checks", {})
    if (
        quality.get("schema_version") != 1
        or quality.get("pipeline")
        != "model_v3.features.open_meteo_activity_weather"
        or quality.get("status") != "pass"
        or set(checks) != QUALITY_CHECK_NAMES
        or not all(checks.values())
    ):
        raise ActivityWeatherError("Activity-weather quality contract is invalid")
    if quality.get("signal_issue_week") != issue_week.isoformat():
        raise ActivityWeatherError("Activity weather belongs to a different signal week")
    dataset = quality.get("municipality_dataset", {})
    if dataset.get("sha256") != _sha256(municipality_weather_path):
        raise ActivityWeatherError("Municipality activity-weather hash mismatch")
    if tuple(dataset.get("columns", ())) != WEEKLY_COLUMNS:
        raise ActivityWeatherError("Municipality activity-weather schema changed")
    period_start = date.fromisoformat(quality["period_start"])
    period_end = date.fromisoformat(quality["period_end"])
    expected_starts = [issue_week - timedelta(weeks=lag) for lag in (5, 4, 3, 2, 1)]
    if period_start != expected_starts[0] or period_end != issue_week - timedelta(days=1):
        raise ActivityWeatherError("Activity weather does not cover five complete weeks")

    rows: dict[tuple[str, date], WeeklyWeather] = {}
    with municipality_weather_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != WEEKLY_COLUMNS:
            raise ActivityWeatherError("Municipality activity-weather CSV schema changed")
        for index, source in enumerate(reader, start=1):
            code = parse_code(
                source["municipality_code"], context=f"activity-weather row {index}"
            )
            week_start = date.fromisoformat(source["week_start"])
            week_end = date.fromisoformat(source["week_end"])
            key = (code, week_start)
            if key in rows:
                raise ActivityWeatherError(f"Duplicate municipality activity weather: {key}")
            if (
                week_start not in expected_starts
                or week_end != week_start + timedelta(days=6)
                or source["weather_status"] != "complete"
                or source["source_hour_count"] != "168"
            ):
                raise ActivityWeatherError("Municipality activity-weather row contract changed")
            try:
                values = {column: float(source[column]) for column in OUTPUT_VARIABLES}
            except (TypeError, ValueError) as exc:
                raise ActivityWeatherError("Municipality activity weather is non-numeric") from exc
            if not all(math.isfinite(value) for value in values.values()):
                raise ActivityWeatherError("Municipality activity weather is non-finite")
            if values["tp_sum_mm"] < 0 or not (
                0 <= values["swvl1_mean_m3_m3"] <= 1
                and 0 <= values["swvl2_mean_m3_m3"] <= 1
            ):
                raise ActivityWeatherError("Municipality activity weather is physically invalid")
            rows[key] = WeeklyWeather(
                municipality_code=code,
                week_start=week_start,
                week_end=week_end,
                status="complete",
                values=values,
            )
    expected_keys = {
        (code, week_start) for code in municipality_codes for week_start in expected_starts
    }
    if set(rows) != expected_keys:
        raise ActivityWeatherError("Municipality activity-weather coverage differs")
    return rows, quality


def _plan_payload(plan: ActivityWeatherPlan) -> dict[str, Any]:
    return {
        "as_of_utc": plan.as_of_utc.isoformat(),
        "signal_issue_week": plan.signal_issue_week.isoformat(),
        "period_start": plan.period_start.isoformat(),
        "period_end": plan.period_end.isoformat(),
        "complete_day_count": (plan.period_end - plan.period_start).days + 1,
        "complete_week_count": (plan.period_end - plan.period_start).days // 7 + 1,
        "sample_point_count": len(plan.sample_points),
        "request_batch_count": len(plan.batches),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build polygon-weighted weekly Open-Meteo model features"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--as-of")
    sync = subparsers.add_parser("sync")
    sync.add_argument("--as-of")
    build = subparsers.add_parser("build")
    build.add_argument("--manifest", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.command in {"plan", "sync"}:
        as_of = _parse_utc(args.as_of) if args.as_of else datetime.now(timezone.utc)
        if args.command == "plan":
            print(json.dumps(_plan_payload(build_plan(config, as_of=as_of)), indent=2))
            return 0
        manifest = sync_activity_weather(config, as_of=as_of, config_path=config_path)
        print(manifest)
        return 0
    manifest_path = args.manifest.resolve()
    output, quality = build_municipality_weather(
        config, manifest_path, config_path=config_path
    )
    print(json.dumps({"municipality_weather": str(output), "quality": str(quality)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
