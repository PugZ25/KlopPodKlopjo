#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.nijz_obcina_weekly import (
    DEFAULT_KME_INPUT,
    DEFAULT_LYME_INPUT,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_MUNICIPALITY_REFERENCE,
    DEFAULT_OUTPUT,
    build_obcina_weekly_epidemiology,
    write_obcina_weekly_epidemiology,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert NIJZ weekly municipality infection workbooks into a long, "
            "join-ready CSV with Lyme and KME case counts."
        )
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
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output CSV path for the cleaned weekly epidemiology data.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON manifest path.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tables = build_obcina_weekly_epidemiology(
            lyme_input=Path(args.lyme_input),
            kme_input=Path(args.kme_input),
            municipality_reference=Path(args.municipality_reference),
        )
        write_obcina_weekly_epidemiology(
            tables,
            output_path=Path(args.output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("NIJZ weekly epidemiology pipeline completed.")
    print(f"- rows: {tables.manifest['row_count']}")
    print(f"- municipalities: {tables.manifest['municipality_count']}")
    print(f"- weeks: {tables.manifest['week_count']}")
    print(f"- Lyme cases: {tables.manifest['lyme_case_total']}")
    print(f"- KME cases: {tables.manifest['kme_case_total']}")
    print(f"- output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
