from __future__ import annotations

import json
import unittest
from pathlib import Path

from pyproj import Geod

from model_v3.features.static_geography import (
    StaticGeographyError,
    build_feature_rows,
    geodesic_geometry_area_m2,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "static_geography_source.geojson"


class StaticGeographyTests(unittest.TestCase):
    def test_known_wgs84_polygon_area_is_in_square_metres(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [14.0, 45.0],
                    [15.0, 45.0],
                    [15.0, 46.0],
                    [14.0, 46.0],
                    [14.0, 45.0],
                ]
            ],
        }
        area = geodesic_geometry_area_m2(
            geometry, geod=Geod(ellps="WGS84"), context="fixture"
        )

        self.assertEqual(round(area), 8_686_379_302)

    def test_polygon_hole_is_subtracted(self) -> None:
        outer = [
            [14.0, 45.0],
            [15.0, 45.0],
            [15.0, 46.0],
            [14.0, 46.0],
            [14.0, 45.0],
        ]
        hole = [
            [14.2, 45.2],
            [14.4, 45.2],
            [14.4, 45.4],
            [14.2, 45.4],
            [14.2, 45.2],
        ]
        geod = Geod(ellps="WGS84")
        full = geodesic_geometry_area_m2(
            {"type": "Polygon", "coordinates": [outer]},
            geod=geod,
            context="full",
        )
        with_hole = geodesic_geometry_area_m2(
            {"type": "Polygon", "coordinates": [outer, hole]},
            geod=geod,
            context="hole",
        )

        self.assertGreater(with_hole, 0)
        self.assertLess(with_hole, full)

    def test_fixture_codes_match_and_areas_are_positive(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rows, timestamps = build_feature_rows(
            payload,
            canonical_codes={"001", "002"},
            code_property="SIFRA",
            ellipsoid="WGS84",
        )

        self.assertEqual([row["municipality_code"] for row in rows], ["001", "002"])
        self.assertTrue(all(row["municipality_area_km2"] > 0 for row in rows))
        self.assertEqual(len(timestamps), 2)

    def test_missing_geometry_is_rejected_not_imputed(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 1},
                    "geometry": None,
                }
            ],
        }

        with self.assertRaisesRegex(StaticGeographyError, "geometry must be present"):
            build_feature_rows(
                payload,
                canonical_codes={"001"},
                code_property="SIFRA",
                ellipsoid="WGS84",
            )


if __name__ == "__main__":
    unittest.main()
