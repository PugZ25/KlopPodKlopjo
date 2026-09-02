from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from model_v3.models.kme_model_freeze import (
    DEFAULT_CONFIG_PATH,
    GLM_BASE,
    REPO_ROOT,
    FreezeRow,
    design_matrix,
    generate_folds,
    load_config,
    read_development_population,
    read_development_region_cases,
    read_development_targets,
    sha256_file,
    verify_inputs,
)


def row(issue_week: date) -> FreezeRow:
    return FreezeRow(
        region_code="R1",
        region_name="Region One",
        issue_week=issue_week,
        target_start=issue_week + timedelta(weeks=1),
        target_end=issue_week + timedelta(weeks=8),
        target_value=1,
        population=200_000,
        population_year_min=issue_week.year - 1,
        population_year_max=issue_week.year - 1,
        seasonal_sin=0.25,
        seasonal_cos=0.75,
        past_cases=2,
        latest_past_case_week=issue_week - timedelta(weeks=1),
    )


class KmeModelFreezeTests(unittest.TestCase):
    def test_frozen_decisions_and_input_hashes_match(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        paths, hashes = verify_inputs(config, REPO_ROOT)
        self.assertEqual(config["freeze"]["status"], "FROZEN")
        self.assertEqual(config["task"]["target_offsets"], list(range(1, 9)))
        self.assertFalse(config["task"]["issue_week_included"])
        self.assertEqual(config["selected_model"]["candidate_id"], GLM_BASE)
        self.assertEqual(config["prospective_lockbox"]["iso_year"], 2026)
        self.assertFalse(config["finalization_support"]["weather_required"])
        self.assertEqual(set(paths), set(hashes))

    def test_freeze_manifest_records_current_config_and_code(self) -> None:
        path = REPO_ROOT / "model_v3/outputs/kme_model_freeze/kme_model_freeze_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "FROZEN_DEVELOPMENT_SYSTEM_2026_PIPELINE_LOCKBOX_UNOPENED")
        self.assertEqual(manifest["configuration"]["sha256"], sha256_file(DEFAULT_CONFIG_PATH))
        self.assertEqual(
            manifest["code"]["sha256"],
            sha256_file(REPO_ROOT / "model_v3/models/kme_model_freeze.py"),
        )
        self.assertFalse(manifest["checks"]["post_2025_KME_outcomes_opened"])

    def test_protected_rows_are_skipped_before_outcome_numeric_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_path = root / "target.csv"
            with target_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "statistical_region_code",
                        "issue_week",
                        "target_window_start",
                        "target_window_end",
                        "target_kme_cases_next_8w",
                        "target_status",
                        "target_training_eligible",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "statistical_region_code": "R1",
                            "issue_week": "2025-01-06",
                            "target_window_start": "2025-01-13",
                            "target_window_end": "2025-03-03",
                            "target_kme_cases_next_8w": "2",
                            "target_status": "complete",
                            "target_training_eligible": "true",
                        },
                        {
                            "statistical_region_code": "UNKNOWN_NOT_PARSED",
                            "issue_week": "2026-01-05",
                            "target_window_start": "2026-01-12",
                            "target_window_end": "2026-03-02",
                            "target_kme_cases_next_8w": "protected_not_numeric",
                            "target_status": "protected_not_parsed",
                            "target_training_eligible": "protected_not_parsed",
                        },
                    ]
                )
            targets, skipped_targets = read_development_targets(
                target_path, {"R1": "Region One"}, 2026
            )
            self.assertEqual(len(targets), 1)
            self.assertEqual(skipped_targets, 1)

            cases_path = root / "weekly.csv"
            with cases_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["municipality_code", "issue_week", "kme_cases"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"municipality_code": "001", "issue_week": "2025-01-06", "kme_cases": "1"},
                        {
                            "municipality_code": "UNKNOWN_NOT_PARSED",
                            "issue_week": "2026-01-05",
                            "kme_cases": "protected_not_numeric",
                        },
                    ]
                )
            cases, skipped_cases = read_development_region_cases(
                cases_path, {"001": "R1"}, 2026
            )
            self.assertEqual(cases[("R1", date(2025, 1, 6))], 1)
            self.assertEqual(skipped_cases, 1)

            population_path = root / "population.csv"
            with population_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["municipality_code", "year", "population"]
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"municipality_code": "001", "year": "2025", "population": "100"},
                        {
                            "municipality_code": "UNKNOWN_NOT_PARSED",
                            "year": "2026",
                            "population": "protected_not_numeric",
                        },
                    ]
                )
            population, skipped_population = read_development_population(
                population_path, 2026
            )
            self.assertEqual(population["001"][2025], 100)
            self.assertEqual(skipped_population, 1)

    def test_selected_design_has_no_population_weather_or_past_case_column(self) -> None:
        matrix, columns = design_matrix([row(date(2022, 6, 6))], ["R1"])
        self.assertEqual(matrix.shape, (1, 3))
        self.assertEqual(
            columns, ("intercept", "seasonal_sin_annual", "seasonal_cos_annual")
        )
        self.assertNotIn("population", " ".join(columns))
        self.assertNotIn("weather", " ".join(columns))
        self.assertNotIn("past", " ".join(columns))

    def test_frozen_folds_purge_target_windows_at_boundary(self) -> None:
        safe_2018 = row(date(2018, 6, 4))
        safe_2019 = row(date(2019, 6, 3))
        crossing = row(date(2019, 11, 11))
        validation = row(date(2020, 1, 6))
        config = {
            "validation": {
                "first_validation_iso_year": 2020,
                "last_validation_iso_year": 2020,
                "minimum_distinct_training_iso_years": 2,
            }
        }
        folds = generate_folds([safe_2018, safe_2019, crossing, validation], config)
        self.assertEqual(len(folds), 1)
        self.assertEqual(folds[0].n_purged, 1)
        self.assertEqual(folds[0].train_rows, (safe_2018, safe_2019))
        self.assertTrue(
            all(item.target_end < folds[0].validation_start for item in folds[0].train_rows)
        )


if __name__ == "__main__":
    unittest.main()
