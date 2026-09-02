from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from model_v3.evaluation.descriptive_epidemiology import (
    DENOMINATOR_MISSING,
    DENOMINATOR_NONPOSITIVE,
    DENOMINATOR_VALID,
    DescriptiveEpidemiologyError,
    calculate_incidence_per_100000,
    load_calendar,
    load_population,
    load_target_metadata,
    load_weekly_lyme,
)


class DescriptiveIncidenceTests(unittest.TestCase):
    def test_incidence_per_100000_uses_cases_as_numerator(self) -> None:
        incidence, status = calculate_incidence_per_100000(50, 10_000)

        self.assertEqual(status, DENOMINATOR_VALID)
        self.assertAlmostEqual(incidence, 500.0)

    def test_zero_cases_produce_zero_incidence_with_valid_population(self) -> None:
        incidence, status = calculate_incidence_per_100000(0, 12_500)

        self.assertEqual(status, DENOMINATOR_VALID)
        self.assertEqual(incidence, 0.0)

    def test_missing_population_produces_missing_incidence(self) -> None:
        incidence, status = calculate_incidence_per_100000(7, None)

        self.assertEqual(status, DENOMINATOR_MISSING)
        self.assertIsNone(incidence)

    def test_zero_population_is_not_used_as_a_denominator(self) -> None:
        incidence, status = calculate_incidence_per_100000(7, 0)

        self.assertEqual(status, DENOMINATOR_NONPOSITIVE)
        self.assertIsNone(incidence)

    def test_negative_case_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(DescriptiveEpidemiologyError, "must not be negative"):
            calculate_incidence_per_100000(-1, 10_000)

    def test_negative_population_is_rejected(self) -> None:
        with self.assertRaisesRegex(DescriptiveEpidemiologyError, "must not be negative"):
            calculate_incidence_per_100000(1, -10_000)

    def test_incidence_is_not_integer_truncated(self) -> None:
        incidence, status = calculate_incidence_per_100000(1, 3)

        self.assertEqual(status, DENOMINATOR_VALID)
        self.assertAlmostEqual(incidence, 33_333.333333333336)


class DescriptiveLockboxLoaderTests(unittest.TestCase):
    def test_lockbox_rows_are_skipped_before_numeric_and_code_parsing(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            population_path = root / "population.csv"
            population_path.write_text(
                "municipality_code,year,population\n"
                "001,2024,10000\n"
                "NOT_A_CODE,2025,SECRET\n",
                encoding="utf-8",
            )
            weekly_path = root / "weekly.csv"
            weekly_path.write_text(
                "municipality_code,issue_week,lyme_cases\n"
                "001,2024-12-30,2\n"
                "NOT_A_CODE,2025-01-06,SECRET\n",
                encoding="utf-8",
            )
            calendar_path = root / "calendar.csv"
            calendar_path.write_text(
                "issue_week,year,iso_week\n"
                "2024-12-30,2025,1\n"
                "2025-01-06,SECRET,SECRET\n",
                encoding="utf-8",
            )
            target_path = root / "target.csv"
            target_path.write_text(
                "municipality_code,issue_week,target_lyme_cases_next_4w,"
                "target_window_start,target_window_end,target_status,"
                "target_training_eligible\n"
                "001,2024-12-30,,2025-01-06,2025-01-27,"
                "incomplete_future_horizon,false\n"
                "NOT_A_CODE,2025-01-06,SECRET,NOT_A_DATE,NOT_A_DATE,"
                "SECRET,SECRET\n",
                encoding="utf-8",
            )

            population = load_population(population_path, lockbox_year=2025)
            weekly = load_weekly_lyme(weekly_path, lockbox_year=2025)
            calendar = load_calendar(calendar_path, lockbox_year=2025)
            target = load_target_metadata(target_path, lockbox_year=2025)

        self.assertEqual(len(population), 1)
        self.assertEqual(population[0].population, 10000)
        self.assertEqual(len(weekly), 1)
        self.assertEqual(weekly[0].lyme_cases, 2)
        self.assertEqual(len(calendar), 1)
        self.assertEqual(calendar[0].issue_week, date(2024, 12, 30))
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0].issue_week, date(2024, 12, 30))
        self.assertIsNone(target[0].target_value)


if __name__ == "__main__":
    unittest.main()
