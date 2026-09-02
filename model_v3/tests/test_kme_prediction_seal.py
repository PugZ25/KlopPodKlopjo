from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from model_v3.models.kme_model_freeze import FEATURE_COLUMNS
from model_v3.models.kme_region_model import annual_harmonic, sha256_file
from model_v3.predict.kme_prediction_seal import (
    BASELINE_RATE,
    DEFAULT_CONFIG_PATH,
    GLM_BASE,
    PARQUET_SCHEMA,
    PERSISTENCE_ID,
    REPO_ROOT,
    SNAPSHOT_COLUMNS,
    KmePredictionSealError,
    eligible_issue_weeks,
    json_row,
    load_config,
    read_frozen_feature_panel,
    verify_inputs,
)


OUTPUT_ROOT = REPO_ROOT / "model_v3" / "outputs" / "kme_prediction_seal"


class KmePredictionSealTests(unittest.TestCase):
    def test_seal_decisions_and_input_hashes_match(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        paths, hashes = verify_inputs(config, REPO_ROOT)
        self.assertEqual(
            config["seal"]["status"],
            "SEALED_WITHOUT_PIPELINE_ACCESS_TO_2026_KME_OUTCOMES",
        )
        self.assertEqual(
            config["seal"]["temporal_classification"],
            "retrospective_ongoing_holdout_predictions_sealed_during_2026_not_fully_prospective",
        )
        self.assertEqual(
            config["seal"]["external_human_outcome_access_status"],
            "UNKNOWN_not_auditable_from_repository",
        )
        self.assertEqual(config["prediction_period"]["target_offsets"], list(range(1, 9)))
        self.assertFalse(config["prediction_period"]["issue_week_included"])
        self.assertEqual(
            [system["candidate_id"] for system in config["systems"]],
            [GLM_BASE, BASELINE_RATE, PERSISTENCE_ID],
        )
        self.assertEqual(set(paths), set(hashes))

    def test_eligible_issue_grid_is_derived_from_iso_dates(self) -> None:
        issues = eligible_issue_weeks(2026, 8)
        self.assertEqual(len(issues), 45)
        self.assertEqual(issues[0], date(2025, 12, 29))
        self.assertEqual(issues[-1], date(2026, 11, 2))
        self.assertTrue(all(issue.isocalendar().year == 2026 for issue in issues))
        self.assertTrue(
            all(
                (issue.fromordinal(issue.toordinal() + 7 * offset)).isocalendar().year
                == 2026
                for issue in issues
                for offset in range(1, 9)
            )
        )

    def test_snapshot_formats_share_one_canonical_table(self) -> None:
        json_rows = json.loads(
            (OUTPUT_ROOT / "kme_2026_sealed_predictions.json").read_text(encoding="utf-8")
        )
        parquet_table = pq.read_table(OUTPUT_ROOT / "kme_2026_sealed_predictions.parquet")
        parquet_rows = [json_row(row) for row in parquet_table.to_pylist()]
        self.assertEqual(parquet_table.schema, PARQUET_SCHEMA)
        self.assertEqual(json_rows, parquet_rows)
        self.assertEqual(len(json_rows), 1080)
        self.assertEqual(
            Counter(row["candidate_id"] for row in json_rows),
            Counter({GLM_BASE: 540, BASELINE_RATE: 540}),
        )
        keys = {
            (row["candidate_id"], row["statistical_region_code"], row["issue_week"])
            for row in json_rows
        }
        self.assertEqual(len(keys), len(json_rows))
        self.assertTrue(all(row["lower_interval"] is None for row in json_rows))
        self.assertTrue(all(row["upper_interval"] is None for row in json_rows))
        self.assertTrue(
            all(
                row["population_year_max"] < date.fromisoformat(row["issue_week"]).year
                for row in json_rows
            )
        )

        with (OUTPUT_ROOT / "kme_2026_sealed_predictions.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            csv_rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(csv_rows[0]), SNAPSHOT_COLUMNS)
        self.assertEqual(len(csv_rows), len(json_rows))

    def test_selected_prediction_matches_frozen_glm_equation(self) -> None:
        rows = json.loads(
            (OUTPUT_ROOT / "kme_2026_sealed_predictions.json").read_text(encoding="utf-8")
        )
        selected = next(row for row in rows if row["candidate_id"] == GLM_BASE)
        with (OUTPUT_ROOT / "kme_frozen_final_glm_coefficients.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            coefficients = {
                row["feature"]: float(row["coefficient"])
                for row in csv.DictReader(handle)
            }
        issue = date.fromisoformat(selected["issue_week"])
        seasonal_sin, seasonal_cos = annual_harmonic(issue)
        linear_predictor = (
            math.log(selected["population_exposure"] / 100_000.0)
            + coefficients["intercept"]
            + coefficients["seasonal_sin_annual"] * seasonal_sin
            + coefficients["seasonal_cos_annual"] * seasonal_cos
            + coefficients.get(f"region[{selected['statistical_region_code']}]", 0.0)
        )
        self.assertAlmostEqual(
            selected["predicted_cases"], math.exp(linear_predictor), places=12
        )
        self.assertAlmostEqual(
            selected["predicted_incidence_per_100000"],
            selected["predicted_cases"]
            / selected["population_exposure"]
            * 100_000.0,
            places=12,
        )

    def test_manifest_records_current_contract_and_no_outcome_access(self) -> None:
        manifest_path = OUTPUT_ROOT / "kme_2026_prediction_seal_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["configuration"]["sha256"], sha256_file(DEFAULT_CONFIG_PATH)
        )
        self.assertEqual(
            manifest["code"]["sha256"],
            sha256_file(REPO_ROOT / "model_v3" / "predict" / "kme_prediction_seal.py"),
        )
        self.assertFalse(manifest["checks"]["2026_KME_outcomes_read"])
        self.assertFalse(manifest["checks"]["2026_KME_targets_created"])
        self.assertFalse(manifest["checks"]["weather_used_by_selected_model"])
        self.assertFalse(manifest["checks"]["past_KME_used_by_selected_model"])
        self.assertEqual(manifest["prediction_support"]["last_target_window_end"], "2026-12-28")

    def test_persistence_is_an_algorithm_contract_not_fabricated_values(self) -> None:
        contract = json.loads(
            (OUTPUT_ROOT / "kme_2026_persistence_baseline_contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["candidate_id"], PERSISTENCE_ID)
        self.assertEqual(
            contract["algorithm"],
            "sum_reported_regional_KME_cases_in_exactly_t_minus_8_through_t_minus_1",
        )
        self.assertFalse(contract["current_or_future_target_values_allowed"])
        self.assertEqual(contract["missing_past_week_rule"], "prediction_unavailable_not_zero")
        self.assertNotIn("predictions", contract)

    def test_protected_fit_row_is_rejected_before_outcome_numeric_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protected.csv"
            protected = dict.fromkeys(FEATURE_COLUMNS, "protected_not_numeric")
            protected.update(
                {
                    "statistical_region_code": "UNKNOWN_NOT_PARSED",
                    "statistical_region_name": "UNKNOWN_NOT_PARSED",
                    "issue_week": "2026-01-05",
                    "target_window_start": "2026-01-12",
                    "target_window_end": "2026-03-02",
                }
            )
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FEATURE_COLUMNS)
                writer.writeheader()
                writer.writerow(protected)
            with self.assertRaisesRegex(
                KmePredictionSealError, "Protected 2026 outcome row"
            ):
                read_frozen_feature_panel(path)


if __name__ == "__main__":
    unittest.main()
