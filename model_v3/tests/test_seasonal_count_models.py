from __future__ import annotations

import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from model_v3.models.seasonal_count_models import (
    MODEL_S1,
    MODEL_S2,
    MODEL_S3,
    ModelRow,
    PastIncidence,
    build_population_history,
    build_design_matrix,
    calculate_past_incidence,
    fit_poisson_model,
    make_design_spec,
    prepare_model_rows,
    prediction_arrays,
    read_development_population,
    read_development_target_metadata,
    seasonal_terms,
    select_population_exposure,
)
from model_v3.validation.rolling_origin import TargetWindowRow


def make_model_row(
    *,
    municipality_code: str,
    issue_week: date,
    population: int,
    target: int,
    past_count: int = 1,
) -> ModelRow:
    seasonal_sin, seasonal_cos = seasonal_terms(issue_week)
    return ModelRow(
        municipality_code=municipality_code,
        issue_week=issue_week,
        target_window_start=issue_week + timedelta(weeks=1),
        target_window_end=issue_week + timedelta(weeks=4),
        target_value=target,
        population=population,
        population_year=issue_week.year - 1,
        seasonal_sin=seasonal_sin,
        seasonal_cos=seasonal_cos,
        past_incidence=PastIncidence(
            case_count=past_count,
            incidence_per_100000=past_count / population * 100000.0,
            status="available",
            window_start=issue_week - timedelta(weeks=4),
            window_end=issue_week - timedelta(weeks=1),
            latest_information_week=issue_week - timedelta(weeks=1),
        ),
    )


class SeasonalDesignTests(unittest.TestCase):
    def test_population_is_exposure_not_an_ordinary_design_column(self) -> None:
        issue_week = date(2020, 4, 6)
        rows = [
            make_model_row(
                municipality_code="001",
                issue_week=issue_week,
                population=100,
                target=1,
            ),
            make_model_row(
                municipality_code="001",
                issue_week=issue_week,
                population=200,
                target=2,
            ),
        ]
        spec = make_design_spec(MODEL_S1, rows)
        matrix = build_design_matrix(rows, spec)

        self.assertEqual(
            spec.column_names,
            ("intercept", "seasonal_sin_annual", "seasonal_cos_annual"),
        )
        np.testing.assert_allclose(matrix[0], matrix[1])
        self.assertNotIn("population", spec.column_names)

    def test_municipality_effects_are_deterministically_treatment_coded(self) -> None:
        issue_week = date(2020, 4, 6)
        rows = [
            make_model_row(
                municipality_code=code,
                issue_week=issue_week,
                population=100,
                target=1,
            )
            for code in ("003", "001", "002")
        ]
        spec = make_design_spec(MODEL_S2, rows)
        matrix = build_design_matrix(rows, spec)

        self.assertEqual(spec.municipality_reference, "001")
        self.assertEqual(spec.municipality_levels, ("001", "002", "003"))
        self.assertEqual(spec.column_names[-2:], ("municipality[002]", "municipality[003]"))
        self.assertEqual(matrix[1, -2:].tolist(), [0.0, 0.0])
        self.assertEqual(matrix[2, -2:].tolist(), [1.0, 0.0])
        self.assertEqual(matrix[0, -2:].tolist(), [0.0, 1.0])

    def test_s3_design_contains_past_incidence_as_separate_predictor(self) -> None:
        row = make_model_row(
            municipality_code="001",
            issue_week=date(2020, 4, 6),
            population=10000,
            target=2,
            past_count=3,
        )
        spec = make_design_spec(MODEL_S3, [row])
        matrix = build_design_matrix([row], spec)

        self.assertEqual(spec.column_names[-1], "past_4w_lyme_incidence_per_100000")
        self.assertAlmostEqual(matrix[0, -1], 30.0)

    def test_annual_harmonic_is_derived_only_from_issue_date(self) -> None:
        self.assertEqual(seasonal_terms(date(2021, 1, 1)), (0.0, 1.0))
        leap_terms = seasonal_terms(date(2020, 12, 28))
        ordinary_terms = seasonal_terms(date(2021, 12, 27))
        self.assertTrue(all(math.isfinite(value) for value in leap_terms + ordinary_terms))


class PastIncidenceAvailabilityTests(unittest.TestCase):
    def test_past_incidence_uses_exactly_t_minus_4_through_t_minus_1(self) -> None:
        issue_week = date(2020, 2, 3)
        weekly_cases = {
            ("001", issue_week - timedelta(weeks=4)): 1,
            ("001", issue_week - timedelta(weeks=3)): 2,
            ("001", issue_week - timedelta(weeks=2)): 3,
            ("001", issue_week - timedelta(weeks=1)): 4,
            ("001", issue_week): 1000,
            ("001", issue_week + timedelta(weeks=1)): 2000,
        }
        result = calculate_past_incidence(
            weekly_cases,
            municipality_code="001",
            issue_week=issue_week,
            population=10000,
        )

        self.assertEqual(result.case_count, 10)
        self.assertAlmostEqual(result.incidence_per_100000 or -1, 100.0)
        self.assertEqual(result.window_start, issue_week - timedelta(weeks=4))
        self.assertEqual(result.window_end, issue_week - timedelta(weeks=1))
        self.assertLess(result.latest_information_week, issue_week)

    def test_current_and_future_cases_cannot_change_past_incidence(self) -> None:
        issue_week = date(2020, 2, 3)
        base = {
            ("001", issue_week - timedelta(weeks=offset)): offset
            for offset in (4, 3, 2, 1)
        }
        changed = dict(base)
        changed[("001", issue_week)] = 9999
        changed[("001", issue_week + timedelta(weeks=1))] = 9999

        expected = calculate_past_incidence(
            base,
            municipality_code="001",
            issue_week=issue_week,
            population=10000,
        )
        observed = calculate_past_incidence(
            changed,
            municipality_code="001",
            issue_week=issue_week,
            population=10000,
        )
        self.assertEqual(observed, expected)

    def test_missing_prior_week_is_not_converted_to_zero(self) -> None:
        issue_week = date(2020, 2, 3)
        weekly_cases = {
            ("001", issue_week - timedelta(weeks=offset)): 1
            for offset in (4, 3, 1)
        }
        result = calculate_past_incidence(
            weekly_cases,
            municipality_code="001",
            issue_week=issue_week,
            population=10000,
        )
        self.assertEqual(result.status, "missing_prior_week")
        self.assertIsNone(result.case_count)
        self.assertIsNone(result.incidence_per_100000)


