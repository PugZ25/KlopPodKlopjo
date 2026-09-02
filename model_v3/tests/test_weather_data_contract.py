from __future__ import annotations

import json
import unittest
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "weather_data_contract.json"
)


class WeatherDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_authorizes_only_cutoff_bounded_retrospective_use(self) -> None:
        self.assertEqual(
            self.contract["status"],
            "implemented_for_retrospective_development_through_verified_weather_cutoff",
        )
        self.assertTrue(
            self.contract["gate_checks"]["weather_feature_pipeline_authorized"]
        )
        self.assertTrue(self.contract["gate_checks"]["model_ablation_authorized"])
        self.assertFalse(
            self.contract["gate_checks"]["post_cutoff_operational_inference_authorized"]
        )
        self.assertTrue(self.contract["implementation"]["weather_features_created"])
        self.assertTrue(self.contract["implementation"]["four_arm_ablation_run"])
        self.assertTrue(
            self.contract["implementation"]["catboost_weather_model_trained"]
        )

    def test_training_and_inference_use_same_final_product_through_cutoff(self) -> None:
        source = self.contract["source"]
        self.assertEqual(source["required_expver"], "0001")
        self.assertEqual(
            source["training_source"],
            "same_verified_local_final_ERA5_Land_archive",
        )
        self.assertEqual(
            source["inference_source"],
            "same_verified_local_final_ERA5_Land_archive_up_to_its_cutoff",
        )
        self.assertFalse(source["preliminary_expver_0005_used"])

    def test_variable_schema_and_units_match_verified_raw_archive(self) -> None:
        observed = {
            row["source_short_name"]: row["source_unit"]
            for row in self.contract["variables"]
        }
        self.assertEqual(
            observed,
            {
                "t2m": "K",
                "d2m": "K",
                "tp": "m_of_water_equivalent_accumulated_from_00_UTC",
                "stl1": "K",
                "stl2": "K",
                "swvl1": "m3_m-3",
                "swvl2": "m3_m-3",
            },
        )

    def test_lockbox_was_not_opened(self) -> None:
        audit = self.contract["development_metadata_audit"]
        self.assertEqual(audit["last_file"], "era5land_slovenia_2024_12.nc")
        self.assertEqual(audit["files_from_lockbox_year_opened"], 0)
        self.assertFalse(self.contract["gate_checks"]["lockbox_weather_files_opened"])
        self.assertFalse(
            self.contract["gate_checks"]["lockbox_epidemiological_data_opened"]
        )

    def test_lags_use_only_completed_weeks_before_issue_week(self) -> None:
        features = self.contract["feature_contract"]
        self.assertEqual(
            features["lag_1_completed_week"], "t_minus_1"
        )
        self.assertEqual(features["lag_2_completed_week"], "t_minus_2")
        self.assertEqual(
            features["rolling_previous_4_completed_weeks"],
            "t_minus_4_through_t_minus_1",
        )
        self.assertFalse(features["current_week_allowed"])
        self.assertFalse(features["future_weather_allowed"])

    def test_weather_cutoff_and_fixed_municipalities_are_explicit(self) -> None:
        scope = self.contract["scope"]
        self.assertEqual(scope["weather_cutoff"], "2024-12-31T23:00:00Z")
        self.assertIn("no_additional_publication_embargo", scope["availability_rule"])
        self.assertIn("do_not_extrapolate", scope["post_cutoff_rule"])
        municipalities = self.contract["municipality_contract"]
        self.assertTrue(municipalities["fixed_analytical_zones_all_years"])
        self.assertFalse(municipalities["historical_boundary_reconstruction"])
        self.assertEqual(municipalities["municipality_count"], 212)


if __name__ == "__main__":
    unittest.main()
