from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from model_v3.models.kme_region_model import sha256_file
from model_v3.predict.kme_prediction_snapshot import (
    DEFAULT_CONFIG_PATH,
    FORBIDDEN_OUTPUT_COLUMNS,
    REPO_ROOT,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_SCHEMA,
    KmePredictionSnapshotError,
    build_snapshot_table,
    json_compatible,
    load_config,
    verify_inputs,
)


OUTPUT_ROOT = REPO_ROOT / "model_v3" / "outputs" / "kme_prediction_snapshot" / "v1"


class KmePredictionSnapshotTests(unittest.TestCase):
    def test_config_and_input_hashes_are_frozen(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        paths, hashes = verify_inputs(config, REPO_ROOT)
        self.assertEqual(config["selection"]["horizon_weeks"], 8)
        self.assertEqual(
            config["selection"]["selected_model_id"], "glm_seasonal_region_offset"
        )
        self.assertEqual(set(paths), set(hashes))
        self.assertFalse(FORBIDDEN_OUTPUT_COLUMNS.intersection(SNAPSHOT_COLUMNS))

    def test_canonical_snapshot_has_exact_regional_coverage(self) -> None:
        table, context = build_snapshot_table(load_config(DEFAULT_CONFIG_PATH), REPO_ROOT)
        self.assertEqual(table.schema, SNAPSHOT_SCHEMA)
        self.assertEqual(table.num_rows, 12)
        self.assertEqual(context["issue_date"], date(2026, 8, 24))
        self.assertEqual(context["seal_date"], date(2026, 8, 30))
        self.assertEqual(
            len(set(table["statistical_region_code"].to_pylist())), table.num_rows
        )
        self.assertTrue(all(value == 8 for value in table["horizon_weeks"].to_pylist()))
        self.assertTrue(all(value >= 0 for value in table["predicted_cases"].to_pylist()))
        self.assertEqual(table["lower_interval"].null_count, 12)
        self.assertEqual(table["upper_interval"].null_count, 12)

    def test_snapshot_values_match_selected_sealed_predictions(self) -> None:
        table, _context = build_snapshot_table(load_config(DEFAULT_CONFIG_PATH), REPO_ROOT)
        snapshot = {
            row["statistical_region_code"]: row for row in table.to_pylist()
        }
        selected: dict[str, dict[str, str]] = {}
        source_path = (
            REPO_ROOT
            / "model_v3"
            / "outputs"
            / "kme_prediction_seal"
            / "kme_2026_sealed_predictions.csv"
        )
        with source_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (
                    row["candidate_id"] == "glm_seasonal_region_offset"
                    and row["issue_week"] == "2026-08-24"
                ):
                    selected[row["statistical_region_code"]] = row
        self.assertEqual(set(snapshot), set(selected))
        for code, output in snapshot.items():
            source = selected[code]
            self.assertEqual(output["statistical_region_name"], source["statistical_region_name"])
            self.assertEqual(output["model_version"], source["model_version"])
            self.assertEqual(output["data_version"], source["data_version"])
            self.assertTrue(
                math.isclose(
                    output["predicted_cases"],
                    float(source["predicted_cases"]),
                    rel_tol=0,
                    abs_tol=0,
                )
            )

    def test_json_and_parquet_outputs_have_exact_parity(self) -> None:
        parquet_rows = pq.read_table(OUTPUT_ROOT / "prediction_snapshot.parquet").to_pylist()
        expected_json = [
            {key: json_compatible(value) for key, value in row.items()}
            for row in parquet_rows
        ]
        actual_json = json.loads(
            (OUTPUT_ROOT / "prediction_snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(actual_json, expected_json)
        self.assertEqual(tuple(actual_json[0]), SNAPSHOT_COLUMNS)

    def test_quality_summary_records_lineage_and_protections(self) -> None:
        quality = json.loads(
            (OUTPUT_ROOT / "prediction_snapshot_quality.json").read_text(encoding="utf-8")
        )
        self.assertEqual(quality["canonical_table"]["row_count"], 12)
        self.assertEqual(quality["canonical_table"]["issue_date"], "2026-08-24")
        self.assertFalse(quality["checks"]["2026_KME_outcomes_read"])
        self.assertTrue(quality["checks"]["selected_model_only"])
        self.assertTrue(quality["checks"]["outcomes_excluded"])
        self.assertEqual(
            quality["configuration"]["sha256"], sha256_file(DEFAULT_CONFIG_PATH)
        )
        self.assertEqual(
            quality["code"]["sha256"],
            sha256_file(
                REPO_ROOT / "model_v3" / "predict" / "kme_prediction_snapshot.py"
            ),
        )
        for label in ("json", "parquet"):
            record = quality["outputs"][label]
            self.assertEqual(
                record["sha256"], sha256_file(REPO_ROOT / record["path"])
            )

    def test_input_hash_mismatch_is_rejected(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        config["inputs"]["sealed_predictions_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            with self.assertRaisesRegex(
                KmePredictionSnapshotError, "sealed_predictions SHA-256 mismatch"
            ):
                verify_inputs(loaded, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
