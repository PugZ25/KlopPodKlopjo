#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.obcina_weekly_weather_dem import (
    DEFAULT_DEM_INPUT,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_OUTPUT,
    DEFAULT_WEATHER_INPUT,
    build_weekly_weather_dem_features,
    write_weekly_weather_dem_features,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Join municipality weekly weather features with municipality-level "
            "Copernicus DEM summary features."
        )
    )
    parser.add_argument(
        "--weather-input",
        default=str(DEFAULT_WEATHER_INPUT),
        help="Input CSV path for municipality weekly weather features.",
    )
    parser.add_argument(
        "--dem-input",
        default=str(DEFAULT_DEM_INPUT),
        help="Input CSV path for municipality DEM features.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output CSV path for the combined weekly weather + DEM features.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON path for the join manifest.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tables = build_weekly_weather_dem_features(
            weather_input=Path(args.weather_input),
            dem_input=Path(args.dem_input),
        )
        write_weekly_weather_dem_features(
            tables,
            output_path=Path(args.output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Municipality weekly weather + DEM join completed.")
    print(f"- rows: {tables.manifest['row_count']}")
    print(f"- municipalities: {tables.manifest['municipality_count']}")
    print(f"- output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
