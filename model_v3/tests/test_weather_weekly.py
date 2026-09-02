from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from model_v3.features.weather_weekly import (
    WeatherWeeklyError,
    build_spatial_weights,
    coordinate_edges,
    deaccumulate_precipitation,
    monday_week_start,
    spatial_weighted_mean,
)


class WeatherWeeklyTests(unittest.TestCase):
    def test_coordinate_edges_preserve_increasing_and_decreasing_grids(self) -> None:
        np.testing.assert_allclose(
            coordinate_edges(np.array([0.0, 1.0, 2.0])),
            [-0.5, 0.5, 1.5, 2.5],
        )
        np.testing.assert_allclose(
            coordinate_edges(np.array([2.0, 1.0, 0.0])),
            [2.5, 1.5, 0.5, -0.5],
        )

    def test_week_start_is_monday_for_utc_hour(self) -> None:
        self.assertEqual(
            monday_week_start(datetime(2024, 8, 11, 23, tzinfo=timezone.utc)),
            datetime(2024, 8, 5).date(),
        )

    def test_precipitation_deaccumulation_resets_at_hour_one(self) -> None:
        times = [
            datetime(2020, 1, 2, hour, tzinfo=timezone.utc)
            for hour in (0, 1, 2)
        ]
        accumulated = np.array([[0.005], [0.001], [0.003]], dtype=np.float32)
        hourly, previous, previous_time, corrections, _ = deaccumulate_precipitation(
            accumulated,
            times,
            previous_accumulated=np.array([0.003], dtype=np.float32),
            previous_time=times[0] - timedelta(hours=1),
        )

        np.testing.assert_allclose(hourly[:, 0], [0.002, 0.001, 0.002], atol=1e-9)
        np.testing.assert_allclose(previous, [0.003])
        self.assertEqual(previous_time, times[-1])
        self.assertEqual(corrections, 0)

    def test_only_float32_roundoff_negative_precipitation_is_clamped(self) -> None:
        times = [
            datetime(2020, 1, 2, 2, tzinfo=timezone.utc),
            datetime(2020, 1, 2, 3, tzinfo=timezone.utc),
        ]
        accumulated = np.array([[0.003], [0.003 - 1e-8]], dtype=np.float32)
        hourly, *_rest, corrections, minimum = deaccumulate_precipitation(
            accumulated,
            times,
            previous_accumulated=np.array([0.001], dtype=np.float32),
            previous_time=times[0] - timedelta(hours=1),
        )
        self.assertEqual(hourly[1, 0], 0.0)
        self.assertEqual(corrections, 1)
        self.assertLess(minimum, 0.0)

        with self.assertRaisesRegex(WeatherWeeklyError, "non-roundoff negative"):
            deaccumulate_precipitation(
                np.array([[0.003], [0.001]], dtype=np.float32),
                times,
                previous_accumulated=np.array([0.001], dtype=np.float32),
                previous_time=times[0] - timedelta(hours=1),
            )

    def test_fixed_municipality_intersection_weights_sum_to_one(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"SIFRA": "001"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[-0.4, -0.4], [0.4, -0.4], [0.4, 0.4], [-0.4, 0.4], [-0.4, -0.4]]
                        ],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"SIFRA": "002"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[0.6, -0.4], [1.4, -0.4], [1.4, 0.4], [0.6, 0.4], [0.6, -0.4]]
                        ],
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "municipalities.geojson"
            path.write_text(json.dumps(payload), encoding="utf-8")
            weights, rows, coverage = build_spatial_weights(
                path,
                codes=["001", "002"],
                latitudes=np.array([0.0, 1.0]),
                longitudes=np.array([0.0, 1.0]),
                code_property="SIFRA",
                area_crs="EPSG:3857",
            )

        np.testing.assert_allclose(weights.sum(axis=1), [[1.0], [1.0]])
        self.assertTrue(rows)
        self.assertEqual(set(coverage), {"001", "002"})

    def test_source_wide_missing_hour_remains_missing(self) -> None:
        weights = np.array([[0.5, 0.5]])
        from scipy import sparse

        result = spatial_weighted_mean(
            np.array([[np.nan, np.nan], [1.0, 3.0]]),
            sparse.csr_matrix(weights),
        )

        self.assertTrue(np.isnan(result[0, 0]))
        self.assertEqual(result[1, 0], 2.0)


if __name__ == "__main__":
    unittest.main()
