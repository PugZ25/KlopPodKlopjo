from __future__ import annotations

import json
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from pipelines.features.copernicus_obcina_weekly import (
    build_calendar_features,
    compute_axis_edges,
    make_grid_key,
)


def processing_deps_available() -> bool:
    return all(find_spec(name) is not None for name in ("numpy", "pandas", "pyproj", "shapely", "xarray"))


class CopernicusWeeklyHelperTests(unittest.TestCase):
    def test_compute_axis_edges_handles_descending_coordinates(self) -> None:
        edges = compute_axis_edges([46.9, 46.8, 46.7])
        expected = [46.95, 46.85, 46.75, 46.650000000000006]
        for actual_value, expected_value in zip(edges, expected, strict=True):
            self.assertAlmostEqual(actual_value, expected_value, places=10)

    def test_make_grid_key_rounds_to_expected_precision(self) -> None:
        self.assertEqual(make_grid_key(46.91234, 13.31234), "46.9123|13.3123")

    def test_build_calendar_features_uses_iso_week(self) -> None:
        features = build_calendar_features(__import__("datetime").datetime(2026, 3, 30))
        self.assertEqual(features["iso_year"], 2026)
        self.assertEqual(features["iso_week"], 14)
        self.assertEqual(features["month"], 4)


@unittest.skipUnless(processing_deps_available(), "Processing dependencies are not installed.")
class CopernicusWeeklyPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.source_dir = self.temp_path / "hourly"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.geojson_path = self.temp_path / "obcine.geojson"
        self._write_geojson()
        self._write_dataset()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_geojson(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 1, "NAZIV": "Leva"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [13.95, 45.85],
                                [14.05, 45.85],
                                [14.05, 46.05],
                                [13.95, 46.05],
                                [13.95, 45.85],
                            ]
                        ],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 2, "NAZIV": "Desna"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [14.05, 45.85],
                                [14.15, 45.85],
                                [14.15, 46.05],
                                [14.05, 46.05],
                                [14.05, 45.85],
                            ]
                        ],
                    },
                },
            ],
        }
        self.geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_dataset(self) -> None:
        import numpy as np
        import pandas as pd
        import xarray as xr

        times = pd.date_range("2024-01-01", periods=24 * 8, freq="h")
        latitudes = [46.0, 45.9]
        longitudes = [14.0, 14.1]
        shape = (len(times), len(latitudes), len(longitudes))

        air_temperature = np.zeros(shape, dtype=np.float32)
        humidity = np.zeros(shape, dtype=np.float32)
        precipitation = np.zeros(shape, dtype=np.float32)
        soil_temperature_1 = np.zeros(shape, dtype=np.float32)
        soil_temperature_2 = np.zeros(shape, dtype=np.float32)
        soil_water_1 = np.zeros(shape, dtype=np.float32)
        soil_water_2 = np.zeros(shape, dtype=np.float32)

        air_temperature[:, :, 0] = 10.0
        air_temperature[:, :, 1] = 20.0
        humidity[:, :, 0] = 80.0
        humidity[:, :, 1] = 60.0
        precipitation[:, :, 0] = 0.5
        precipitation[:, :, 1] = 1.0
        soil_temperature_1[:, :, 0] = 8.0
        soil_temperature_1[:, :, 1] = 12.0
        soil_temperature_2[:, :, 0] = 7.0
        soil_temperature_2[:, :, 1] = 11.0
        soil_water_1[:, :, 0] = 0.30
        soil_water_1[:, :, 1] = 0.40
        soil_water_2[:, :, 0] = 0.35
        soil_water_2[:, :, 1] = 0.45

        ds = xr.Dataset(
            {
                "air_temperature_c": (("time", "latitude", "longitude"), air_temperature),
                "relative_humidity_pct": (("time", "latitude", "longitude"), humidity),
                "precipitation_hourly_mm": (("time", "latitude", "longitude"), precipitation),
                "soil_temperature_level_1_c": (
                    ("time", "latitude", "longitude"),
                    soil_temperature_1,
                ),
                "soil_temperature_level_2_c": (
                    ("time", "latitude", "longitude"),
                    soil_temperature_2,
                ),
                "soil_water_layer_1_m3_m3": (("time", "latitude", "longitude"), soil_water_1),
                "soil_water_layer_2_m3_m3": (("time", "latitude", "longitude"), soil_water_2),
            },
            coords={
                "time": times,
                "latitude": latitudes,
                "longitude": longitudes,
            },
        )
        ds.to_netcdf(self.source_dir / "era5land_slovenia_features_2024_01.nc")

    def test_area_weighted_pipeline_builds_expected_weekly_features(self) -> None:
        from pipelines.features.copernicus_obcina_weekly import (
            build_obcina_weather_feature_tables,
            build_overlay_table,
        )

        overlay, summary = build_overlay_table(
            self.source_dir / "era5land_slovenia_features_2024_01.nc",
            self.geojson_path,
        )
        self.assertEqual(summary.municipality_count, 2)
        self.assertGreater(summary.coverage_min_pct, 99.99)
        weight_sums = overlay.groupby("obcina_sifra")["cell_weight"].sum().to_dict()
        self.assertAlmostEqual(weight_sums["1"], 1.0, places=6)
        self.assertAlmostEqual(weight_sums["2"], 1.0, places=6)

        tables = build_obcina_weather_feature_tables(
            source_dir=self.source_dir,
            geojson_path=self.geojson_path,
            keep_partial_weeks=False,
        )
        weekly = tables.municipality_weekly.sort_values("obcina_sifra").reset_index(drop=True)

        self.assertEqual(len(weekly), 2)
        left = weekly.iloc[0]
        right = weekly.iloc[1]

        self.assertEqual(left["obcina_naziv"], "Leva")
        self.assertAlmostEqual(left["air_temperature_c_mean"], 10.0, delta=0.01)
        self.assertAlmostEqual(left["precipitation_sum_mm"], 84.0, delta=0.01)
        self.assertAlmostEqual(left["humidity_hours_ge_80_sum"], 168.0, delta=0.01)
        self.assertAlmostEqual(left["tick_activity_window_hours_sum"], 168.0, delta=0.01)
        self.assertAlmostEqual(left["covered_area_pct"], 100.0, delta=0.01)

        self.assertEqual(right["obcina_naziv"], "Desna")
        self.assertAlmostEqual(right["air_temperature_c_mean"], 20.0, delta=0.01)
        self.assertAlmostEqual(right["precipitation_sum_mm"], 168.0, delta=0.01)
        self.assertAlmostEqual(right["humidity_hours_ge_80_sum"], 0.0, delta=0.01)
        self.assertAlmostEqual(right["tick_activity_window_hours_sum"], 0.0, delta=0.01)
        self.assertEqual(right["observation_days_count"], 7)


if __name__ == "__main__":
    unittest.main()
