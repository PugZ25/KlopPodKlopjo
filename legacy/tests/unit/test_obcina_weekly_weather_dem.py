from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipelines.features.obcina_weekly_weather_dem import (
    DEM_FEATURE_COLUMNS,
    build_weekly_weather_dem_features,
)


class WeeklyWeatherDemJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.weather_path = self.temp_path / "weather.csv"
        self.dem_path = self.temp_path / "dem.csv"

        self.weather_path.write_text(
            "\n".join(
                [
                    "week_start,week_end,obcina_sifra,obcina_naziv,air_temperature_c_mean,precipitation_sum_mm",
                    "2026-01-05,2026-01-11,1,Ajdovscina,10.0,12.5",
                    "2026-01-12,2026-01-18,1,Ajdovscina,11.0,13.5",
                    "2026-01-05,2026-01-11,2,Tisina,5.0,7.5",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.dem_path.write_text(
            "\n".join(
                [
                    "obcina_sifra,obcina_naziv,elevation_m_mean,elevation_m_std,elevation_m_range",
                    "1,Ajdovscina,626.2,405.1,1425.7",
                    "2,Tisina,198.3,4.7,38.8",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_join_adds_requested_dem_columns(self) -> None:
        tables = build_weekly_weather_dem_features(
            weather_input=self.weather_path,
            dem_input=self.dem_path,
        )

        combined = tables.combined
        self.assertEqual(len(combined), 3)
        for column in DEM_FEATURE_COLUMNS:
            self.assertIn(column, combined.columns)

        first = combined.iloc[0]
        self.assertEqual(first["obcina_sifra"], 1)
        self.assertAlmostEqual(first["elevation_m_mean"], 626.2, places=6)
        self.assertAlmostEqual(first["elevation_m_std"], 405.1, places=6)
        self.assertAlmostEqual(first["elevation_m_range"], 1425.7, places=6)

        second_tisina = combined[combined["obcina_sifra"] == 2].iloc[0]
        self.assertAlmostEqual(second_tisina["elevation_m_mean"], 198.3, places=6)


if __name__ == "__main__":
    unittest.main()
