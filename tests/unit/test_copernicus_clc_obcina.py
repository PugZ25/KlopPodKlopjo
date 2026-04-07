from __future__ import annotations

import json
import struct
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from pipelines.features.copernicus_clc_obcina import (
    PIXEL_ASSIGNMENT_METHOD,
    build_obcina_clc_feature_tables,
)


def processing_deps_available() -> bool:
    return all(find_spec(name) is not None for name in ("numpy", "pandas", "pyproj", "shapely", "PIL"))


def _dbf_field(name: str, field_type: str, field_length: int, decimal_count: int = 0) -> bytes:
    descriptor = bytearray(32)
    encoded_name = name.encode("ascii")
    descriptor[: len(encoded_name)] = encoded_name
    descriptor[11] = ord(field_type)
    descriptor[16] = field_length
    descriptor[17] = decimal_count
    return bytes(descriptor)


def _dbf_record(fields: list[tuple[str, str, int, int]], values: dict[str, object]) -> bytes:
    record = bytearray(b" ")
    for name, field_type, field_length, decimal_count in fields:
        raw_value = values[name]
        if field_type == "N":
            text = f"{int(raw_value):>{field_length}d}"
        elif field_type == "C":
            text = str(raw_value)[:field_length].ljust(field_length)
        else:
            raise ValueError(f"Unsupported test field type: {field_type}")
        record.extend(text.encode("cp1252"))
    return bytes(record)


@unittest.skipUnless(processing_deps_available(), "Processing dependencies are not installed.")
class CopernicusClcObcinaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.raster_dir = self.temp_path / "clc"
        self.raster_dir.mkdir(parents=True, exist_ok=True)
        self.raster_path = self.raster_dir / "test_clc.tif"
        self.geojson_path = self.temp_path / "obcine.geojson"
        self._write_raster_and_vat()
        self._write_geojson()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_raster_and_vat(self) -> None:
        import numpy as np
        from PIL import Image

        raster = np.array(
            [
                [1, 3],
                [2, 1],
            ],
            dtype=np.uint8,
        )
        Image.fromarray(raster, mode="L").save(self.raster_path)
        self.raster_path.with_suffix(".tfw").write_text(
            "\n".join(
                [
                    "100.0",
                    "0.0",
                    "0.0",
                    "-100.0",
                    "400050.0",
                    "100150.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        fields = [
            ("Value", "N", 10, 0),
            ("LABEL3", "C", 50, 0),
            ("CODE_18", "C", 3, 0),
        ]
        descriptors = b"".join(
            _dbf_field(name, field_type, field_length, decimal_count)
            for name, field_type, field_length, decimal_count in fields
        )
        header_length = 32 + len(fields) * 32 + 1
        record_length = 1 + sum(field_length for _, _, field_length, _ in fields)
        header = struct.pack(
            "<BBBBIHH20x",
            0x03,
            126,
            4,
            7,
            3,
            header_length,
            record_length,
        )
        records = [
            {"Value": 1, "LABEL3": "Broad-leaved forest", "CODE_18": "311"},
            {"Value": 2, "LABEL3": "Pastures", "CODE_18": "231"},
            {"Value": 3, "LABEL3": "Transitional woodland-shrub", "CODE_18": "324"},
        ]
        body = b"".join(_dbf_record(fields, record) for record in records)
        vat_path = self.raster_dir / "test_clc.tif.vat.dbf"
        vat_path.write_bytes(header + descriptors + b"\r" + body + b"\x1A")

    def _write_geojson(self) -> None:
        from pyproj import Transformer

        inverse = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)

        def projected_box_to_geojson(
            west: float,
            south: float,
            east: float,
            north: float,
        ) -> list[list[list[float]]]:
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
                            400100.0,
                            100200.0,
                        ),
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"SIFRA": 2, "NAZIV": "Desna"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": projected_box_to_geojson(
                            400100.0,
                            100000.0,
                            400200.0,
                            100200.0,
                        ),
                    },
                },
            ],
        }
        self.geojson_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_pipeline_builds_expected_municipality_clc_features(self) -> None:
        tables = build_obcina_clc_feature_tables(
            raster_path=self.raster_path,
            geojson_path=self.geojson_path,
        )

        sampling = tables.sampling.sort_values("obcina_sifra").reset_index(drop=True)
        summary = tables.municipality_features.sort_values("obcina_sifra").reset_index(drop=True)

        self.assertEqual(len(sampling), 2)
        self.assertEqual(len(summary), 2)

        left = summary.iloc[0]
        right = summary.iloc[1]

        self.assertEqual(left["obcina_naziv"], "Leva")
        self.assertEqual(left["pixel_count"], 2)
        self.assertEqual(left["assignment_method"], PIXEL_ASSIGNMENT_METHOD)
        self.assertAlmostEqual(left["covered_area_pct_estimate"], 100.0, places=6)
        self.assertEqual(left["dominant_clc_code"], 231)
        self.assertAlmostEqual(left["forest_cover_pct"], 50.0, places=6)
        self.assertAlmostEqual(left["broad_leaved_forest_cover_pct"], 50.0, places=6)
        self.assertAlmostEqual(left["grassland_pasture_cover_pct"], 50.0, places=6)
        self.assertAlmostEqual(left["shrub_transitional_cover_pct"], 0.0, places=6)

        self.assertEqual(right["obcina_naziv"], "Desna")
        self.assertEqual(right["dominant_clc_code"], 311)
        self.assertAlmostEqual(right["forest_cover_pct"], 50.0, places=6)
        self.assertAlmostEqual(right["broad_leaved_forest_cover_pct"], 50.0, places=6)
        self.assertAlmostEqual(right["grassland_pasture_cover_pct"], 0.0, places=6)
        self.assertAlmostEqual(right["shrub_transitional_cover_pct"], 50.0, places=6)

        self.assertEqual(tables.manifest["municipality_feature_row_count"], 2)
        self.assertEqual(tables.manifest["sampling_row_count"], 2)


if __name__ == "__main__":
    unittest.main()
