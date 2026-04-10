from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from ml.training.config import load_config
from ml.training.dataset import prepare_dataset
from ml.training.splits import build_time_splits


class TrainingPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.dataset_path = self.temp_path / "training.csv"
        self.config_path = self.temp_path / "config.json"
        self.repo_root = Path(__file__).resolve().parents[2]

        self.dataset_path.write_text(
            textwrap.dedent(
                """\
                time,obcina_sifra,obcina_naziv,assignment_method,air_temperature_c,relative_humidity_pct,grid_cell_count,target_risk_score
                2026-04-01 00:00:00,143,Zavrc,point_in_polygon,10.5,75.0,1,34.0
                2026-04-01 00:00:00,1,Ajdovscina,point_in_polygon,14.1,60.0,3,28.0
                2026-04-02 00:00:00,143,Zavrc,point_in_polygon,11.0,74.0,1,35.0
                2026-04-02 00:00:00,1,Ajdovscina,point_in_polygon,15.2,,3,29.0
                2026-04-03 00:00:00,143,Zavrc,nearest_centroid_fallback,9.7,81.0,1,41.0
                2026-04-03 00:00:00,1,Ajdovscina,point_in_polygon,13.8,65.0,3,30.0
                2026-04-04 00:00:00,143,Zavrc,nearest_centroid_fallback,8.9,85.0,1,43.0
                2026-04-04 00:00:00,1,Ajdovscina,point_in_polygon,12.6,67.0,3,31.0
                2026-04-05 00:00:00,143,Zavrc,nearest_centroid_fallback,8.4,87.0,1,45.0
                2026-04-05 00:00:00,1,Ajdovscina,point_in_polygon,12.1,69.0,3,32.0
                2026-04-06 00:00:00,143,Zavrc,nearest_centroid_fallback,7.9,90.0,1,48.0
                2026-04-06 00:00:00,1,Ajdovscina,point_in_polygon,11.4,70.0,3,33.0
                """
            ),
            encoding="utf-8",
        )

        self.config_path.write_text(
            json.dumps(
                {
                    "dataset_path": "training.csv",
                    "output_dir": "artifacts/run_1",
                    "target_column": "target_risk_score",
                    "time_column": "time",
                    "problem_type": "regression",
                    "categorical_columns": [
                        "obcina_sifra",
                        "obcina_naziv",
                        "assignment_method",
                    ],
                    "id_columns": ["obcina_sifra", "obcina_naziv"],
                    "ignore_columns": [],
                    "split": {
                        "train_ratio": 0.67,
                        "validation_ratio": 0.17,
                        "test_ratio": 0.16,
                    },
                    "catboost": {
                        "iterations": 20,
                        "learning_rate": 0.1,
                        "depth": 4,
                        "verbose": 10,
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_load_config_resolves_paths_relative_to_config(self) -> None:
        config = load_config(self.config_path)

        self.assertEqual(config.dataset_path, self.dataset_path.resolve())
        self.assertEqual(
            config.output_dir,
            (self.temp_path / "artifacts/run_1").resolve(),
        )

    def test_load_config_supports_binary_classification_weights(self) -> None:
        self.config_path.write_text(
            json.dumps(
                {
                    "dataset_path": "training.csv",
                    "output_dir": "artifacts/run_2",
                    "target_column": "target_kme_presence",
                    "time_column": "time",
                    "problem_type": "binary_classification",
                    "feature_columns": [
                        "obcina_sifra",
                        "assignment_method",
                        "air_temperature_c",
                    ],
                    "categorical_columns": [
                        "obcina_sifra",
                        "assignment_method",
                    ],
                    "id_columns": ["obcina_sifra", "obcina_naziv"],
                    "ignore_columns": [],
                    "catboost": {
                        "iterations": 10,
                        "auto_class_weights": "Balanced",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        config = load_config(self.config_path)

        self.assertEqual(config.problem_type, "binary_classification")
        self.assertEqual(config.catboost.auto_class_weights, "Balanced")

    def test_prepare_dataset_infers_features_and_categorical_indices(self) -> None:
        config = load_config(self.config_path)
        dataset = prepare_dataset(config)

        self.assertEqual(
            dataset.feature_columns,
            [
                "obcina_sifra",
                "obcina_naziv",
                "assignment_method",
                "air_temperature_c",
                "relative_humidity_pct",
                "grid_cell_count",
            ],
        )
        self.assertEqual(dataset.cat_feature_indices, [0, 1, 2])
        self.assertTrue(math.isnan(dataset.features[3][4]))

    def test_build_time_splits_keeps_shared_timestamps_together(self) -> None:
        config = load_config(self.config_path)
        dataset = prepare_dataset(config)
        splits = build_time_splits(dataset.timestamps, config.split)

        self.assertEqual(splits["train"].unique_time_count, 4)
        self.assertEqual(splits["validation"].unique_time_count, 1)
        self.assertEqual(splits["test"].unique_time_count, 1)
        self.assertEqual(splits["train"].row_count, 8)
        self.assertEqual(splits["validation"].row_count, 2)
        self.assertEqual(splits["test"].row_count, 2)

        train_times = set(splits["train"].unique_times)
        validation_times = set(splits["validation"].unique_times)
        test_times = set(splits["test"].unique_times)
        self.assertTrue(train_times.isdisjoint(validation_times))
        self.assertTrue(train_times.isdisjoint(test_times))
        self.assertTrue(validation_times.isdisjoint(test_times))

    def test_validate_only_cli_smoke(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ml.training.train",
                "--config",
                str(self.config_path),
                "--validate-only",
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Validation complete.", result.stdout)
        self.assertIn('"row_count": 12', result.stdout)


if __name__ == "__main__":
    unittest.main()
