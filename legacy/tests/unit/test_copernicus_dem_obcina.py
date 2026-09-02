from __future__ import annotations

import json
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from pipelines.features.copernicus_dem_obcina import (
    PIXEL_ASSIGNMENT_METHOD,
    build_obcina_dem_feature_tables,
)


def processing_deps_available() -> bool:
    return all(find_spec(name) is not None for name in ("numpy", "pandas", "pyproj", "shapely", "PIL"))


@unittest.skipUnless(processing_deps_available(), "Processing dependencies are not installed.")
class CopernicusDemObcinaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.dem_dir = self.temp_path / "copernicus_dem_slovenia"
        self.tiles_dir = self.dem_dir / "tiles"
        self.tiles_dir.mkdir(parents=True, exist_ok=True)
        self.geojson_path = self.temp_path / "obcine.geojson"
        self._write_tile_and_manifest()
        self._write_geojson()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_tile_and_manifest(self) -> None:
        import numpy as np
        from PIL import Image

        tile_array = np.array(
            [
                [100.0, 200.0],
                [300.0, 400.0],
            ],
            dtype=np.float32,
        )
        Image.fromarray(tile_array, mode="F").save(self.tiles_dir / "tile_01_01.tif")

        manifest = {
            "dem_instance": "COPERNICUS_30",
            "heights": "orthometric",
            "output_epsg": 3794,
            "resolution_m": 30.0,
            "tiles": [
                {
                    "row": 1,
                    "col": 1,
                    "width_px": 2,
                    "height_px": 2,
                    "bbox_projected": [400000.0, 100000.0, 400060.0, 100060.0],
                    "filename": "tile_01_01.tif",
                }
            ],
        }
        (self.dem_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def _write_geojson(self) -> None:
        from pyproj import Transformer

        inverse = Transformer.from_crs("EPSG:3794", "EPSG:4326", always_xy=True)

        def projected_box_to_geojson(west: float, south: float, east: float, north: float) -> list[list[list[float]]]:
            ring_projected = [
                (west, south),
                (east, south),
                (east, north),
                (west, north),
                (west, south),
            ]
            ring_wgs84 = [[*inverse.transform(x, y)] for x, y in ring_projected]
            return [ring_wgs84]

        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 1, "NAZIV": "Leva"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": projected_box_to_geojson(
                            400000.0,
                            100000.0,
                            400030.0,
                            100060.0,
                        ),
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 2, "NAZIV": "Desna"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": projected_box_to_geojson(
                            400030.0,
                            100000.0,
                            400060.0,
                            100060.0,
                        ),
                    },
                },
            ],
        }
        self.geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_pipeline_builds_expected_municipality_dem_features(self) -> None:
        tables = build_obcina_dem_feature_tables(
            dem_dir=self.dem_dir,
            geojson_path=self.geojson_path,
        )

        coverage = tables.tile_coverage.sort_values(["obcina_sifra", "tile_row", "tile_col"]).reset_index(drop=True)
        summary = tables.municipality_features.sort_values("obcina_sifra").reset_index(drop=True)

        self.assertEqual(len(coverage), 2)
        self.assertEqual(len(summary), 2)

        left = summary.iloc[0]
        right = summary.iloc[1]

        self.assertEqual(left["obcina_naziv"], "Leva")
        self.assertEqual(left["pixel_count"], 2)
        self.assertEqual(left["tile_count"], 1)
        self.assertEqual(left["assignment_method"], PIXEL_ASSIGNMENT_METHOD)
        self.assertAlmostEqual(left["elevation_m_mean"], 200.0, places=6)
        self.assertAlmostEqual(left["elevation_m_std"], 100.0, places=6)
        self.assertAlmostEqual(left["elevation_m_min"], 100.0, places=6)
        self.assertAlmostEqual(left["elevation_m_max"], 300.0, places=6)
        self.assertAlmostEqual(left["covered_area_pct_estimate"], 100.0, places=6)

        self.assertEqual(right["obcina_naziv"], "Desna")
        self.assertAlmostEqual(right["elevation_m_mean"], 300.0, places=6)
        self.assertAlmostEqual(right["elevation_m_min"], 200.0, places=6)
        self.assertAlmostEqual(right["elevation_m_max"], 400.0, places=6)
        self.assertAlmostEqual(right["covered_area_pct_estimate"], 100.0, places=6)

        self.assertEqual(tables.manifest["municipality_feature_row_count"], 2)
        self.assertEqual(tables.manifest["tile_coverage_row_count"], 2)


if __name__ == "__main__":
    unittest.main()
