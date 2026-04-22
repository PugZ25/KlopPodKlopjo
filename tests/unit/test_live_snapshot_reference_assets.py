from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.data.build_live_municipality_risk_frontend_data import (
    MODEL_SPECS,
    MUNICIPALITY_COORDINATES_PATH,
    MUNICIPALITY_STATIC_FEATURES_PATH,
    load_coordinate_lookup,
)


class LiveSnapshotReferenceAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.coordinates = load_coordinate_lookup()
        cls.static_features = json.loads(
            MUNICIPALITY_STATIC_FEATURES_PATH.read_text(encoding="utf-8")
        )

    def test_municipality_reference_files_cover_same_codes(self) -> None:
        self.assertEqual(set(self.coordinates), set(self.static_features))
        self.assertGreaterEqual(len(self.coordinates), 200)

    def test_coordinate_payload_is_two_dimensional(self) -> None:
        payload = json.loads(MUNICIPALITY_COORDINATES_PATH.read_text(encoding="utf-8"))
        for municipality_code, coordinates in payload.items():
            with self.subTest(municipality_code=municipality_code):
                self.assertEqual(len(coordinates), 2)
                self.assertIsInstance(coordinates[0], float)
                self.assertIsInstance(coordinates[1], float)

    def test_model_reference_artifacts_are_present_and_consistent(self) -> None:
        for spec in MODEL_SPECS:
            with self.subTest(model_id=spec.model_id):
                self.assertTrue(spec.model_path.exists())
                self.assertTrue(spec.metadata_path.exists())
                self.assertTrue(spec.holdout_values_path.exists())

                metadata = json.loads(spec.metadata_path.read_text(encoding="utf-8"))
                self.assertTrue(metadata.get("feature_importances"))

                holdout_values = json.loads(
                    spec.holdout_values_path.read_text(encoding="utf-8")
                )
                self.assertGreater(len(holdout_values), 1000)
                self.assertEqual(holdout_values, sorted(holdout_values))


if __name__ == "__main__":
    unittest.main()