class OffsetAndPredictionTests(unittest.TestCase):
    def test_identical_design_predictions_scale_with_population_exposure(self) -> None:
        start = date(2018, 1, 1)
        training_rows = [
            make_model_row(
                municipality_code="001",
                issue_week=start + timedelta(weeks=index * 5),
                population=10000 + index * 100,
                target=1 + (index % 4),
            )
            for index in range(12)
        ]
        fitted = fit_poisson_model(training_rows, model_id=MODEL_S1)
        issue_week = date(2020, 4, 6)
        validation_rows = [
            make_model_row(
                municipality_code="001",
                issue_week=issue_week,
                population=10000,
                target=1,
            ),
            make_model_row(
                municipality_code="001",
                issue_week=issue_week,
                population=20000,
                target=1,
            ),
        ]
        predictions = prediction_arrays(fitted, validation_rows)

        self.assertTrue(fitted.result.converged)
        self.assertAlmostEqual(predictions["mean"][1] / predictions["mean"][0], 2.0)
        self.assertTrue(
            np.all(predictions["predictive_lower"] <= predictions["mean"])
        )
        self.assertTrue(
            np.all(predictions["predictive_upper"] >= predictions["mean"])
        )


class LockboxReaderTests(unittest.TestCase):
    def test_target_metadata_reader_excludes_2025_before_normalization(self) -> None:
        content = "\n".join(
            [
                "municipality_code,issue_week,target_lyme_cases_next_4w,target_window_start,target_window_end,target_status,target_training_eligible",
                "001,2024-01-01,2,2024-01-08,2024-01-29,complete,true",
                "NOT_A_CODE,2025-01-06,SECRET,NOT_A_DATE,NOT_A_DATE,SECRET,SECRET",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "targets.csv"
            path.write_text(content + "\n", encoding="utf-8")
            rows = read_development_target_metadata(
                path, development_start_year=2016, development_end_year=2024
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].issue_week, date(2024, 1, 1))

    def test_population_reader_excludes_2025_before_value_parsing(self) -> None:
        content = "\n".join(
            [
                "municipality_code,year,population",
                "001,2024,10000",
                "NOT_A_CODE,2025,SECRET",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "population.csv"
            path.write_text(content + "\n", encoding="utf-8")
            values = read_development_population(path, lockbox_year=2025)
        self.assertEqual(values, {("001", 2024): 10000})


class PopulationAvailabilitySafeguardTests(unittest.TestCase):
    def test_previous_year_is_selected_over_issue_and_future_years(self) -> None:
        history = build_population_history(
            {
                ("001", 2020): 9000,
                ("001", 2021): 10000,
                ("001", 2022): 20000,
                ("001", 2023): 30000,
            }
        )

        selected = select_population_exposure(
            history,
            municipality_code="001",
            issue_week=date(2022, 6, 6),
        )

        self.assertEqual(selected.year, 2021)
        self.assertEqual(selected.population, 10000)

    def test_missing_previous_year_falls_back_to_latest_earlier_year(self) -> None:
        history = build_population_history(
            {
                ("001", 2019): 8000,
                ("001", 2020): 9000,
                ("001", 2022): 20000,
            }
        )

        selected = select_population_exposure(
            history,
            municipality_code="001",
            issue_week=date(2022, 6, 6),
        )

        self.assertEqual(selected.year, 2020)
        self.assertEqual(selected.population, 9000)

    def test_missing_earlier_population_is_rejected(self) -> None:
        history = build_population_history({("001", 2022): 20000})

        with self.assertRaisesRegex(
            ValueError, "No present population value strictly before the issue year"
        ):
            select_population_exposure(
                history,
                municipality_code="001",
                issue_week=date(2022, 6, 6),
            )

    def test_offset_and_s3_denominator_share_selected_population(self) -> None:
        issue_week = date(2022, 6, 6)
        target_row = TargetWindowRow(
            municipality_code="001",
            issue_week=issue_week,
            target_window_start=issue_week + timedelta(weeks=1),
            target_window_end=issue_week + timedelta(weeks=4),
            target_status="complete",
            target_training_eligible=True,
        )
        weekly_cases = {
            ("001", issue_week - timedelta(weeks=offset)): value
            for offset, value in zip((4, 3, 2, 1), (1, 2, 3, 4), strict=True)
        }

        prepared = prepare_model_rows(
            [target_row],
            {("001", issue_week): 5},
            {
                ("001", 2021): 10000,
                ("001", 2022): 20000,
            },
            weekly_cases,
        )[0]

        self.assertEqual(prepared.population_year, 2021)
        self.assertEqual(prepared.population, 10000)
        self.assertEqual(prepared.past_incidence.case_count, 10)
        self.assertAlmostEqual(
            prepared.past_incidence.incidence_per_100000 or -1,
            100.0,
        )


if __name__ == "__main__":
    unittest.main()
