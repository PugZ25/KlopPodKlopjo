#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.surs_obcina_population import (
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_OUTPUT,
    DEFAULT_RAW_INPUT,
    build_obcina_surs_population_yearly_features,
    write_obcina_surs_population_yearly_features,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build yearly municipality log-population features from a raw "
            "SURS SiStat JSON export."
        )
    )
    parser.add_argument(
        "--raw-input",
        default=str(DEFAULT_RAW_INPUT),
        help="Input JSON path for the raw SURS export.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output CSV path for yearly municipality log-population features.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON path for the SURS feature manifest.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tables = build_obcina_surs_population_yearly_features(
            raw_input=Path(args.raw_input),
        )
        write_obcina_surs_population_yearly_features(
            tables,
            output_path=Path(args.output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("SURS municipality log-population feature build completed.")
    print(f"- rows: {tables.manifest['row_count']}")
    print(f"- municipalities: {tables.manifest['municipality_count']}")
    print(f"- years: {tables.manifest['year_count']}")
    print(f"- output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
