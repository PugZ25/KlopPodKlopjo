from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from model_v3.models.static_geography_ablation import (
    AUGMENTED_COLUMNS,
    AUGMENTED_ID,
    BASE_COLUMNS,
    CONTROL_ID,
    AblationRow,
    StaticGeographyAblationError,
    build_design_matrix,
    classify_metric_delta,
    design_columns,
    read_phase_9_s1_predictions,
)


def fixture_row(*, area: float = 100.0) -> AblationRow:
    return AblationRow(
        municipality_code="001",
        issue_week=date(2020, 1, 6),
        target_window_start=date(2020, 1, 13),
        target_window_end=date(2020, 2, 3),
        target_value=4,
        population=20_000,
        population_year=2019,
        seasonal_sin=0.1,
        seasonal_cos=0.9,
        municipality_area_km2=area,
    )


class StaticGeographyAblationTests(unittest.TestCase):
    def test_control_design_is_exact_s1_design(self) -> None:
        self.assertEqual(
            design_columns(CONTROL_ID),
            ("intercept", "seasonal_sin_annual", "seasonal_cos_annual"),
        )
        self.assertEqual(design_columns(CONTROL_ID), BASE_COLUMNS)

    def test_augmented_design_only_appends_area(self) -> None:
        self.assertEqual(AUGMENTED_COLUMNS[:-1], BASE_COLUMNS)
        self.assertEqual(AUGMENTED_COLUMNS[-1], "municipality_area_km2")

    def test_area_changes_augmented_but_not_control_matrix(self) -> None:
        first = fixture_row(area=100.0)
        second = fixture_row(area=250.0)

        np.testing.assert_array_equal(
            build_design_matrix([first], CONTROL_ID),
            build_design_matrix([second], CONTROL_ID),
        )
        self.assertNotEqual(
            build_design_matrix([first], AUGMENTED_ID)[0, 3],
            build_design_matrix([second], AUGMENTED_ID)[0, 3],
        )

    def test_population_is_not_an_ordinary_design_column(self) -> None:
        self.assertNotIn("population", BASE_COLUMNS)
        self.assertNotIn("population", AUGMENTED_COLUMNS)

    def test_lower_metric_delta_is_improvement(self) -> None:
        self.assertEqual(classify_metric_delta(-0.01), "improvement")
        self.assertEqual(classify_metric_delta(0.01), "deterioration")
        self.assertEqual(classify_metric_delta(0.0), "no_change")

    def test_reference_loader_rejects_lockbox_before_numeric_parsing(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "predictions.csv"
            path.write_text(
                "fold_id,model_id,municipality_code,issue_week,"
                "predicted_target_lyme_cases_next_4w\n"
                "fold_lockbox,model_s1_seasonality_offset,NOT_A_CODE,"
                "2025-01-06,NOT_A_NUMBER\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                StaticGeographyAblationError, "lockbox issue week"
            ):
                read_phase_9_s1_predictions(path, lockbox_year=2025)


if __name__ == "__main__":
    unittest.main()
