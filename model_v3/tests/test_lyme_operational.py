from __future__ import annotations

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from model_v3.features.weather_weekly import OUTPUT_VARIABLES, WEEKLY_COLUMNS
from model_v3.predict.lyme_operational import (
    assess_readiness,
    compare_prediction_snapshots,
    create_prediction_snapshot,
    load_config,
    seal_frozen_model,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LymeOperationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()
        cls.manifest = seal_frozen_model(cls.config)

    def test_sealed_model_is_bound_to_frozen_support(self) -> None:
        self.assertEqual(self.manifest["status"], "sealed")
        self.assertEqual(self.manifest["training"]["municipality_count"], 212)
        self.assertEqual(self.manifest["training"]["last_issue_week"], "2024-12-02")
        self.assertEqual(
            len(
                self.manifest["artifacts"]["model"][
                    "structural_sha256_excluding_volatile_metadata"
                ]
            ),
            64,
        )
        self.assertFalse(self.manifest["operational_retraining_allowed"])

    def test_readiness_blocks_missing_current_inputs(self) -> None:
        payload = assess_readiness(
            self.config,
            issue_week=date(2026, 8, 24),
            weekly_weather_path=Path("/tmp/does-not-exist-weather.csv"),
            weather_quality_path=Path("/tmp/does-not-exist-quality.json"),
            weekly_cases_path=Path("/tmp/does-not-exist-cases.csv"),
            weekly_cases_provenance_path=Path(
                "/tmp/does-not-exist-cases-provenance.json"
            ),
        )
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["checks"]["sealed_model_artifacts_present"])
        self.assertFalse(payload["checks"]["operational_weekly_cases_present"])

    def test_end_to_end_snapshot_uses_all_municipalities_and_no_risk_levels(self) -> None:
        issue_week = date(2026, 8, 24)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            weekly_cases_path = temporary / "weekly_cases.csv"
            weekly_weather_path = temporary / "weekly_weather.csv"
            weather_quality_path = temporary / "weather_quality.json"
            case_provenance_path = temporary / "weekly_cases.provenance.json"
            output_directory = temporary / "outputs"
            with (
                REPO_ROOT / "model_v3/outputs/canonical/municipality.csv"
            ).open(encoding="utf-8", newline="") as handle:
                municipality_rows = list(csv.DictReader(handle))
            municipality_codes = [row["municipality_code"] for row in municipality_rows]

            with weekly_cases_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("municipality_code", "issue_week", "lyme_cases"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "municipality_code": "invalid-code-is-not-parsed",
                        "issue_week": issue_week.isoformat(),
                        "lyme_cases": "future-value-is-not-parsed",
                    }
                )
                for code in municipality_codes:
                    for lag in (4, 3, 2, 1):
                        writer.writerow(
                            {
                                "municipality_code": code,
                                "issue_week": (issue_week - timedelta(weeks=lag)).isoformat(),
                                "lyme_cases": 1 if code == "001" and lag == 1 else 0,
                            }
                        )

            case_provenance_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_name": "Synthetic NIJZ-compatible test fixture",
                        "source_url": "https://example.invalid/test-fixture",
                        "retrieved_at_utc": "2026-08-28T08:00:00+00:00",
                        "acquisition_method": "unit_test_fixture",
                        "source_file": {
                            "filename": weekly_cases_path.name,
                            "sha256": sha256(weekly_cases_path),
                        },
                    }
                ),
                encoding="utf-8",
            )

            weather_values = {
                "t2m_mean_c": 18.0,
                "d2m_mean_c": 12.0,
                "tp_sum_mm": 15.0,
                "stl1_mean_c": 17.0,
                "stl2_mean_c": 15.0,
                "swvl1_mean_m3_m3": 0.25,
                "swvl2_mean_m3_m3": 0.28,
            }
            with weekly_weather_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=WEEKLY_COLUMNS)
                writer.writeheader()
                for lag in (4, 3, 2, 1):
                    week = issue_week - timedelta(weeks=lag)
                    for code in municipality_codes:
                        writer.writerow(
                            {
                                "municipality_code": code,
                                "week_start": week.isoformat(),
                                "week_end": (week + timedelta(days=6)).isoformat(),
                                "weather_status": "complete",
                                "source_hour_count": 168,
                                "minimum_present_hours": 168,
                                **weather_values,
                            }
                        )
            quality = {
                "schema_version": 1,
                "status": "pass",
                "issue_week": issue_week.isoformat(),
                "weather_vintage": "preliminary_era5_land_t",
                "municipality_count": 212,
                "complete_week_count": 4,
                "weekly_dataset": {"sha256": sha256(weekly_weather_path)},
            }
            weather_quality_path.write_text(
                json.dumps(quality), encoding="utf-8"
            )
            config = copy.deepcopy(self.config)
            config["outputs"]["directory"] = str(output_directory)
            config["outputs"]["frontend_json"] = str(temporary / "frontend.json")
            snapshot = create_prediction_snapshot(
                config,
                issue_week=issue_week,
                weekly_weather_path=weekly_weather_path,
                weather_quality_path=weather_quality_path,
                weekly_cases_path=weekly_cases_path,
                weekly_cases_provenance_path=case_provenance_path,
                generated_at=datetime(2026, 8, 28, 12, tzinfo=timezone.utc),
                publish_frontend=False,
            )
            self.assertEqual(snapshot["municipality_count"], 212)
            self.assertEqual(snapshot["weather_vintage"], "preliminary_era5_land_t")
            self.assertEqual(snapshot["target_window_start"], "2026-08-31")
            self.assertEqual(snapshot["target_window_end"], "2026-09-27")
            self.assertEqual(len(snapshot["predictions"]), 212)
            self.assertTrue(
                all(
                    row["latest_case_week_used"] == "2026-08-17"
                    and row["latest_weather_week_used"] == "2026-08-17"
                    for row in snapshot["predictions"]
                )
            )
            self.assertTrue(
                all("risk_level" not in row for row in snapshot["predictions"])
            )
            self.assertFalse((temporary / "frontend.json").exists())
            output = json.loads(
                (output_directory / "prediction_snapshot_quality.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(output["status"], "pass")

    def test_prediction_bridge_is_diagnostic_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            preliminary_path = temporary / "preliminary.json"
            final_path = temporary / "final.json"
            common = {
                "issue_week": "2026-08-24",
                "predictions": [
                    {
                        "municipality_code": "001",
                        "predicted_reported_lyme_cases_next_4w": 1.0,
                    },
                    {
                        "municipality_code": "002",
                        "predicted_reported_lyme_cases_next_4w": 3.0,
                    },
                ],
            }
            preliminary = {
                **common,
                "weather_vintage": "preliminary_era5_land_t",
            }
            final = {
                **common,
                "weather_vintage": "final_era5_land",
                "predictions": [
                    {
                        "municipality_code": "001",
                        "predicted_reported_lyme_cases_next_4w": 2.0,
                    },
                    {
                        "municipality_code": "002",
                        "predicted_reported_lyme_cases_next_4w": 2.0,
                    },
                ],
            }
            preliminary_path.write_text(json.dumps(preliminary), encoding="utf-8")
            final_path.write_text(json.dumps(final), encoding="utf-8")
            result = compare_prediction_snapshots(preliminary_path, final_path)
            self.assertEqual(
                result["status"], "diagnostic_only_no_promotion_decision"
            )
            self.assertEqual(result["metrics"]["mae_final_minus_preliminary"], 1.0)
            self.assertIsNone(result["promotion_thresholds"])
            self.assertFalse(result["automatic_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
