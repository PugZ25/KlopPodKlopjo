from __future__ import annotations

import unittest
from datetime import date, timedelta

from model_v3.validation.rolling_origin import (
    RollingOriginValidationError,
    generate_rolling_origin_folds,
)


def target_metadata_row(
    issue_week: date,
    *,
    municipality_code: str = "001",
    status: str = "complete",
    eligible: bool = True,
) -> dict[str, object]:
    return {
        "municipality_code": municipality_code,
        "issue_week": issue_week,
        "target_window_start": issue_week + timedelta(weeks=1),
        "target_window_end": issue_week + timedelta(weeks=4),
        "target_status": status,
        "target_training_eligible": eligible,
    }


def two_year_boundary_rows() -> list[dict[str, object]]:
    issue_weeks = [
        date(2016, 11, 28),
        date(2016, 12, 5),
        date(2016, 12, 12),
        date(2016, 12, 19),
        date(2016, 12, 26),
        date(2017, 1, 2),
        date(2017, 1, 9),
        date(2017, 11, 27),
        date(2017, 12, 4),
        date(2017, 12, 11),
        date(2017, 12, 18),
        date(2017, 12, 25),
    ]
    return [target_metadata_row(issue_week) for issue_week in issue_weeks]


class RollingOriginValidationTests(unittest.TestCase):
    def test_no_train_target_window_overlaps_validation(self) -> None:
        folds = generate_rolling_origin_folds(
            list(reversed(two_year_boundary_rows())),
            development_start_year=2016,
            development_end_year=2017,
            lockbox_year=2025,
        )

        self.assertEqual(len(folds), 1)
        fold = folds[0]
        self.assertTrue(
            all(
                row.target_window_end < fold.validation_start
                for row in fold.train_rows
            )
        )
        self.assertEqual(
            max(row.target_window_end for row in fold.train_rows),
            date(2016, 12, 26),
        )

    def test_validation_target_windows_do_not_leak_into_later_period(self) -> None:
        fold = generate_rolling_origin_folds(
            two_year_boundary_rows(),
            development_start_year=2016,
            development_end_year=2017,
            lockbox_year=2025,
        )[0]

        self.assertTrue(
            all(
                row.target_window_start >= fold.validation_start
                and row.target_window_end <= fold.validation_end
                for row in fold.validation_rows
            )
        )
        self.assertIn(date(2017, 11, 27), {row.issue_week for row in fold.validation_rows})
        self.assertNotIn(date(2017, 12, 4), {row.issue_week for row in fold.validation_rows})

    def test_lockbox_issue_weeks_and_target_windows_are_never_returned(self) -> None:
        issue_weeks = [
            date(2023, 11, 27),
            date(2023, 12, 4),
            date(2023, 12, 11),
            date(2023, 12, 18),
            date(2023, 12, 25),
            date(2024, 1, 1),
            date(2024, 1, 8),
            date(2024, 11, 25),
            date(2024, 12, 2),
            date(2024, 12, 9),
            date(2024, 12, 16),
            date(2024, 12, 23),
            date(2024, 12, 30),
            date(2025, 1, 6),
            date(2025, 1, 13),
        ]
        fold = generate_rolling_origin_folds(
            [target_metadata_row(issue_week) for issue_week in issue_weeks],
            development_start_year=2023,
            development_end_year=2024,
            lockbox_year=2025,
        )[0]

        selected_rows = fold.train_rows + fold.validation_rows
        self.assertTrue(all(row.issue_week.year < 2025 for row in selected_rows))
        self.assertTrue(
            all(row.target_window_end.year < 2025 for row in selected_rows)
        )
        self.assertNotIn(date(2024, 12, 9), {row.issue_week for row in selected_rows})

    def test_rows_on_and_near_boundaries_are_purged_strictly(self) -> None:
        fold = generate_rolling_origin_folds(
            two_year_boundary_rows(),
            development_start_year=2016,
            development_end_year=2017,
            lockbox_year=2025,
        )[0]

        train_dates = {row.issue_week for row in fold.train_rows}
        train_purged_dates = {
            row.issue_week for row in fold.train_boundary_purged_rows
        }
        validation_dates = {row.issue_week for row in fold.validation_rows}
        validation_purged_dates = {
            row.issue_week for row in fold.validation_boundary_purged_rows
        }

        self.assertIn(date(2016, 11, 28), train_dates)
        self.assertIn(date(2016, 12, 5), train_purged_dates)
        self.assertEqual(len(train_purged_dates), 4)
        self.assertIn(date(2017, 11, 27), validation_dates)
        self.assertIn(date(2017, 12, 4), validation_purged_dates)
        self.assertEqual(len(validation_purged_dates), 4)

        manifest = fold.manifest_record()
        self.assertEqual(manifest["n_train"], 1)
        self.assertEqual(manifest["n_validation"], 3)
        self.assertEqual(manifest["number_of_purged_rows"], 8)
        self.assertEqual(manifest["train_target_end_max"], date(2016, 12, 26))

    def test_folds_use_actual_available_years_without_inventing_missing_years(self) -> None:
        issue_weeks = [
            date(2016, 1, 4),
            date(2016, 11, 28),
            date(2018, 1, 1),
            date(2018, 1, 8),
            date(2018, 11, 26),
            date(2018, 12, 3),
            date(2018, 12, 10),
            date(2018, 12, 17),
            date(2018, 12, 24),
            date(2018, 12, 31),
        ]

        folds = generate_rolling_origin_folds(
            [target_metadata_row(issue_week) for issue_week in issue_weeks],
            development_start_year=2016,
            development_end_year=2018,
            lockbox_year=2025,
        )

        self.assertEqual([fold.validation_start.year for fold in folds], [2018])
        self.assertEqual(folds[0].fold_id, "fold_01_validate_2018")

    def test_target_ineligible_rows_are_excluded_not_boundary_imputed(self) -> None:
        rows = two_year_boundary_rows()
        rows.append(
            target_metadata_row(
                date(2017, 6, 5),
                status="incomplete_future_horizon",
                eligible=False,
            )
        )

        fold = generate_rolling_origin_folds(
            rows,
            development_start_year=2016,
            development_end_year=2017,
            lockbox_year=2025,
        )[0]

        self.assertEqual(fold.n_ineligible_excluded, 1)
        self.assertNotIn(
            date(2017, 6, 5), {row.issue_week for row in fold.validation_rows}
        )

    def test_duplicate_municipality_week_is_rejected(self) -> None:
        row = target_metadata_row(date(2016, 1, 4))

        with self.assertRaisesRegex(
            RollingOriginValidationError, "duplicate municipality-week"
        ):
            generate_rolling_origin_folds(
                [row, row],
                development_start_year=2016,
                development_end_year=2017,
                lockbox_year=2025,
            )


if __name__ == "__main__":
    unittest.main()
