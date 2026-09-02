from __future__ import annotations

import csv
import json
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from model_v3.features.open_meteo_activity_weather import (
    ActivityWeatherError,
    ActivityWeatherHttpError,
    EXPECTED_UNITS,
    build_municipality_weather,
    build_plan,
    load_config,
    read_municipality_weather,
    sync_activity_weather,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "model_v3/config/open_meteo_activity_weather.json"


def _config_for(tmp_path: Path) -> dict[str, object]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["outputs"]["retrieval_root"] = str(tmp_path / "retrievals")
    return config


def _fake_http_get(url: str, **_: object) -> bytes:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    latitudes = [float(value) for value in query["latitude"][0].split(",")]
    longitudes = [float(value) for value in query["longitude"][0].split(",")]
    elevations = query["elevation"][0].split(",")
    assert elevations == ["nan"] * len(latitudes)
    start = date.fromisoformat(query["start_date"][0])
    end = date.fromisoformat(query["end_date"][0])
    hour_count = ((end - start).days + 1) * 24
    start_datetime = datetime.combine(start, datetime.min.time())
    times = [
        (start_datetime + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M")
        for index in range(hour_count)
    ]
    locations = []
    for latitude, longitude in zip(latitudes, longitudes, strict=True):
        locations.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "utc_offset_seconds": 0,
                "timezone": "GMT",
                "hourly_units": EXPECTED_UNITS,
                "hourly": {
                    "time": times,
                    "temperature_2m": [11.5] * hour_count,
                    "precipitation": [0.25] * hour_count,
                    "soil_temperature_6cm": [9.25] * hour_count,
                    "soil_moisture_3_to_9cm": [0.31] * hour_count,
                },
            }
        )
    return json.dumps(locations).encode("utf-8")


def test_plan_uses_latest_seven_complete_days_and_current_monday() -> None:
    config = load_config(CONFIG_PATH)
    plan = build_plan(config, as_of="2026-09-01T12:00:00Z")

    assert plan.signal_issue_week == date(2026, 8, 31)
    assert plan.period_start == date(2026, 8, 25)
    assert plan.period_end == date(2026, 8, 31)
    assert len(plan.sample_points) == 298
    assert len(plan.batches) == 6

    next_day = build_plan(config, as_of="2026-09-02T12:00:00Z")
    assert next_day.signal_issue_week == date(2026, 8, 31)
    assert next_day.period_start == date(2026, 8, 26)
    assert next_day.period_end == date(2026, 9, 1)


def test_config_forbids_model_use_and_activity_thresholds() -> None:
    config = load_config(CONFIG_PATH)

    assert config["purpose"]["used_by_disease_model"] is False
    assert config["purpose"]["categorical_activity_thresholds_allowed"] is False
    assert config["purpose"]["personal_risk_interpretation_allowed"] is False
    assert config["spatial_contract"]["not_claimed"] == (
        "not_native_model_grid_polygon_integration"
    )


def test_sync_build_and_verified_reader_cover_every_municipality(tmp_path: Path) -> None:
    config = _config_for(tmp_path)
    manifest = sync_activity_weather(
        config,
        as_of="2026-09-01T12:00:00Z",
        http_get=_fake_http_get,
    )
    municipality_weather, quality_path = build_municipality_weather(config, manifest)

    with municipality_weather.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    municipality_codes = {row["municipality_code"] for row in csv_rows}
    rows, quality = read_municipality_weather(
        municipality_weather,
        quality_path,
        issue_week=date(2026, 8, 31),
        municipality_codes=municipality_codes,
    )

    assert len(rows) == 212
    assert rows["001"]["temperature_2m_mean_c"] == pytest.approx(11.5)
    assert rows["001"]["precipitation_sum_mm"] == pytest.approx(42.0)
    assert rows["001"]["soil_temperature_6cm_mean_c"] == pytest.approx(9.25)
    assert rows["001"]["soil_moisture_3_to_9cm_mean_m3_m3"] == pytest.approx(0.31)
    assert quality["period_start"] == "2026-08-25"
    assert quality["period_end"] == "2026-08-31"
    assert quality["spatial"]["municipality_count"] == 212
    assert quality["spatial"]["unique_sample_point_count"] == 298

    def unexpected_http_get(url: str, **kwargs: object) -> bytes:
        raise AssertionError(f"completed retrieval unexpectedly downloaded again: {url}")

    reused_manifest = sync_activity_weather(
        config,
        as_of="2026-09-01T12:00:00Z",
        http_get=unexpected_http_get,
    )
    reused_weather, reused_quality = build_municipality_weather(
        config, reused_manifest
    )
    assert reused_manifest == manifest
    assert reused_weather == municipality_weather
    assert reused_quality == quality_path


def test_build_rejects_incomplete_hourly_response(tmp_path: Path) -> None:
    config = _config_for(tmp_path)

    def incomplete_http_get(url: str, **kwargs: object) -> bytes:
        payload = json.loads(_fake_http_get(url, **kwargs))
        payload[0]["hourly"]["precipitation"].pop()
        return json.dumps(payload).encode("utf-8")

    manifest = sync_activity_weather(
        config,
        as_of="2026-09-01T12:00:00Z",
        http_get=incomplete_http_get,
    )
    with pytest.raises(ActivityWeatherError, match="precipitation support is incomplete"):
        build_municipality_weather(config, manifest)


def test_failed_sync_removes_only_its_incomplete_retrieval(tmp_path: Path) -> None:
    config = _config_for(tmp_path)

    def rejected_http_get(url: str, **_: object) -> bytes:
        raise ActivityWeatherHttpError(429, f"test rejection for {url}")

    with pytest.raises(ActivityWeatherHttpError, match="HTTP 429"):
        sync_activity_weather(
            config,
            as_of="2026-09-01T12:00:00Z",
            http_get=rejected_http_get,
        )

    retrieval = tmp_path / "retrievals/retrieved_20260901T120000Z"
    assert not retrieval.exists()
