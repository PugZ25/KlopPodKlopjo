from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from model_v3.predict.prediction_snapshot import (
    DEFAULT_CONFIG_PATH,
    FORBIDDEN_OUTPUT_COLUMNS,
    SNAPSHOT_COLUMNS,
    PredictionSnapshotError,
    build_snapshot_table,
    load_config,
    sha256_file,
    write_snapshot_outputs,
)


PREDICTION_FIELDS = (
    "system_type",
    "candidate_id",
    "municipality_code",
    "issue_week",
    "target_window_start",
    "target_window_end",
    "predicted_target_lyme_cases_next_4w",
    "prediction_status",
    "interval_lower",
    "interval_upper",
    "interval_status",
    "population_exposure",
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SnapshotFixture:
    def __init__(self, root: Path, *, blank_population: bool = False) -> None:
        self.root = root
        self.municipality = root / "municipality.csv"
        self.predictions = root / "predictions.csv"
        self.model_config = root / "model.json"
        self.receipt = root / "receipt.json"
        self.output_directory = root / "outputs"

        with self.municipality.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["municipality_code", "municipality_name"]
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"municipality_code": "001", "municipality_name": "Alpha"},
                    {"municipality_code": "002", "municipality_name": "Beta"},
                ]
            )
        self.model_config.write_text('{"fixed": true}\n', encoding="utf-8")

        rows = []
        for issue, start, end in (
            ("2025-01-06", "2025-01-13", "2025-02-03"),
            ("2025-01-13", "2025-01-20", "2025-02-10"),
        ):
            rows.extend(
                [
                    {
                        "system_type": "final_selected_model",
                        "candidate_id": "selected_model",
                        "municipality_code": "001",
                        "issue_week": issue,
                        "target_window_start": start,
                        "target_window_end": end,
                        "predicted_target_lyme_cases_next_4w": "2.5",
                        "prediction_status": "available",
                        "interval_lower": "",
                        "interval_upper": "",
                        "interval_status": "no_intervals",
                        "population_exposure": "10000",
                    },
                    {
                        "system_type": "final_selected_model",
                        "candidate_id": "selected_model",
                        "municipality_code": "002",
                        "issue_week": issue,
                        "target_window_start": start,
                        "target_window_end": end,
                        "predicted_target_lyme_cases_next_4w": "1.0",
                        "prediction_status": "available",
                        "interval_lower": "",
                        "interval_upper": "",
                        "interval_status": "no_intervals",
                        "population_exposure": "" if blank_population else "20000",
                    },
                ]
            )
        with self.predictions.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PREDICTION_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        receipt = {
            "status": "completed",
            "protected_parse_count": 1,
            "rerun_allowed": False,
            "completed_at_utc": "2026-01-02T03:04:05+00:00",
            "output_records": {
                "predictions": {
                    "path": str(self.predictions),
                    "sha256": file_hash(self.predictions),
                }
            },
        }
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")

    def config(self) -> dict[str, object]:
        return {
            "schema_version": "1.0.0",
            "inputs": {
                "selected_model_predictions": str(self.predictions),
                "selected_model_predictions_sha256": file_hash(self.predictions),
                "lockbox_receipt": str(self.receipt),
                "lockbox_receipt_sha256": file_hash(self.receipt),
                "municipality": str(self.municipality),
                "municipality_sha256": file_hash(self.municipality),
                "selected_model_config": str(self.model_config),
                "selected_model_config_sha256": file_hash(self.model_config),
            },
            "selection": {
                "selected_model_id": "selected_model",
                "required_system_type": "final_selected_model",
                "issue_date_rule": "latest",
                "horizon_weeks": 4,
                "expected_municipality_count": 2,
                "required_prediction_status": "available",
                "required_interval_status": "no_intervals",
            },
            "data_status": {
                "valid_denominator": "retrospective_lockbox_evaluation_prediction",
                "invalid_denominator": "retrospective_lockbox_evaluation_prediction_missing_population_denominator",
            },
            "outputs": {
                "directory": str(self.output_directory),
                "parquet": "prediction_snapshot.parquet",
                "json": "prediction_snapshot.json",
                "quality_summary": "prediction_snapshot_quality.json",
            },
        }


