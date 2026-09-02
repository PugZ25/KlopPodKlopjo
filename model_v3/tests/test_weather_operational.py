from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import xarray as xr

from model_v3.features.weather_operational import (
    DEFAULT_CONFIG_PATH,
    OperationalWeatherError,
    build_bridge_summary,
    build_cds_requests,
    build_operational_weekly_weather,
    latest_ready_issue_week,
    load_config,
    _read_grib_source,
    sha256_file,
    sync_operational_weather,
    weather_window,
)
from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS


class FakeResult:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def download(self, target: str) -> None:
        Path(target).write_bytes(self.payload)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def retrieve(self, dataset: str, request: dict[str, object]) -> FakeResult:
        self.calls.append((dataset, request))
        return FakeResult(json.dumps(request, sort_keys=True).encode("utf-8"))


def write_synthetic_source(path: Path, *, expver: str = "0005") -> None:
    start = datetime(2025, 1, 5, tzinfo=timezone.utc)
    hours = 29 * 24
    times = np.asarray(
        [np.datetime64((start + timedelta(hours=index)).replace(tzinfo=None)) for index in range(hours)]
    )
    latitudes = np.asarray([1.0, 0.0], dtype=np.float64)
    longitudes = np.asarray([0.0, 1.0], dtype=np.float64)
    shape = (hours, 2, 2)
    grid = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)
    repeated_grid = np.broadcast_to(grid, shape).copy()
    precipitation = np.empty(shape, dtype=np.float32)
    for index in range(hours):
        hour = (start + timedelta(hours=index)).hour
        accumulated_hours = 24 if hour == 0 else hour
        precipitation[index] = accumulated_hours * 0.001
    dataset = xr.Dataset(
        data_vars={
            "t2m": (("valid_time", "latitude", "longitude"), 280.0 + repeated_grid, {"units": "K"}),
            "d2m": (("valid_time", "latitude", "longitude"), 275.0 + repeated_grid, {"units": "K"}),
            "tp": (("valid_time", "latitude", "longitude"), precipitation, {"units": "m"}),
            "stl1": (("valid_time", "latitude", "longitude"), 279.0 + repeated_grid, {"units": "K"}),
            "stl2": (("valid_time", "latitude", "longitude"), 278.0 + repeated_grid, {"units": "K"}),
            "swvl1": (("valid_time", "latitude", "longitude"), 0.2 + repeated_grid / 100.0, {"units": "m**3 m**-3"}),
            "swvl2": (("valid_time", "latitude", "longitude"), 0.3 + repeated_grid / 100.0, {"units": "m**3 m**-3"}),
        },
        coords={
            "valid_time": times,
            "latitude": latitudes,
            "longitude": longitudes,
            "expver": ("valid_time", np.asarray([expver] * hours)),
        },
    )
    dataset.to_netcdf(path)


class OperationalWeatherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(DEFAULT_CONFIG_PATH)

    def test_request_plan_includes_precipitation_context_and_four_weeks(self) -> None:
        window, requests = build_cds_requests(self.config, date(2025, 2, 3))

        self.assertEqual(window.weather_start, date(2025, 1, 6))
        self.assertEqual(window.weather_end, date(2025, 2, 2))
        self.assertEqual(window.source_context_start, date(2025, 1, 5))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["request"]["day"][0], "05")
        self.assertEqual(requests[-1]["request"]["day"][-1], "02")
        self.assertEqual(len(requests[0]["request"]["time"]), 24)
        self.assertEqual(requests[0]["request"]["data_format"], "grib")
        self.assertTrue(requests[0]["filename"].endswith(".grib"))

    def test_grib_reader_preserves_expver_and_canonical_variables(self) -> None:
        from eccodes import (
            codes_grib_new_from_samples,
            codes_release,
            codes_set,
            codes_set_values,
            codes_write,
        )

        parameter_ids = (167, 168, 228, 139, 170, 39, 40)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.grib"
            with path.open("wb") as handle:
                for parameter_id in parameter_ids:
                    message = codes_grib_new_from_samples("regular_ll_sfc_grib1")
                    try:
                        for key, value in (
                            ("Ni", 2),
                            ("Nj", 2),
                            ("latitudeOfFirstGridPointInDegrees", 1.0),
                            ("longitudeOfFirstGridPointInDegrees", 0.0),
                            ("latitudeOfLastGridPointInDegrees", 0.0),
                            ("longitudeOfLastGridPointInDegrees", 1.0),
                            ("iDirectionIncrementInDegrees", 1.0),
                            ("jDirectionIncrementInDegrees", 1.0),
                            ("jScansPositively", 0),
                            ("dataDate", 20250105),
                            ("dataTime", 0),
                            ("step", 0),
                            ("paramId", parameter_id),
                            ("experimentVersionNumber", "0005"),
                        ):
                            codes_set(message, key, value)
                        codes_set_values(message, [1.0, 2.0, 3.0, 4.0])
                        codes_write(message, handle)
                    finally:
                        codes_release(message)
            source = _read_grib_source(path)
            self.assertEqual(source.expver, "0005")
            self.assertEqual(tuple(source.values), (
                "t2m", "d2m", "tp", "stl1", "stl2", "swvl1", "swvl2"
            ))
            np.testing.assert_array_equal(source.latitudes, [1.0, 0.0])
            np.testing.assert_array_equal(source.longitudes, [0.0, 1.0])

    def test_latest_ready_issue_week_respects_five_day_latency(self) -> None:
        friday = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
        monday = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)

        self.assertEqual(latest_ready_issue_week(friday, lag_days=5), date(2026, 8, 31))
        self.assertEqual(latest_ready_issue_week(monday, lag_days=5), date(2026, 8, 24))

    def test_sync_is_immutable_and_refuses_not_yet_available_t_minus_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = json.loads(json.dumps(self.config))
            config["outputs"]["retrieval_root"] = str(root / "retrievals")
            client = FakeClient()
            retrieved_at = datetime(2025, 2, 7, 12, tzinfo=timezone.utc)

            manifest = sync_operational_weather(
                config,
                issue_week=date(2025, 2, 3),
                retrieved_at=retrieved_at,
                client=client,
                repo_root=root,
            )

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["requested_weather_end"], "2025-02-02")
            self.assertEqual(len(payload["files"]), 2)
            self.assertEqual(len(client.calls), 2)
            with self.assertRaises(FileExistsError):
                sync_operational_weather(
                    config,
                    issue_week=date(2025, 2, 3),
                    retrieved_at=retrieved_at,
                    client=client,
                    repo_root=root,
                )

            with self.assertRaisesRegex(OperationalWeatherError, "not nominally available"):
                sync_operational_weather(
                    config,
                    issue_week=date(2025, 2, 3),
                    retrieved_at=datetime(2025, 2, 6, 12, tzinfo=timezone.utc),
                    client=client,
                    repo_root=root,
                )

    def test_builder_reuses_frozen_grid_weights_and_produces_complete_weeks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "source.nc"
            write_synthetic_source(raw)
            municipality = root / "municipality.csv"
            municipality.write_text(
                "municipality_code,municipality_name\n001,One\n002,Two\n",
                encoding="utf-8",
            )
            weights = root / "weights.csv"
            weights.write_text(
                "municipality_code,grid_cell_index,latitude,longitude,intersection_area_m2,normalized_intersection_weight\n"
                "001,0,1,0,25,0.25\n"
                "001,1,1,1,75,0.75\n"
                "002,2,0,0,50,0.5\n"
                "002,3,0,1,50,0.5\n",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "retrieval_id": "fixture",
                "retrieved_at_utc": "2025-02-07T12:00:00+00:00",
                "issue_week": "2025-02-03",
                "requested_weather_start": "2025-01-06",
                "requested_weather_end": "2025-02-02",
                "source_context_start": "2025-01-05",
                "dataset": "reanalysis-era5-land",
                "data_format": "netcdf",
                "requests": [],
                "files": [
                    {
                        "path": raw.name,
                        "bytes": raw.stat().st_size,
                        "sha256": sha256_file(raw),
                    }
                ],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            config = json.loads(json.dumps(self.config))
            config["source"]["data_format"] = "netcdf"
            config["spatial_contract"]["weights"] = str(weights)
            config["spatial_contract"]["weights_sha256"] = sha256_file(weights)
            config["spatial_contract"]["municipality"] = str(municipality)
            config["spatial_contract"]["municipality_sha256"] = sha256_file(municipality)

            weekly_path, quality_path = build_operational_weekly_weather(
                config, manifest_path, repo_root=root
            )

            quality = json.loads(quality_path.read_text(encoding="utf-8"))
            self.assertEqual(quality["status"], "pass")
            self.assertEqual(quality["expver"], "0005")
            self.assertEqual(quality["weather_vintage"], "preliminary_era5_land_t")
            self.assertEqual(quality["complete_week_count"], 4)
            self.assertEqual(quality["row_count"], 8)
            with weekly_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(tuple(rows[0]), WEEKLY_COLUMNS)
            self.assertEqual(rows[0]["municipality_code"], "001")
            self.assertAlmostEqual(float(rows[0]["t2m_mean_c"]), 7.6, places=5)
            self.assertAlmostEqual(float(rows[0]["tp_sum_mm"]), 168.0, places=3)

    def test_bridge_is_diagnostic_and_cannot_promote_without_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preliminary = root / "preliminary.csv"
            final = root / "final.csv"
            fieldnames = list(WEEKLY_COLUMNS)
            base = {
                "municipality_code": "001",
                "week_start": "2025-01-06",
                "week_end": "2025-01-12",
                "weather_status": "complete",
                "source_hour_count": "168",
                "minimum_present_hours": "168",
                **{column: "1.0" for column in OUTPUT_VARIABLES},
            }
            with preliminary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(base)
            final_row = dict(base)
            final_row[OUTPUT_VARIABLES[0]] = "0.5"
            with final.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(final_row)

            payload = build_bridge_summary(
                self.config, preliminary, final, root / "bridge.json"
            )

            self.assertFalse(payload["promotion_authorized"])
            self.assertIn("diagnostic_only", payload["status"])
            self.assertAlmostEqual(payload["metrics"][OUTPUT_VARIABLES[0]]["mae"], 0.5)

    def test_non_monday_issue_is_rejected(self) -> None:
        with self.assertRaisesRegex(OperationalWeatherError, "must be a Monday"):
            weather_window(date(2025, 2, 4))


if __name__ == "__main__":
    unittest.main()
