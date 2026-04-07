#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.copernicus_clc_obcina import (
    DEFAULT_COVERAGE_OUTPUT,
    DEFAULT_GEOJSON_PATH,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_RASTER_PATH,
    DEFAULT_SUMMARY_OUTPUT,
    ProcessingDependencyError,
    build_obcina_clc_feature_tables,
    write_clc_feature_tables,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build municipality-level CLC 2018 summary features from the "
            "raw 100 m Copernicus land-cover raster."
        )
    )
    parser.add_argument(
        "--raster-path",
        default=str(DEFAULT_RASTER_PATH),
        help="Path to the raw CLC GeoTIFF raster.",
    )
    parser.add_argument(
        "--geojson-path",
        default=str(DEFAULT_GEOJSON_PATH),
        help="Path to the GURS municipality GeoJSON file.",
    )
    parser.add_argument(
        "--limit-obcine",
        type=int,
        help="Optional limit for smoke tests.",
    )
    parser.add_argument(
        "--obcina-sifre",
        help="Optional comma-separated municipality codes to process.",
    )
    parser.add_argument(
        "--sampling-output",
        default=str(DEFAULT_COVERAGE_OUTPUT),
        help="Output CSV path for municipality raster sampling rows.",
    )
    parser.add_argument(
        "--summary-output",
        default=str(DEFAULT_SUMMARY_OUTPUT),
        help="Output CSV path for municipality CLC feature rows.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON path for the pipeline manifest.",
    )
    return parser


def parse_obcina_sifre(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    values = [value.strip() for value in raw_value.split(",") if value.strip()]
    return values or None


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tables = build_obcina_clc_feature_tables(
            raster_path=Path(args.raster_path),
            geojson_path=Path(args.geojson_path),
            limit_obcine=args.limit_obcine,
            obcina_sifre=parse_obcina_sifre(args.obcina_sifre),
        )
        write_clc_feature_tables(
            tables,
            sampling_output=Path(args.sampling_output),
            summary_output=Path(args.summary_output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ProcessingDependencyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Municipality CLC feature pipeline completed.")
    print(f"- municipality rows: {tables.manifest['municipality_feature_row_count']}")
    print(f"- sampling rows: {tables.manifest['sampling_row_count']}")
    print(f"- summary output: {Path(args.summary_output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