class PredictionSnapshotTests(unittest.TestCase):
    def test_default_source_builds_latest_complete_212_municipality_snapshot(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        table, lineage = build_snapshot_table(config)

        self.assertEqual(tuple(table.column_names), SNAPSHOT_COLUMNS)
        self.assertEqual(table.num_rows, 212)
        self.assertEqual(lineage["issue_date"], "2025-11-24")
        self.assertEqual(set(table.column("horizon_weeks").to_pylist()), {4})
        self.assertEqual(table.column("lower_interval").null_count, 212)
        self.assertEqual(table.column("upper_interval").null_count, 212)
        self.assertFalse(FORBIDDEN_OUTPUT_COLUMNS.intersection(table.column_names))

    def test_latest_issue_is_selected_and_incidence_uses_valid_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = SnapshotFixture(Path(directory))
            table, lineage = build_snapshot_table(fixture.config(), Path(directory))

        rows = table.to_pylist()
        self.assertEqual(lineage["issue_date"], "2025-01-13")
        self.assertEqual([row["municipality_code"] for row in rows], ["001", "002"])
        self.assertEqual(rows[0]["issue_date"], date(2025, 1, 13))
        self.assertEqual(
            rows[0]["generated_at"].isoformat(), "2026-01-02T03:04:05+00:00"
        )
        self.assertAlmostEqual(rows[0]["predicted_incidence_per_100k"], 25.0)
        self.assertAlmostEqual(rows[1]["predicted_incidence_per_100k"], 5.0)

    def test_horizon_other_than_four_weeks_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = SnapshotFixture(root)
            config = fixture.config()
            config["selection"]["horizon_weeks"] = 8

            with self.assertRaisesRegex(PredictionSnapshotError, "exactly 4 weeks"):
                build_snapshot_table(config, root)

    def test_missing_population_is_null_not_zero_and_has_explicit_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = SnapshotFixture(Path(directory), blank_population=True)
            table, _lineage = build_snapshot_table(fixture.config(), Path(directory))

        row = table.to_pylist()[1]
        self.assertIsNone(row["predicted_incidence_per_100k"])
        self.assertEqual(
            row["data_status"],
            "retrospective_lockbox_evaluation_prediction_missing_population_denominator",
        )

    def test_json_and_parquet_are_round_trip_identical_from_one_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = SnapshotFixture(root)
            config = fixture.config()
            table, lineage = build_snapshot_table(config, root)
            quality = write_snapshot_outputs(table, config, lineage, root)

            parquet_table = pq.read_table(fixture.output_directory / "prediction_snapshot.parquet")
            payload = json.loads(
                (fixture.output_directory / "prediction_snapshot.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertEqual(len(payload["predictions"]), parquet_table.num_rows)
        self.assertTrue(quality["checks"]["json_parquet_round_trip_parity"])
        self.assertTrue(quality["checks"]["predictive_intervals_not_fabricated"])

    def test_duplicate_municipality_prediction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = SnapshotFixture(root)
            with fixture.predictions.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PREDICTION_FIELDS)
                writer.writerow(
                    {
                        "system_type": "final_selected_model",
                        "candidate_id": "selected_model",
                        "municipality_code": "001",
                        "issue_week": "2025-01-13",
                        "target_window_start": "2025-01-20",
                        "target_window_end": "2025-02-10",
                        "predicted_target_lyme_cases_next_4w": "2.5",
                        "prediction_status": "available",
                        "interval_lower": "",
                        "interval_upper": "",
                        "interval_status": "no_intervals",
                        "population_exposure": "10000",
                    }
                )
            receipt = json.loads(fixture.receipt.read_text(encoding="utf-8"))
            receipt["output_records"]["predictions"]["sha256"] = file_hash(
                fixture.predictions
            )
            fixture.receipt.write_text(json.dumps(receipt), encoding="utf-8")
            config = fixture.config()

            with self.assertRaisesRegex(PredictionSnapshotError, "Duplicate"):
                build_snapshot_table(config, root)

    def test_hash_mismatch_stops_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = SnapshotFixture(root)
            config = fixture.config()
            config["inputs"]["municipality_sha256"] = "0" * 64

            with self.assertRaisesRegex(PredictionSnapshotError, "SHA-256 mismatch"):
                build_snapshot_table(config, root)

    def test_installed_pyarrow_is_the_pinned_dependency(self) -> None:
        requirements = (
            DEFAULT_CONFIG_PATH.parents[1] / "requirements-prediction.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("pyarrow==25.0.1", requirements)
        self.assertEqual(len(sha256_file(DEFAULT_CONFIG_PATH)), 64)


if __name__ == "__main__":
    unittest.main()
