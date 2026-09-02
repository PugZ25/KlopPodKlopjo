from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from model_v3.panel.lyme_four_week_target import (
    STATUS_COMPLETE,
    STATUS_INCOMPLETE_FUTURE_HORIZON,
    STATUS_MISSING_FUTURE_WEEK,
    TARGET_COLUMN,
    TARGET_STATUS_COLUMN,
    TARGET_TRAINING_ELIGIBILITY_COLUMN,
    TARGET_WINDOW_END_COLUMN,
    TARGET_WINDOW_START_COLUMN,
    TargetValidationError,
    calculate_lyme_four_week_targets,
    read_canonical_weekly_lyme,
)


def weekly_row(
    municipality_code: str, issue_week: date, lyme_cases: int
) -> dict[str, object]:
    return {
        "municipality_code": municipality_code,
        "issue_week": issue_week,
        "lyme_cases": lyme_cases,
    }


def target_row(
    rows: list[dict[str, object]], municipality_code: str, issue_week: date
) -> dict[str, object]:
    targets = calculate_lyme_four_week_targets(rows)
    return next(
        row
        for row in targets
        if row["municipality_code"] == municipality_code
        and row["issue_week"] == issue_week
    )


class LymeFourWeekTargetTests(unittest.TestCase):
    def test_ordinary_consecutive_weeks_sum_four_future_weeks(self) -> None:
        issue_week = date(2024, 3, 4)
        values = [90, 1, 2, 3, 4]
        rows = [
            weekly_row("001", issue_week + timedelta(weeks=offset), value)
            for offset, value in enumerate(values)
        ]
        rows.reverse()

        result = target_row(rows, "001", issue_week)

        self.assertEqual(result[TARGET_COLUMN], 10)
        self.assertEqual(result[TARGET_STATUS_COLUMN], STATUS_COMPLETE)
        self.assertIs(result[TARGET_TRAINING_ELIGIBILITY_COLUMN], True)

    def test_year_and_iso_week_boundary_uses_calendar_dates(self) -> None:
        issue_week = date(2020, 12, 21)
        rows = [
            weekly_row("001", issue_week, 99),
            weekly_row("001", date(2020, 12, 28), 1),
            weekly_row("001", date(2021, 1, 4), 2),
            weekly_row("001", date(2021, 1, 11), 3),
            weekly_row("001", date(2021, 1, 18), 4),
        ]

        result = target_row(rows, "001", issue_week)

        self.assertEqual(result[TARGET_COLUMN], 10)
        self.assertEqual(result[TARGET_WINDOW_START_COLUMN], date(2020, 12, 28))
        self.assertEqual(result[TARGET_WINDOW_END_COLUMN], date(2021, 1, 18))

    def test_municipalities_are_calculated_independently(self) -> None:
        issue_week = date(2024, 4, 1)
        rows: list[dict[str, object]] = []
        for offset, value in enumerate([0, 1, 1, 1, 1]):
            rows.append(
                weekly_row("001", issue_week + timedelta(weeks=offset), value)
            )
        for offset, value in enumerate([0, 10, 20, 30, 40]):
            rows.append(
                weekly_row("002", issue_week + timedelta(weeks=offset), value)
            )

        targets = calculate_lyme_four_week_targets(rows)
        municipality_001 = next(
            row
            for row in targets
            if row["municipality_code"] == "001"
            and row["issue_week"] == issue_week
        )
        municipality_002 = next(
            row
            for row in targets
            if row["municipality_code"] == "002"
            and row["issue_week"] == issue_week
        )

        self.assertEqual(municipality_001[TARGET_COLUMN], 4)
        self.assertEqual(municipality_002[TARGET_COLUMN], 100)

    def test_incomplete_future_horizon_is_explicit_and_ineligible(self) -> None:
        issue_week = date(2024, 5, 6)
        rows = [
            weekly_row("001", issue_week + timedelta(weeks=offset), offset)
            for offset in range(4)
        ]

        result = target_row(rows, "001", issue_week)

        self.assertIsNone(result[TARGET_COLUMN])
        self.assertEqual(
            result[TARGET_STATUS_COLUMN], STATUS_INCOMPLETE_FUTURE_HORIZON
        )
        self.assertIs(result[TARGET_TRAINING_ELIGIBILITY_COLUMN], False)
        self.assertEqual(result[TARGET_WINDOW_START_COLUMN], date(2024, 5, 13))
        self.assertEqual(result[TARGET_WINDOW_END_COLUMN], date(2024, 6, 3))

    def test_missing_week_inside_window_is_not_silently_zero(self) -> None:
        issue_week = date(2024, 6, 3)
        rows = [
            weekly_row("001", issue_week, 50),
            weekly_row("001", issue_week + timedelta(weeks=1), 1),
            # t+2 is deliberately absent.
            weekly_row("001", issue_week + timedelta(weeks=3), 3),
            weekly_row("001", issue_week + timedelta(weeks=4), 4),
            weekly_row("001", issue_week + timedelta(weeks=5), 100),
        ]

        result = target_row(rows, "001", issue_week)

        self.assertIsNone(result[TARGET_COLUMN])
        self.assertEqual(result[TARGET_STATUS_COLUMN], STATUS_MISSING_FUTURE_WEEK)
        self.assertIs(result[TARGET_TRAINING_ELIGIBILITY_COLUMN], False)

    def test_current_issue_week_is_excluded(self) -> None:
        issue_week = date(2024, 7, 1)
        rows = [weekly_row("001", issue_week, 10_000)] + [
            weekly_row("001", issue_week + timedelta(weeks=offset), 0)
            for offset in range(1, 5)
        ]

        result = target_row(rows, "001", issue_week)

        self.assertEqual(result[TARGET_COLUMN], 0)

    def test_exactly_t_plus_1_through_t_plus_4_are_included(self) -> None:
        issue_week = date(2024, 8, 5)
        values = [100, 1, 2, 4, 8, 1_000]
        rows = [
            weekly_row("001", issue_week + timedelta(weeks=offset), value)
            for offset, value in enumerate(values)
        ]

        result = target_row(rows, "001", issue_week)

        self.assertEqual(result[TARGET_COLUMN], 15)
        self.assertEqual(result[TARGET_WINDOW_START_COLUMN], issue_week + timedelta(weeks=1))
        self.assertEqual(result[TARGET_WINDOW_END_COLUMN], issue_week + timedelta(weeks=4))

    def test_duplicate_municipality_week_is_rejected(self) -> None:
        issue_week = date(2024, 9, 2)
        rows = [
            weekly_row("001", issue_week, 1),
            weekly_row("001", issue_week, 2),
        ]

        with self.assertRaisesRegex(TargetValidationError, "duplicate municipality-week"):
            calculate_lyme_four_week_targets(rows)

    def test_missing_lyme_case_value_is_rejected_instead_of_becoming_zero(self) -> None:
        issue_week = date(2024, 10, 7)
        rows = [
            {
                "municipality_code": "001",
                "issue_week": issue_week,
                "lyme_cases": None,
            }
        ]

        with self.assertRaisesRegex(TargetValidationError, "present non-negative integer"):
            calculate_lyme_four_week_targets(rows)

    def test_lockbox_row_is_skipped_before_code_and_case_parsing(self) -> None:
        content = "\n".join(
            [
                "municipality_code,issue_week,lyme_cases",
                "001,2024-12-30,2",
                "NOT_A_CODE,2025-01-06,SECRET",
            ]
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "weekly_cases.csv"
            path.write_text(content + "\n", encoding="utf-8")
            rows, skipped = read_canonical_weekly_lyme(
                path, lockbox_year=2025
            )

        self.assertEqual(skipped, 1)
        self.assertEqual(rows, [weekly_row("001", date(2024, 12, 30), 2)])
        targets = calculate_lyme_four_week_targets(rows)
        self.assertEqual(len(targets), 1)
        self.assertEqual(
            targets[0][TARGET_STATUS_COLUMN], STATUS_INCOMPLETE_FUTURE_HORIZON
        )
        self.assertIsNone(targets[0][TARGET_COLUMN])


if __name__ == "__main__":
    unittest.main()
