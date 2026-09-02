from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from model_v3.evaluation.lockbox_evaluation import (
    BASELINE_D,
    CHALLENGER_ID,
    DEFAULT_CONFIG_PATH,
    REFERENCE_ID,
    SYSTEM_IDS,
    LockboxEvaluationError,
    calibration_group_rows,
    construct_lockbox_target,
    create_open_receipt,
    load_config,
    merge_weather,
    overall_calibration_rows,
    read_lockbox_issue_weeks,
    read_lockbox_weekly_cases_once,
)
from model_v3.features.weather_weekly import OUTPUT_VARIABLES
from model_v3.models.weather_ablation import WeeklyWeather


def mondays_in_year(year: int) -> list[date]:
    current = date(year, 1, 1)
    while current.weekday() != 0:
        current += timedelta(days=1)
    result: list[date] = []
    while current.year == year:
        result.append(current)
        current += timedelta(weeks=1)
    return result


def synthetic_prediction(candidate_id: str, index: int) -> dict[str, object]:
    observed = index % 4
    predicted = float(index + 1) / 3.0
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_id,
        "municipality_code": f"{index + 1:03d}",
        "issue_week": date(2025, 1, 6) + timedelta(weeks=index),
        "actual_target_lyme_cases_next_4w": observed,
        "predicted_target_lyme_cases_next_4w": predicted,
    }


class LockboxEvaluationTests(unittest.TestCase):
    def test_config_freezes_exact_systems_and_target(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)

        self.assertEqual(config["freeze"]["systems"], list(SYSTEM_IDS))
        self.assertEqual(config["target"]["included_week_offsets"], [1, 2, 3, 4])
        self.assertFalse(config["target"]["issue_week_included"])
        self.assertTrue(config["freeze"]["run_once"])

    def test_lockbox_calendar_returns_only_fully_contained_target_windows(self) -> None:
        mondays = mondays_in_year(2025)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["issue_week"])
                writer.writeheader()
                for week in mondays:
                    writer.writerow({"issue_week": week.isoformat()})

            observed, eligible = read_lockbox_issue_weeks(path, lockbox_year=2025)

        self.assertEqual(tuple(mondays), observed)
        self.assertEqual(eligible[0], date(2025, 1, 6))
        self.assertEqual(eligible[-1], date(2025, 12, 1))
        self.assertEqual(len(eligible), 48)
        self.assertTrue(all(week.year == 2025 for week in eligible))
        self.assertTrue(all((week + timedelta(weeks=4)).year == 2025 for week in eligible))

    def test_truncated_lockbox_calendar_purges_incomplete_four_week_horizon(self) -> None:
        observed_fixture = [
            week for week in mondays_in_year(2025) if week <= date(2025, 12, 22)
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["issue_week"])
                writer.writeheader()
                for week in observed_fixture:
                    writer.writerow({"issue_week": week.isoformat()})

            observed, eligible = read_lockbox_issue_weeks(path, lockbox_year=2025)

        self.assertEqual(observed[-1], date(2025, 12, 22))
        self.assertEqual(eligible[-1], date(2025, 11, 24))
        self.assertEqual(len(observed), 51)
        self.assertEqual(len(eligible), 47)
        self.assertEqual(len(observed) - len(eligible), 4)

    def test_target_is_exactly_t_plus_1_through_t_plus_4_per_municipality(self) -> None:
        all_weeks = mondays_in_year(2025)
        cases = {
            (code, week): index + 1 + (100 if code == "002" else 0)
            for code in ("001", "002")
            for index, week in enumerate(all_weeks)
        }
        issue_weeks = tuple(
            week for week in all_weeks if week + timedelta(weeks=4) <= date(2025, 12, 31)
        )

        rows, targets = construct_lockbox_target(
            expected_case_weeks=all_weeks,
            issue_weeks=issue_weeks,
            municipality_codes=("001", "002"),
            lockbox_cases=cases,
            lockbox_year=2025,
        )

        issue = date(2025, 1, 6)
        expected_001 = sum(cases[("001", issue + timedelta(weeks=offset))] for offset in (1, 2, 3, 4))
        expected_002 = sum(cases[("002", issue + timedelta(weeks=offset))] for offset in (1, 2, 3, 4))
        self.assertEqual(targets[("001", issue)], expected_001)
        self.assertEqual(targets[("002", issue)], expected_002)
        self.assertNotEqual(targets[("001", issue)], expected_001 + cases[("001", issue)])
        first = next(row for row in rows if row.municipality_code == "001" and row.issue_week == issue)
        self.assertEqual(first.target_window_start, issue + timedelta(weeks=1))
        self.assertEqual(first.target_window_end, issue + timedelta(weeks=4))

    def test_protected_reader_skips_non_lockbox_numeric_values_before_parsing(self) -> None:
        content = (
            "municipality_code,issue_week,lyme_cases\n"
            "001,2024-12-30,not_parsed\n"
            "001,2025-01-06,2\n"
            "002,2025-01-06,0\n"
        ).encode("utf-8")
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weekly_cases.csv"
            path.write_bytes(content)

            values, actual = read_lockbox_weekly_cases_once(
                path, lockbox_year=2025, expected_sha256=expected
            )

        self.assertEqual(actual, expected)
        self.assertEqual(values, {("001", date(2025, 1, 6)): 2, ("002", date(2025, 1, 6)): 0})

    def test_receipt_creation_refuses_second_open(self) -> None:
        config = load_config(DEFAULT_CONFIG_PATH)
        outputs_root = DEFAULT_CONFIG_PATH.parents[1] / "outputs"
        with tempfile.TemporaryDirectory(dir=outputs_root) as directory:
            receipt = Path(directory) / "LOCKBOX_OPENED.json"
            create_open_receipt(receipt, config_path=DEFAULT_CONFIG_PATH, config=config)

            with self.assertRaisesRegex(LockboxEvaluationError, "already exists"):
                create_open_receipt(receipt, config_path=DEFAULT_CONFIG_PATH, config=config)

    def test_weather_extension_replaces_only_incomplete_overlap(self) -> None:
        values = {column: float(index) for index, column in enumerate(OUTPUT_VARIABLES)}
        week = date(2024, 12, 30)
        development = {
            ("001", week): WeeklyWeather(
                "001", week, week + timedelta(days=6), "incomplete_source_week", None
            )
        }
        extension_row = WeeklyWeather(
            "001", week, week + timedelta(days=6), "complete", values
        )

        combined = merge_weather(development, {("001", week): extension_row})

        self.assertEqual(combined[("001", week)], extension_row)

    def test_calibration_diagnostics_are_descriptive_and_deterministic(self) -> None:
        predictions = [
            synthetic_prediction(candidate_id, index)
            for candidate_id in (CHALLENGER_ID, REFERENCE_ID, BASELINE_D)
            for index in range(20)
        ]

        overall = overall_calibration_rows(predictions)
        groups = calibration_group_rows(predictions, n_groups=10)

        self.assertEqual(len(overall), 3)
        self.assertTrue(all(row["diagnostic_only_no_recalibration"] for row in overall))
        self.assertEqual(len(groups), 30)
        for candidate_id in SYSTEM_IDS:
            selected = [row for row in groups if row["candidate_id"] == candidate_id]
            self.assertEqual([row["calibration_group"] for row in selected], list(range(1, 11)))
            self.assertEqual(sum(int(row["n"]) for row in selected), 20)


if __name__ == "__main__":
    unittest.main()
