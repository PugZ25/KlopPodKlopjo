from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from model_v3.models.kme_region_model import sha256_file
from model_v3.models.tick_borne_combined_model_freeze import (
    DEFAULT_CONFIG_PATH as FREEZE_CONFIG_PATH,
)
from model_v3.models.tick_borne_combined_model_freeze import (
    load_config as load_freeze_config,
)
from model_v3.models.tick_borne_combined_region_model import (
    DEFAULT_CONFIG_PATH as MODEL_CONFIG_PATH,
)
from model_v3.models.tick_borne_combined_region_model import (
    PUBLIC_SYSTEM_IDS,
    load_config as load_model_config,
    verify_inputs as verify_model_inputs,
)
from model_v3.panel.tick_borne_combined_eight_week_target import (
    DEFAULT_CONFIG_PATH as TARGET_CONFIG_PATH,
)
from model_v3.panel.tick_borne_combined_eight_week_target import (
    construct_target_rows,
    load_config as load_target_config,
    verify_inputs as verify_target_inputs,
)
from model_v3.predict.tick_borne_combined_prediction_snapshot import (
    DEFAULT_CONFIG_PATH as PREDICTION_CONFIG_PATH,
)
from model_v3.predict.tick_borne_combined_prediction_snapshot import (
    FORBIDDEN_FIELDS,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_SCHEMA,
    load_config as load_prediction_config,
    read_required_past_cases,
    verify_inputs as verify_prediction_inputs,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_OUTPUT = REPO_ROOT / "model_v3" / "outputs" / "tick_borne_combined_model"
FREEZE_OUTPUT = REPO_ROOT / "model_v3" / "outputs" / "tick_borne_combined_freeze"
SNAPSHOT_OUTPUT = (
    REPO_ROOT
    / "model_v3"
    / "outputs"
    / "tick_borne_combined_prediction_snapshot"
    / "v1"
)


class TickBorneCombinedPipelineTests(unittest.TestCase):
    def test_target_contract_and_hashes(self) -> None:
        config = load_target_config(TARGET_CONFIG_PATH)
        paths, hashes = verify_target_inputs(config, REPO_ROOT)
        self.assertEqual(config["target"]["included_week_offsets"], list(range(1, 9)))
        self.assertFalse(config["target"]["issue_week_included"])
        self.assertTrue(config["target"]["does_not_represent_all_tick_borne_diseases"])
        self.assertEqual(set(paths), set(hashes))

    def test_combined_target_is_exact_component_sum_and_excludes_t(self) -> None:
        start = date(2024, 12, 2)
        weeks = tuple(start + timedelta(weeks=offset) for offset in range(10))
        components = {
            ("01", week): (offset + 1, 100 + offset)
            for offset, week in enumerate(weeks)
        }
        rows = construct_target_rows(("01",), weeks, components)
        first = rows[0]
        expected_lyme = sum(offset + 1 for offset in range(1, 9))
        expected_kme = sum(100 + offset for offset in range(1, 9))
        self.assertEqual(first.lyme_target, expected_lyme)
        self.assertEqual(first.kme_target, expected_kme)
        self.assertEqual(first.combined_target, expected_lyme + expected_kme)
        self.assertNotEqual(first.combined_target, sum(components[("01", weeks[0])]))
        self.assertEqual(first.target_start, first.issue_week + timedelta(weeks=1))
        self.assertEqual(first.target_end, first.issue_week + timedelta(weeks=8))
        self.assertTrue(first.training_eligible)
        self.assertFalse(rows[-1].training_eligible)
        self.assertIsNone(rows[-1].combined_target)

    def test_model_comparison_and_selection_are_frozen(self) -> None:
        config = load_model_config(MODEL_CONFIG_PATH)
        paths, hashes = verify_model_inputs(config, REPO_ROOT)
        self.assertEqual(set(paths), set(hashes))
        self.assertEqual(
            tuple(system["candidate_id"] for system in config["systems"]),
            PUBLIC_SYSTEM_IDS,
        )
        selection = json.loads(
            (MODEL_OUTPUT / "tick_borne_combined_model_selection.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(selection["selected_candidate_id"], "glm_past_combined_offset")
        self.assertFalse(selection["catboost_promoted"])
        self.assertEqual(selection["catboost_n_folds_improving_vs_best_non_ml"], 7)
        self.assertEqual(selection["n_compared_folds"], 8)

    def test_rolling_folds_use_target_end_boundaries(self) -> None:
        path = MODEL_OUTPUT / "tick_borne_combined_fold_manifest.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            folds = list(csv.DictReader(handle))
        self.assertEqual(len(folds), 8)
        self.assertEqual([int(row["validation_iso_year"]) for row in folds], list(range(2018, 2026)))
        for row in folds:
            self.assertLess(
                date.fromisoformat(row["train_target_end_max"]),
                date.fromisoformat(row["validation_start"]),
            )
            self.assertEqual(int(row["target_embargo_weeks"]), 8)
            self.assertGreater(int(row["n_purged_target_boundary"]), 0)

    def test_feature_availability_is_strictly_backward_looking(self) -> None:
        path = MODEL_OUTPUT / "tick_borne_combined_feature_panel.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreater(len(rows), 0)
        for source in rows:
            issue = date.fromisoformat(source["issue_week"])
            self.assertEqual(
                date.fromisoformat(source["latest_past_case_week_used"]),
                issue - timedelta(weeks=1),
            )
            self.assertLess(date.fromisoformat(source["latest_weather_week_end"]), issue)
            self.assertLess(int(source["population_year_max"]), issue.year)

    def test_freeze_manifest_matches_current_code_and_artifacts(self) -> None:
        config = load_freeze_config(FREEZE_CONFIG_PATH)
        manifest = json.loads(
            (FREEZE_OUTPUT / "tick_borne_combined_freeze_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "FROZEN_COMBINED_MODEL_2026_OUTCOMES_UNOPENED")
        self.assertEqual(manifest["selected_model"]["candidate_id"], "glm_past_combined_offset")
        self.assertTrue(manifest["fit"]["converged"])
        self.assertEqual(manifest["fit"]["n_training_rows"], 6651)
        self.assertEqual(manifest["fit"]["warning_count"], 0)
        self.assertFalse(manifest["checks"]["2026_outcomes_accessed"])
        self.assertFalse(manifest["checks"]["weather_required_for_final_fit_row"])
        self.assertEqual(manifest["configuration"]["sha256"], sha256_file(FREEZE_CONFIG_PATH))
        self.assertEqual(
            manifest["code"]["sha256"],
            sha256_file(
                REPO_ROOT
                / "model_v3"
                / "models"
                / "tick_borne_combined_model_freeze.py"
            ),
        )
        self.assertEqual(config["task"]["composite_scope"], "reported_Lyme_plus_KME_only_not_all_tick_borne_diseases")

    def test_frozen_design_includes_past_combined_incidence(self) -> None:
        manifest = json.loads(
            (FREEZE_OUTPUT / "tick_borne_combined_freeze_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            "z_past_8w_reported_lyme_plus_kme_incidence_per_100000",
            manifest["fit"]["design_columns"],
        )
        self.assertNotIn("weather", " ".join(manifest["fit"]["design_columns"]))

    def test_snapshot_schema_and_json_parquet_parity(self) -> None:
        config = load_prediction_config(PREDICTION_CONFIG_PATH)
        paths, hashes = verify_prediction_inputs(config, REPO_ROOT)
        self.assertEqual(set(paths), set(hashes))
        table = pq.read_table(SNAPSHOT_OUTPUT / "prediction_snapshot.parquet")
        self.assertEqual(table.schema, SNAPSHOT_SCHEMA)
        self.assertEqual(table.num_rows, 12)
        self.assertEqual(len(set(table["statistical_region_code"].to_pylist())), 12)
        self.assertFalse(FORBIDDEN_FIELDS.intersection(SNAPSHOT_COLUMNS))
        self.assertTrue(all(value >= 0 for value in table["predicted_cases"].to_pylist()))
        self.assertEqual(table["lower_interval"].null_count, 12)
        self.assertEqual(table["upper_interval"].null_count, 12)
        json_rows = json.loads(
            (SNAPSHOT_OUTPUT / "prediction_snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(json_rows), 12)
        self.assertEqual(tuple(json_rows[0]), SNAPSHOT_COLUMNS)
        self.assertTrue(all(row["issue_date"] == "2025-12-29" for row in json_rows))
        self.assertTrue(
            all(
                math.isfinite(row["predicted_cases"]) and row["predicted_cases"] >= 0
                for row in json_rows
            )
        )

    def test_snapshot_quality_records_no_outcome_access(self) -> None:
        quality = json.loads(
            (SNAPSHOT_OUTPUT / "prediction_snapshot_quality.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(quality["checks"]["2026_outcomes_read"])
        self.assertFalse(quality["checks"]["2026_targets_created"])
        self.assertTrue(quality["checks"]["past_cases_exactly_t_minus_8_through_t_minus_1"])
        self.assertEqual(quality["canonical_table"]["target_window_start"], "2026-01-05")
        self.assertEqual(quality["canonical_table"]["target_window_end"], "2026-02-23")
        for label in ("json", "parquet", "contract"):
            record = quality["outputs"][label]
            self.assertEqual(record["sha256"], sha256_file(REPO_ROOT / record["path"]))

    def test_protected_rows_are_skipped_before_numeric_parsing(self) -> None:
        issue = date(2025, 12, 29)
        mapping = {"001": "01"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weekly.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["municipality_code", "issue_week", "lyme_cases", "kme_cases"],
                )
                writer.writeheader()
                for offset in range(-8, 0):
                    writer.writerow(
                        {
                            "municipality_code": "001",
                            "issue_week": (issue + timedelta(weeks=offset)).isoformat(),
                            "lyme_cases": "1",
                            "kme_cases": "2",
                        }
                    )
                writer.writerow(
                    {
                        "municipality_code": "NOT_PARSED",
                        "issue_week": "2026-01-05",
                        "lyme_cases": "protected_not_numeric",
                        "kme_cases": "protected_not_numeric",
                    }
                )
            regional, skipped = read_required_past_cases(path, mapping, issue)
        self.assertEqual(regional, {"01": 24})
        self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
