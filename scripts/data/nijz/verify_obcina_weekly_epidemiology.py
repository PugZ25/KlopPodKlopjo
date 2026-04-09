#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.nijz_obcina_weekly import (
    DEFAULT_KME_INPUT,
    DEFAULT_LYME_INPUT,
    DEFAULT_MUNICIPALITY_REFERENCE,
    DEFAULT_OUTPUT,
    verify_obcina_weekly_epidemiology,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the cleaned NIJZ municipality-week epidemiology CSV against the original XLSX files."
        )
    )
    parser.add_argument(
        "--csv-path",
        default=str(DEFAULT_OUTPUT),
        help="Path to the cleaned epidemiology CSV.",
    )
    parser.add_argument(
        "--lyme-input",
        default=str(DEFAULT_LYME_INPUT),
        help="Path to the NIJZ Lyme workbook.",
    )
    parser.add_argument(
        "--kme-input",
        default=str(DEFAULT_KME_INPUT),
        help="Path to the NIJZ KME workbook.",
    )
    parser.add_argument(
        "--municipality-reference",
        default=str(DEFAULT_MUNICIPALITY_REFERENCE),
        help="CSV used to standardize municipality codes and names.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full verification report as JSON.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = verify_obcina_weekly_epidemiology(
            csv_path=Path(args.csv_path),
            lyme_input=Path(args.lyme_input),
            kme_input=Path(args.kme_input),
            municipality_reference=Path(args.municipality_reference),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = result.report
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("NIJZ epidemiology verification completed.")
        print(f"- valid: {result.is_valid}")
        print(f"- csv rows checked: {report['csv_row_count']}")
        print(f"- expected workbook pairs: {report['expected_pair_count']}")
        print(f"- csv row issues: {len(report['csv_row_issues'])}")
        print(f"- value mismatches: {len(report['value_mismatches'])}")
        print(f"- missing csv keys: {len(report['missing_csv_keys'])}")
        print(f"- unexpected csv keys: {len(report['unexpected_csv_keys'])}")
        print(
            "- municipality row total mismatches: "
            f"{len(report['municipality_row_total_mismatches'])}"
        )
        print(
            "- workbook aggregate mismatches (diagnostic only): "
            f"lyme={len(report['aggregated_total_mismatches']['lyme_cases'])}, "
            f"kme={len(report['aggregated_total_mismatches']['kme_cases'])}"
        )

    return 0 if result.is_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
