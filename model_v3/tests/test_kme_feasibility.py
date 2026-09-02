from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from model_v3.evaluation.kme_feasibility import (
    KmeFeasibilityError,
    anchored_nonoverlap_counts,
    build_design_rows,
    build_year_rows,
    read_canonical_kme_data,
    rolling_window_counts,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class KmeFixture:
    def __init__(self, root: Path, *, missing_week: bool = False) -> None:
        self.root = root
        self.municipality = root / "municipality.csv"
        self.region = root / "statistical_region.csv"
        self.mapping = root / "municipality_statistical_region.csv"
        self.calendar = root / "calendar.csv"
        self.weekly = root / "weekly_cases.csv"
        weeks = [date(2014, 12, 29) + timedelta(weeks=index) for index in range(13)]
        if missing_week:
            weeks.pop(5)

        with self.municipality.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["municipality_code", "municipality_name"]
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"municipality_code": "001", "municipality_name": "Alpha"},
                    {"municipality_code": "002", "municipality_name": "Beta"},
                ]
            )
        with self.region.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["statistical_region_code", "statistical_region_name"],
            )
            writer.writeheader()
            writer.writerow(
                {"statistical_region_code": "R1", "statistical_region_name": "Region One"}
            )
        with self.mapping.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["municipality_code", "statistical_region_code"],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"municipality_code": "001", "statistical_region_code": "R1"},
                    {"municipality_code": "002", "statistical_region_code": "R1"},
                ]
            )
        with self.calendar.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["issue_week", "year", "iso_week"]
            )
            writer.writeheader()
            for week in weeks:
                iso = week.isocalendar()
                writer.writerow(
                    {
                        "issue_week": week.isoformat(),
                        "year": iso.year,
                        "iso_week": iso.week,
                    }
                )
        values = {
            "001": [1, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 0],
            "002": [0] * 13,
        }
        with self.weekly.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["municipality_code", "issue_week", "lyme_cases", "kme_cases"],
            )
            writer.writeheader()
            for code in ("001", "002"):
                for index, week in enumerate(weeks):
                    writer.writerow(
                        {
                            "municipality_code": code,
                            "issue_week": week.isoformat(),
                            "lyme_cases": "not_parsed",
                            "kme_cases": values[code][index],
                        }
                    )

    def config(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "inputs": {
                "weekly_cases": str(self.weekly),
                "weekly_cases_sha256": sha256(self.weekly),
                "municipality": str(self.municipality),
                "municipality_sha256": sha256(self.municipality),
                "calendar": str(self.calendar),
                "calendar_sha256": sha256(self.calendar),
                "statistical_region": str(self.region),
                "statistical_region_sha256": sha256(self.region),
                "municipality_statistical_region": str(self.mapping),
                "municipality_statistical_region_sha256": sha256(self.mapping),
            },
            "canonical_contract": {
                "expected_municipality_count": 2,
                "expected_statistical_region_count": 1,
            },
            "descriptive_windows": {
                "horizons_weeks": [4, 8, 12],
                "definition": "fixture_complete_rolling_windows",
            },
            "statistical_region_mapping": {"status": "verified"},
            "candidate_designs": [
                {"design_id": "A", "analysis_level": "municipality", "horizon_weeks": 4},
                {"design_id": "B", "analysis_level": "municipality", "horizon_weeks": 8},
                {"design_id": "C", "analysis_level": "municipality", "horizon_weeks": 12},
                {"design_id": "D", "analysis_level": "statistical_region", "horizon_weeks": 4},
                {"design_id": "E", "analysis_level": "statistical_region", "horizon_weeks": 8},
            ],
        }


class KmeFeasibilityTests(unittest.TestCase):
    def test_rolling_windows_are_consecutive_and_municipality_independent(self) -> None:
        self.assertEqual(rolling_window_counts([1, 0, 2, 0, 3], 4), [3, 5])
        self.assertEqual(rolling_window_counts([0, 0, 0, 0, 0], 4), [0, 0])
        self.assertEqual(anchored_nonoverlap_counts([1, 0, 2, 0, 3], 4), [3])

    def test_iso_year_summary_uses_iso_year_not_calendar_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = KmeFixture(Path(directory))
            data, _ = read_canonical_kme_data(fixture.config(), Path(directory))
            rows = build_year_rows(data)

        self.assertEqual(rows[0]["iso_year"], 2015)
        self.assertEqual(rows[0]["n_observed_weeks"], 13)
        self.assertEqual(rows[0]["total_kme_cases"], 4)

    def test_candidate_designs_report_municipality_and_region_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = KmeFixture(Path(directory))
            config = fixture.config()
            data, _ = read_canonical_kme_data(config, Path(directory))
            rows = build_design_rows(data, config)

        by_id = {row["design_id"]: row for row in rows}
        self.assertEqual(by_id["A"]["n_candidate_targets"], 20)
        self.assertGreater(by_id["A"]["n_nonzero_candidate_targets"], 0)
        self.assertEqual(by_id["A"]["effective_sample_size_status"], "UNKNOWN_requires_model_and_dependence_structure")
        self.assertEqual(by_id["D"]["status"], "descriptive_feasibility_computed")
        self.assertEqual(by_id["D"]["n_candidate_targets"], 10)
        self.assertGreater(by_id["D"]["n_nonzero_candidate_targets"], 0)
        self.assertEqual(by_id["E"]["n_candidate_targets"], 6)

    def test_missing_calendar_week_is_rejected_not_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = KmeFixture(Path(directory), missing_week=True)
            with self.assertRaisesRegex(KmeFeasibilityError, "missing week"):
                read_canonical_kme_data(fixture.config(), Path(directory))

    def test_only_kme_column_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = KmeFixture(Path(directory))
            data, _ = read_canonical_kme_data(fixture.config(), Path(directory))

        self.assertEqual(sum(data.cases_by_municipality["001"]), 4)
        self.assertEqual(sum(data.cases_by_municipality["002"]), 0)
        self.assertEqual(sum(data.cases_by_statistical_region["R1"]), 4)


if __name__ == "__main__":
    unittest.main()
