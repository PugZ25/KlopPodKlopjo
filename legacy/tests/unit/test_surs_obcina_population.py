from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from pipelines.features.surs_obcina_population import (
    build_obcina_surs_population_yearly_features,
)


class SursPopulationPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.raw_path = self.temp_path / "surs.json"

        payload = {
            "label": "Selected data by MEASURES, MUNICIPALITIES and YEAR",
            "source": "Statistical Office of the Republic of Slovenia",
            "id": ["MERITVE", "OBČINE", "LETO"],
            "size": [1, 3, 2],
            "dimension": {
                "MERITVE": {
                    "category": {
                        "index": {"45": 0},
                        "label": {
                            "45": "Population - Total - 1 January",
                        },
                    }
                },
                "OBČINE": {
                    "category": {
                        "index": {"0": 0, "001": 1, "010": 2},
                        "label": {
                            "0": "SLOVENIA",
                            "001": "Ajdovščina",
                            "010": "Tišina",
                        },
                    }
                },
                "LETO": {
                    "category": {
                        "index": {"2024": 0, "2025": 1},
                        "label": {"2024": "2024", "2025": "2025"},
                    }
                },
            },
            "value": [
                2120000,
                2125000,
                19891,
                19895,
                3948,
                None,
            ],
            "status": {
                "5": "...",
            },
        }
        self.raw_path.write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_parses_yearly_rows_and_computes_log_population(self) -> None:
        tables = build_obcina_surs_population_yearly_features(raw_input=self.raw_path)

        yearly = tables.yearly_features.reset_index(drop=True)
        self.assertEqual(len(yearly), 4)
        self.assertEqual(yearly["obcina_sifra"].tolist(), ["1", "10", "1", "10"])

        first = yearly.iloc[0]
        self.assertEqual(first["year"], 2024)
        self.assertEqual(first["obcina_naziv"], "Ajdovščina")
        self.assertAlmostEqual(first["log_population_total"], math.log1p(19891), places=12)

        tisina_2025 = yearly[(yearly["obcina_sifra"] == "10") & (yearly["year"] == 2025)].iloc[0]
        self.assertTrue(math.isnan(tisina_2025["log_population_total"]))

        self.assertEqual(tables.manifest["municipality_count"], 2)
        self.assertEqual(tables.manifest["latest_available_year"], 2025)
        self.assertEqual(tables.manifest["years_with_missing_values"], [2025])
        self.assertEqual(
            tables.manifest["columns"],
            ["year", "obcina_sifra", "obcina_naziv", "log_population_total"],
        )


if __name__ == "__main__":
    unittest.main()
