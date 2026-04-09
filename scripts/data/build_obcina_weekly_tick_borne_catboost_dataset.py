#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.features.obcina_weekly_tick_borne_catboost import (
    DEFAULT_CLC_INPUT,
    DEFAULT_EPIDEMIOLOGY_INPUT,
    DEFAULT_LOG_POPULATION_INPUT,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_OUTPUT,
    DEFAULT_POPULATION_DENSITY_INPUT,
    DEFAULT_WEATHER_DEM_INPUT,
    build_weekly_tick_borne_catboost_dataset,
    write_weekly_tick_borne_catboost_dataset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a municipality-week CatBoost-ready dataset for Lyme and KME by "
            "combining weather, DEM, land-cover, population, and NIJZ epidemiology features."
        )
    )
    parser.add_argument(
        "--weather-dem-input",
        default=str(DEFAULT_WEATHER_DEM_INPUT),
        help="Path to the weekly weather + DEM feature CSV.",
    )
    parser.add_argument(
        "--clc-input",
        default=str(DEFAULT_CLC_INPUT),
        help="Path to the municipality CLC feature CSV.",
    )
    parser.add_argument(
        "--log-population-input",
        default=str(DEFAULT_LOG_POPULATION_INPUT),
        help="Path to the yearly municipality log-population feature CSV.",
    )
    parser.add_argument(
        "--population-density-input",
        default=str(DEFAULT_POPULATION_DENSITY_INPUT),
        help="Path to the yearly municipality population-density feature CSV.",
    )
    parser.add_argument(
        "--epidemiology-input",
        default=str(DEFAULT_EPIDEMIOLOGY_INPUT),
        help="Path to the weekly NIJZ epidemiology CSV.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output CSV path for the final CatBoost-ready dataset.",
    )
    parser.add_argument(
        "--manifest-output",
        default=str(DEFAULT_MANIFEST_OUTPUT),
        help="Output JSON path for the dataset manifest.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tables = build_weekly_tick_borne_catboost_dataset(
            weather_dem_input=Path(args.weather_dem_input),
            clc_input=Path(args.clc_input),
            log_population_input=Path(args.log_population_input),
            population_density_input=Path(args.population_density_input),
            epidemiology_input=Path(args.epidemiology_input),
        )
        write_weekly_tick_borne_catboost_dataset(
            tables,
            output_path=Path(args.output),
            manifest_output=Path(args.manifest_output),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Weekly tick-borne CatBoost dataset build completed.")
    print(f"- rows: {tables.manifest['row_count']}")
    print(f"- municipalities: {tables.manifest['municipality_count']}")
    print(f"- weeks: {tables.manifest['week_count']}")
    print(f"- output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
