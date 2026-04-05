#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.copernicus_obcina_weekly import (
    DEFAULT_DAILY_OUTPUT,
    DEFAULT_GEOJSON_PATH,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_OVERLAY_OUTPUT,
    DEFAULT_SOURCE_DIR,
    DEFAULT_WEEKLY_OUTPUT,
    ProcessingDependencyError,
    build_obcina_weather_feature_tables,
    parse_iso_date,
    write_weather_feature_tables,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build area-weighted municipality daily and weekly weather features "
            "from ERA5-Land Slovenia NetCDF files."
        )
    )
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Directory with monthly ERA5-Land feature NetCDF files.",
    )
    parser.add_argument(
        "--geojson-path",
        default=str(DEFAULT_GEOJSON_PATH),
        help="Path to the GURS municipality GeoJSON file.",
    )
    parser.add_argument(
        "--start-date",
        help="Optional inclusive start date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        help="Optional inclusive end date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        help="Optional limit for smoke tests.",
    )
    parser.add_argument(
        "--week-start-day",
        default="MON",
        help="Week start day. Supported values: MON, TUE, WED, THU, FRI, SAT, SUN.",
    )
    parser.add_argument(
        "--keep-partial-weeks",
        action="store_true",
        help="Keep first/last partial weeks instead of dropping them.",
    )
    parser.add_argument(
        "--overlay-output",
        default=str(DEFAULT_OVERLAY_OUTPUT),
        help="Output CSV path for the municipality x grid overlay matrix.",
    )
    parser.add_argument(
        "--daily-output",
        default=str(DEFAULT_DAILY_OUTPUT),
        help="Output CSV path for municipality daily weather features.",
    )
    parser.add_argument(
        "--weekly-output",
        default=str(DEFAULT_WEEKLY_OUTPUT),
        help="Output CSV path for municipality weekly weather features.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON path for the pipeline manifest.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        start_date = parse_iso_date(args.start_date) if args.start_date else None
        end_date = parse_iso_date(args.end_date) if args.end_date else None
        if start_date and end_date and start_date > end_date:
            raise ValueError("Start date must be before or equal to end date.")

        tables = build_obcina_weather_feature_tables(
            source_dir=Path(args.source_dir),
            geojson_path=Path(args.geojson_path),
            start_date=start_date,
            end_date=end_date,
            limit_files=args.limit_files,
            week_start_day=args.week_start_day,
            keep_partial_weeks=args.keep_partial_weeks,
        )
        write_weather_feature_tables(
            tables,
            overlay_output=Path(args.overlay_output),
            daily_output=Path(args.daily_output),
            weekly_output=Path(args.weekly_output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ProcessingDependencyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Municipality weather feature pipeline completed.")
    print(f"- overlay rows: {tables.manifest['overlay_summary']['overlay_rows']}")
    print(f"- daily rows: {tables.manifest['daily_row_count']}")
    print(f"- weekly rows: {tables.manifest['weekly_row_count']}")
    print(f"- weekly output: {Path(args.weekly_output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
