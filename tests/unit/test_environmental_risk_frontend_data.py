from __future__ import annotations

import bisect
import csv
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path


class EnvironmentalRiskFrontendDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.frontend_data_path = (
            cls.repo_root / "frontend" / "src" / "data" / "environmentalRisk.ts"
        )
        cls.generator_path = (
            cls.repo_root / "scripts" / "data" / "build_environmental_risk_frontend_data.py"
        )
        cls.frontend_models = cls._load_frontend_models()

    @classmethod
    def _load_frontend_models(cls) -> dict[str, object]:
        text = cls.frontend_data_path.read_text(encoding="utf-8")
        marker = "export const environmentalRiskModels"
        start = text.index("{", text.index(marker))
        return json.loads(text[start:])

    def test_generator_reports_frontend_data_is_up_to_date(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.generator_path), "--check"],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            self.fail(result.stdout + result.stderr)

    def test_frontend_data_matches_env_v2_holdout_methodology(self) -> None:
        specs = (
            (
                "borelioza",
                "catboost_tick_borne_lyme_env_v2",
                self.repo_root
                / "data"
                / "processed"
                / "training"
                / "catboost_tick_borne_lyme_env_v2"
                / "holdout_predictions.csv",
                "prediction_probability",
            ),
            (
                "kme",
                "catboost_tick_borne_kme_env_v2",
                self.repo_root
                / "data"
                / "processed"
                / "training"
                / "catboost_tick_borne_kme_env_v2"
                / "holdout_predictions.csv",
                "prediction_probability",
            ),
        )

        for disease_key, model_id, holdout_path, prediction_column in specs:
            with self.subTest(disease_key=disease_key):
                frontend_model = self.frontend_models[disease_key]
                self.assertEqual(frontend_model["modelId"], model_id)

                with holdout_path.open(encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                holdout_values = sorted(
                    float(row[prediction_column])
                    for row in rows
                    if row["split"] in {"validation", "test"}
                )
                low_upper = self._percentile_threshold(holdout_values, 1 / 3)
                medium_upper = self._percentile_threshold(holdout_values, 2 / 3)

                self.assertAlmostEqual(
                    frontend_model["thresholds"]["lowUpper"],
                    low_upper,
                    places=12,
                )
                self.assertAlmostEqual(
                    frontend_model["thresholds"]["mediumUpper"],
                    medium_upper,
                    places=12,
                )

                snapshot_week = max(row["week_start"] for row in rows if row["split"] == "test")
                self.assertEqual(frontend_model["snapshotWeekStart"], snapshot_week)

                snapshot_rows = [
                    row
                    for row in rows
                    if row["split"] == "test" and row["week_start"] == snapshot_week
                ]
                expected_by_id = {}
                for row in snapshot_rows:
                    municipality_code = str(row["obcina_sifra"])
                    raw_value = float(row[prediction_column])
                    expected_by_id[f"{disease_key}-{municipality_code}"] = {
                        "score": self._score_percentile(holdout_values, raw_value),
                        "level": self._classify_level(raw_value, low_upper, medium_upper),
                        "weekStart": snapshot_week,
                    }

                frontend_locations = frontend_model["locations"]
                self.assertEqual(len(frontend_locations), len(expected_by_id))

                for location in frontend_locations:
                    expected = expected_by_id[location["id"]]
                    self.assertEqual(location["score"], expected["score"])
                    self.assertEqual(location["level"], expected["level"])
                    self.assertEqual(location["weekStart"], expected["weekStart"])
                    self.assertEqual(len(location["coordinates"]), 2)

                expected_featured_ids = [
                    location["id"] for location in frontend_locations[:8]
                ]
                actual_featured_ids = [
                    location["id"] for location in frontend_model["featuredLocations"]
                ]
                self.assertEqual(actual_featured_ids, expected_featured_ids)

    def test_frontend_score_semantics_are_relative_environmental_index(self) -> None:
        for disease_key, frontend_model in self.frontend_models.items():
            with self.subTest(disease_key=disease_key):
                disclaimer = frontend_model["disclaimer"].lower()
                score_explanation = frontend_model["scoreExplanation"].lower()

                self.assertIn("relativni okoljski indeks", disclaimer)
                self.assertIn("relativni okoljski indeks", score_explanation)
                self.assertIn("0-100", score_explanation)
                self.assertIn("empiricni percentil", score_explanation)

    @staticmethod
    def _percentile_threshold(sorted_values: list[float], percentile: float) -> float:
        index = (len(sorted_values) - 1) * percentile
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return sorted_values[lower]
        lower_weight = upper - index
        upper_weight = index - lower
        return (sorted_values[lower] * lower_weight) + (sorted_values[upper] * upper_weight)

    @staticmethod
    def _score_percentile(sorted_values: list[float], value: float) -> int:
        rank = bisect.bisect_right(sorted_values, value)
        return round((100 * rank) / len(sorted_values))

    @staticmethod
    def _classify_level(value: float, low_upper: float, medium_upper: float) -> str:
        if value < low_upper:
            return "Nizko"
        if value < medium_upper:
            return "Srednje"
        return "Visoko"


if __name__ == "__main__":
    unittest.main()
