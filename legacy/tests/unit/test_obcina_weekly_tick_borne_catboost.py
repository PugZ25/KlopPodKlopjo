from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from pipelines.features.obcina_weekly_tick_borne_catboost import (
    build_weekly_tick_borne_catboost_dataset,
)


class WeeklyTickBorneCatBoostDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.weather_dem_path = self.temp_path / "weather_dem.csv"
        self.clc_path = self.temp_path / "clc.csv"
        self.log_population_path = self.temp_path / "log_population.csv"
        self.population_density_path = self.temp_path / "population_density.csv"
        self.epidemiology_path = self.temp_path / "epidemiology.csv"

        self.weather_dem_path.write_text(
            "\n".join(
                [
                    "week_start,week_end,obcina_sifra,obcina_naziv,year,month,iso_year,iso_week,week_of_year_sin,week_of_year_cos,overlay_method,air_temperature_c_mean",
                    "2021-02-22,2021-02-28,1,Ajdovscina,2021,2,2021,8,0.8,0.6,area_weighted_polygon_overlay,10.0",
                    "2021-03-01,2021-03-07,1,Ajdovscina,2021,3,2021,9,0.9,0.4,area_weighted_polygon_overlay,11.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.clc_path.write_text(
            "\n".join(
                [
                    "obcina_sifra,obcina_naziv,dominant_clc_code,dominant_clc_cover_pct,urban_cover_pct,agricultural_cover_pct,grassland_pasture_cover_pct,forest_cover_pct,broad_leaved_forest_cover_pct,coniferous_forest_cover_pct,mixed_forest_cover_pct,shrub_transitional_cover_pct,open_bare_cover_pct,wetland_cover_pct,water_cover_pct",
                    "1,Ajdovscina,311,30.0,3.0,29.0,4.0,62.0,29.0,10.0,23.0,4.0,0.2,0.0,0.1",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.log_population_path.write_text(
            "\n".join(
                [
                    "year,obcina_sifra,obcina_naziv,log_population_total",
                    "2020,1,Ajdovscina,9.9",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.population_density_path.write_text(
            "\n".join(
                [
                    "year,obcina_sifra,obcina_naziv,population_density_per_km2",
                    "2020,1,Ajdovscina,78.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        epidemiology_rows = [
            ("2021-01-04", "2021-01-10", 1, 0),
            ("2021-01-11", "2021-01-17", 2, 1),
            ("2021-01-18", "2021-01-24", 3, 0),
            ("2021-01-25", "2021-01-31", 4, 1),
            ("2021-02-01", "2021-02-07", 5, 0),
            ("2021-02-08", "2021-02-14", 6, 0),
            ("2021-02-15", "2021-02-21", 7, 1),
            ("2021-02-22", "2021-02-28", 8, 0),
            ("2021-03-01", "2021-03-07", 9, 1),
        ]
        with self.epidemiology_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "week_start",
                    "week_end",
                    "iso_year",
                    "iso_week",
                    "obcina_sifra",
                    "obcina_naziv",
                    "lyme_cases",
                    "kme_cases",
                    "tick_borne_cases_total",
                ],
            )
            writer.writeheader()
            for iso_week, row in enumerate(epidemiology_rows, start=1):
                week_start, week_end, lyme_cases, kme_cases = row
                writer.writerow(
                    {
                        "week_start": week_start,
                        "week_end": week_end,
                        "iso_year": 2021,
                        "iso_week": iso_week,
                        "obcina_sifra": "1",
                        "obcina_naziv": "Ajdovscina",
                        "lyme_cases": lyme_cases,
                        "kme_cases": kme_cases,
                        "tick_borne_cases_total": lyme_cases + kme_cases,
                    }
                )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_builder_combines_sources_and_computes_past_only_epidemiology_features(self) -> None:
        tables = build_weekly_tick_borne_catboost_dataset(
            weather_dem_input=self.weather_dem_path,
            clc_input=self.clc_path,
            log_population_input=self.log_population_path,
            population_density_input=self.population_density_path,
            epidemiology_input=self.epidemiology_path,
        )

        combined = tables.combined
        self.assertEqual(len(combined), 2)

        feb_22 = combined[combined["week_start"] == "2021-02-22"].iloc[0]
        self.assertEqual(feb_22["target_lyme_cases"], 8)
        self.assertEqual(feb_22["target_kme_cases"], 0)
        self.assertEqual(feb_22["lyme_cases_lag_2w"], 6.0)
        self.assertEqual(feb_22["lyme_cases_lag_3w"], 5.0)
        self.assertEqual(feb_22["lyme_cases_prev_4w_sum"], 22.0)
        self.assertTrue(math.isnan(feb_22["kme_cases_prev_8w_sum"]))

        mar_01 = combined[combined["week_start"] == "2021-03-01"].iloc[0]
        self.assertEqual(mar_01["target_lyme_cases"], 9)
        self.assertEqual(mar_01["target_kme_cases"], 1)
        self.assertEqual(mar_01["target_tick_borne_cases_total"], 10)
        self.assertEqual(mar_01["target_lyme_presence"], 1)
        self.assertEqual(mar_01["target_kme_presence"], 1)
        self.assertEqual(mar_01["lyme_cases_lag_2w"], 7.0)
        self.assertEqual(mar_01["lyme_cases_lag_3w"], 6.0)
        self.assertEqual(mar_01["lyme_cases_prev_4w_sum"], 26.0)
        self.assertEqual(mar_01["kme_cases_lag_2w"], 1.0)
        self.assertEqual(mar_01["kme_cases_prev_8w_sum"], 3.0)
        self.assertEqual(mar_01["dominant_clc_code"], "311")
        self.assertAlmostEqual(mar_01["log_population_total"], 9.9, places=6)
        self.assertEqual(mar_01["log_population_total_source_year"], 2020)
        self.assertAlmostEqual(mar_01["population_density_per_km2"], 78.0, places=6)
        self.assertEqual(mar_01["population_density_source_year"], 2020)

        self.assertIn("lyme_cases_prev_4w_sum", tables.manifest["added_epidemiology_feature_columns"])
        self.assertIn("target_kme_cases", tables.manifest["target_columns"])


if __name__ == "__main__":
    unittest.main()
