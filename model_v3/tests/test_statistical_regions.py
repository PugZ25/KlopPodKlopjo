from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from model_v3.data.statistical_regions import (
    EXPECTED_HEADERS,
    StatisticalRegionError,
    parse_surs_hierarchy,
)


class StatisticalRegionTests(unittest.TestCase):
    def write_fixture(self, path: Path, rows: list[tuple[object, ...]]) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "fixture"
        worksheet.append(EXPECTED_HEADERS)
        for row in rows:
            worksheet.append(row)
        workbook.save(path)

    def test_hierarchy_uses_codes_and_parent_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regions.xlsx"
            self.write_fixture(
                path,
                [
                    (1, "01", "Region one", "Region one", None),
                    (2, "01.001", "Municipality", "Municipality", "01"),
                    (3, "01.001.001", "Settlement", "Settlement", "01.001"),
                ],
            )
            regions, municipalities = parse_surs_hierarchy(
                path,
                sheet_name="fixture",
                region_level=1,
                municipality_level=2,
            )

        self.assertEqual(regions[0]["statistical_region_code"], "01")
        self.assertEqual(municipalities[0]["municipality_code"], "001")
        self.assertEqual(municipalities[0]["statistical_region_code"], "01")

    def test_parent_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regions.xlsx"
            self.write_fixture(
                path,
                [
                    (1, "01", "Region one", "Region one", None),
                    (2, "01.001", "Municipality", "Municipality", "02"),
                ],
            )
            with self.assertRaisesRegex(StatisticalRegionError, "parent contradicts"):
                parse_surs_hierarchy(
                    path,
                    sheet_name="fixture",
                    region_level=1,
                    municipality_level=2,
                )


if __name__ == "__main__":
    unittest.main()
