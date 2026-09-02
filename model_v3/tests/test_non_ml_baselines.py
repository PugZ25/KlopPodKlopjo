from __future__ import annotations

import unittest
from datetime import date, timedelta

from model_v3.models.non_ml_baselines import (
    BaselineValidationError,
    calculate_persistence_prediction,
    poisson_deviance_contribution,
)


class PersistenceBaselineTests(unittest.TestCase):
    def test_persistence_uses_exactly_t_minus_4_through_t_minus_1(self) -> None:
        issue_week = date(2024, 7, 1)
        weekly_cases = {
            ("001", issue_week - timedelta(weeks=4)): 1,
            ("001", issue_week - timedelta(weeks=3)): 2,
            ("001", issue_week - timedelta(weeks=2)): 3,
            ("001", issue_week - timedelta(weeks=1)): 4,
            ("001", issue_week): 100,
            ("001", issue_week + timedelta(weeks=1)): 1_000,
        }

        result = calculate_persistence_prediction(
            weekly_cases,
            municipality_code="001",
            issue_week=issue_week,
        )

        self.assertEqual(result.value, 10)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.n_observed_weeks, 4)
        self.assertEqual(
            result.information_window_start, issue_week - timedelta(weeks=4)
        )
        self.assertEqual(
            result.information_window_end, issue_week - timedelta(weeks=1)
        )
        self.assertEqual(
            result.latest_information_week, issue_week - timedelta(weeks=1)
        )

    def test_current_and_future_case_values_cannot_change_persistence(self) -> None:
        issue_week = date(2024, 8, 5)
        past = {
            ("001", issue_week - timedelta(weeks=offset)): value
            for offset, value in zip((4, 3, 2, 1), (2, 4, 6, 8))
        }
        first = {
            **past,
            ("001", issue_week): 0,
            ("001", issue_week + timedelta(weeks=1)): 0,
        }
        second = {
            **past,
            ("001", issue_week): 10_000,
            ("001", issue_week + timedelta(weeks=1)): 100_000,
        }

        first_result = calculate_persistence_prediction(
            first, municipality_code="001", issue_week=issue_week
        )
        second_result = calculate_persistence_prediction(
            second, municipality_code="001", issue_week=issue_week
        )

        self.assertEqual(first_result.value, 20)
        self.assertEqual(second_result.value, 20)

    def test_missing_prior_week_produces_missing_prediction_not_zero(self) -> None:
        issue_week = date(2024, 9, 2)
        weekly_cases = {
            ("001", issue_week - timedelta(weeks=4)): 1,
            ("001", issue_week - timedelta(weeks=3)): 2,
            # t-2 is deliberately absent.
            ("001", issue_week - timedelta(weeks=1)): 4,
        }

        result = calculate_persistence_prediction(
            weekly_cases,
            municipality_code="001",
            issue_week=issue_week,
        )

        self.assertIsNone(result.value)
        self.assertEqual(result.status, "missing_prior_week")
        self.assertEqual(result.n_observed_weeks, 3)

    def test_persistence_is_calculated_within_municipality(self) -> None:
        issue_week = date(2024, 10, 7)
        weekly_cases = {}
        for offset in (4, 3, 2, 1):
            weekly_cases[("001", issue_week - timedelta(weeks=offset))] = 1
            weekly_cases[("002", issue_week - timedelta(weeks=offset))] = 10

        municipality_001 = calculate_persistence_prediction(
            weekly_cases, municipality_code="001", issue_week=issue_week
        )
        municipality_002 = calculate_persistence_prediction(
            weekly_cases, municipality_code="002", issue_week=issue_week
        )

        self.assertEqual(municipality_001.value, 4)
        self.assertEqual(municipality_002.value, 40)

    def test_centered_or_future_offsets_are_rejected(self) -> None:
        with self.assertRaisesRegex(BaselineValidationError, "exactly offsets"):
            calculate_persistence_prediction(
                {},
                municipality_code="001",
                issue_week=date(2024, 11, 4),
                prior_week_offsets=(2, 1, 0, -1),
            )


class PoissonDevianceTests(unittest.TestCase):
    def test_zero_prediction_and_zero_observation_uses_valid_limit(self) -> None:
        contribution, status = poisson_deviance_contribution(0, 0.0)

        self.assertEqual(contribution, 0.0)
        self.assertEqual(status, "valid_zero_limit")

    def test_zero_prediction_and_positive_observation_is_invalid(self) -> None:
        contribution, status = poisson_deviance_contribution(1, 0.0)

        self.assertIsNone(contribution)
        self.assertEqual(status, "invalid_zero_prediction_positive_observation")

    def test_positive_prediction_has_finite_poisson_contribution(self) -> None:
        contribution, status = poisson_deviance_contribution(3, 2.5)

        self.assertEqual(status, "valid")
        self.assertIsNotNone(contribution)
        self.assertGreaterEqual(contribution, 0.0)


if __name__ == "__main__":
    unittest.main()
