from __future__ import annotations

import unittest
from datetime import date, timedelta

from model_v3.panel.kme_eight_week_target import construct_target_rows


class KmeEightWeekTargetTests(unittest.TestCase):
    def test_target_is_exactly_t_plus_1_through_t_plus_8(self) -> None:
        start = date(2024, 12, 2)
        weeks = [start + timedelta(weeks=index) for index in range(10)]
        cases = {("01", week): index for index, week in enumerate(weeks)}
        rows = construct_target_rows(("01",), weeks, cases)
        first = rows[0]

        self.assertEqual(first.target_window_start, start + timedelta(weeks=1))
        self.assertEqual(first.target_window_end, start + timedelta(weeks=8))
        self.assertEqual(first.target_value, sum(range(1, 9)))
        self.assertNotEqual(first.target_value, sum(range(0, 8)))
        self.assertTrue(first.training_eligible)

    def test_year_boundary_uses_dates_not_week_numbers(self) -> None:
        start = date(2024, 12, 23)
        weeks = [start + timedelta(weeks=index) for index in range(10)]
        cases = {("01", week): 1 for week in weeks}
        first = construct_target_rows(("01",), weeks, cases)[0]

        self.assertEqual(first.target_window_start, date(2024, 12, 30))
        self.assertEqual(first.target_window_end, date(2025, 2, 17))
        self.assertEqual(first.target_value, 8)

    def test_regions_are_calculated_independently(self) -> None:
        start = date(2020, 1, 6)
        weeks = [start + timedelta(weeks=index) for index in range(10)]
        cases = {
            (region, week): (1 if region == "01" else 10)
            for region in ("01", "02")
            for week in weeks
        }
        rows = construct_target_rows(("01", "02"), weeks, cases)
        first_by_region = {row.statistical_region_code: row for row in rows if row.issue_week == start}

        self.assertEqual(first_by_region["01"].target_value, 8)
        self.assertEqual(first_by_region["02"].target_value, 80)

    def test_incomplete_future_window_is_explicit_and_ineligible(self) -> None:
        start = date(2020, 1, 6)
        weeks = [start + timedelta(weeks=index) for index in range(8)]
        cases = {("01", week): 0 for week in weeks}
        last = construct_target_rows(("01",), weeks, cases)[-1]

        self.assertIsNone(last.target_value)
        self.assertEqual(last.target_status, "incomplete_future_window")
        self.assertFalse(last.training_eligible)


if __name__ == "__main__":
    unittest.main()
