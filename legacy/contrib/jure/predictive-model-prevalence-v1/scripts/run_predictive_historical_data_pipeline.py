from __future__ import annotations

import argparse
import calendar
import re
import sys
from datetime import date
from pathlib import Path

from pipeline_utils import (
    CLC_MANIFEST_OUTPUT,
    CLC_RAW_DIR,
    CLC_SAMPLING_OUTPUT,
    CLC_SUMMARY_OUTPUT,
    DEM_MANIFEST_OUTPUT,
    DEM_RAW_DIR,
    DEM_SUMMARY_OUTPUT,
    DEM_TILE_COVERAGE_OUTPUT,
    ERA5LAND_FEATURE_DIR,
    ERA5LAND_RAW_DIR,
    GITLOOKUP_BUILD_CLC_SCRIPT,
    GITLOOKUP_BUILD_DEM_SCRIPT,
    GITLOOKUP_BUILD_WEATHER_SCRIPT,
    GITLOOKUP_ERA5_SCRIPT,
    GURS_RAW_DIR,
    MUNICIPALITY_MONTHLY_PANEL_OUTPUT,
    MUNICIPALITY_WEEKLY_PANEL_OUTPUT,
    PANEL_MANIFEST_OUTPUT,
    REPORTS_DIR,
    SLOVENIA_MONTHLY_PANEL_OUTPUT,
    SLOVENIA_YEARLY_PANEL_OUTPUT,
    WEATHER_DAILY_OUTPUT,
    WEATHER_OVERLAY_OUTPUT,
    WEATHER_WEEKLY_MANIFEST,
    WEATHER_WEEKLY_OUTPUT,
    ensure_project_dirs,
    run_subprocess,
    timestamp_utc,
    write_json,
)


RAW_ERA5_PATTERN = re.compile(r"era5land_slovenia_(\d{4})_(\d{2})\.nc$")
DEFAULT_HISTORICAL_MODEL_END_DATE = "2025-12-31"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the historical predictive data pipeline inside the predictive workspace."
        )
    )
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-era5-transform", action="store_true")
    parser.add_argument("--skip-weather", action="store_true")
    parser.add_argument("--skip-dem", action="store_true")
    parser.add_argument("--skip-clc", action="store_true")
    parser.add_argument("--skip-panels", action="store_true")
    parser.add_argument(
        "--start-date",
        help="Optional override start date for ERA5 transform and municipality weather build.",
    )
    parser.add_argument(
        "--end-date",
        help="Optional override end date for ERA5 transform and municipality weather build.",
    )
    return parser


def infer_era5_date_window(raw_dir: Path) -> tuple[str, str]:
    matches: list[tuple[int, int]] = []
    for path in (raw_dir / "hourly").glob("*.nc"):
        match = RAW_ERA5_PATTERN.match(path.name)
        if not match:
            continue
        matches.append((int(match.group(1)), int(match.group(2))))

    if not matches:
        raise FileNotFoundError(f"No ERA5 raw monthly files found in {(raw_dir / 'hourly')}")

    first_year, first_month = min(matches)
    last_year, last_month = max(matches)
    last_day = calendar.monthrange(last_year, last_month)[1]
    return (
        date(first_year, first_month, 1).isoformat(),
        date(last_year, last_month, last_day).isoformat(),
    )


def write_markdown_report(results: list[dict[str, object]]) -> None:
    lines = [
        "# Predictive Historical Data Pipeline Report",
        "",
        f"- generated at: `{timestamp_utc()}`",
        "",
    ]
    for result in results:
        lines.append(f"## {result['step']}")
        lines.append("")
        lines.append(f"- exit code: `{result['exit_code']}`")
        lines.append("")
        lines.append("```powershell")
        lines.append(" ".join(result["command"]))
        lines.append("```")
        lines.append("")
        lines.append("### STDOUT")
        lines.append("")
        lines.append("```text")
        lines.append((result["stdout"] or "<empty>").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("### STDERR")
        lines.append("")
        lines.append("```text")
        lines.append((result["stderr"] or "<empty>").rstrip())
        lines.append("```")
        lines.append("")
    (REPORTS_DIR / "predictive_historical_data_pipeline_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_project_dirs()

    start_date, end_date = infer_era5_date_window(ERA5LAND_RAW_DIR)
    if end_date > DEFAULT_HISTORICAL_MODEL_END_DATE:
        end_date = DEFAULT_HISTORICAL_MODEL_END_DATE
    if args.start_date:
        start_date = args.start_date
    if args.end_date:
        end_date = args.end_date

    commands: list[tuple[str, list[str]]] = []
    if not args.skip_sync:
        commands.append(
            (
                "sync_reference_inputs",
                [
                    sys.executable,
                    str(Path(__file__).resolve().parent / "sync_reference_inputs.py"),
                ],
            )
        )
    if not args.skip_era5_transform:
        commands.append(
            (
                "era5_transform_only",
                [
                    sys.executable,
                    str(GITLOOKUP_ERA5_SCRIPT),
                    "--transform-only",
                    "--start-date",
                    start_date,
                    "--end-date",
                    end_date,
                    "--raw-dir",
                    str(ERA5LAND_RAW_DIR),
                    "--feature-dir",
                    str(ERA5LAND_FEATURE_DIR),
                ],
            )
        )
    if not args.skip_weather:
        commands.append(
            (
                "build_municipality_weather",
                [
                    sys.executable,
                    str(GITLOOKUP_BUILD_WEATHER_SCRIPT),
                    "--source-dir",
                    str(ERA5LAND_FEATURE_DIR / "hourly"),
                    "--geojson-path",
                    str(GURS_RAW_DIR / "obcine-gurs-rpe.geojson"),
                    "--start-date",
                    start_date,
                    "--end-date",
                    end_date,
                    "--overlay-output",
                    str(WEATHER_OVERLAY_OUTPUT),
                    "--daily-output",
                    str(WEATHER_DAILY_OUTPUT),
                    "--weekly-output",
                    str(WEATHER_WEEKLY_OUTPUT),
                    "--manifest-output",
                    str(WEATHER_WEEKLY_MANIFEST),
                ],
            )
        )
    if not args.skip_dem:
        commands.append(
            (
                "build_municipality_dem",
                [
                    sys.executable,
                    str(GITLOOKUP_BUILD_DEM_SCRIPT),
                    "--dem-dir",
                    str(DEM_RAW_DIR),
                    "--geojson-path",
                    str(GURS_RAW_DIR / "obcine-gurs-rpe.geojson"),
                    "--tile-coverage-output",
                    str(DEM_TILE_COVERAGE_OUTPUT),
                    "--summary-output",
                    str(DEM_SUMMARY_OUTPUT),
                    "--manifest-output",
                    str(DEM_MANIFEST_OUTPUT),
                ],
            )
        )
    if not args.skip_clc:
        commands.append(
            (
                "build_municipality_clc",
                [
                    sys.executable,
                    str(GITLOOKUP_BUILD_CLC_SCRIPT),
                    "--raster-path",
                    str(
                        CLC_RAW_DIR
                        / "u2018_clc2018_v2020_20u1_raster100m"
                        / "DATA"
                        / "U2018_CLC2018_V2020_20u1.tif"
                    ),
                    "--geojson-path",
                    str(GURS_RAW_DIR / "obcine-gurs-rpe.geojson"),
                    "--sampling-output",
                    str(CLC_SAMPLING_OUTPUT),
                    "--summary-output",
                    str(CLC_SUMMARY_OUTPUT),
                    "--manifest-output",
                    str(CLC_MANIFEST_OUTPUT),
                ],
            )
        )
    if not args.skip_panels:
        commands.append(
            (
                "build_predictive_panels",
                [
                    sys.executable,
                    str(Path(__file__).resolve().parent / "build_predictive_panels.py"),
                    "--weekly-output",
                    str(MUNICIPALITY_WEEKLY_PANEL_OUTPUT),
                    "--municipality-monthly-output",
                    str(MUNICIPALITY_MONTHLY_PANEL_OUTPUT),
                    "--slovenia-monthly-output",
                    str(SLOVENIA_MONTHLY_PANEL_OUTPUT),
                    "--slovenia-yearly-output",
                    str(SLOVENIA_YEARLY_PANEL_OUTPUT),
                    "--manifest-output",
                    str(PANEL_MANIFEST_OUTPUT),
                ],
            )
        )

    results: list[dict[str, object]] = []
    overall_exit = 0
    for step, command in commands:
        outcome = run_subprocess(command)
        results.append({"step": step, **outcome})
        print(f"{step}: exit {outcome['exit_code']}")
        if outcome["exit_code"] != 0:
            overall_exit = int(outcome["exit_code"])
            break

    payload = {
        "generated_at_utc": timestamp_utc(),
        "start_date": start_date,
        "end_date": end_date,
        "results": results,
    }
    write_json(REPORTS_DIR / "predictive_historical_data_pipeline_report.json", payload)
    write_markdown_report(results)
    print(
        f"Historical predictive pipeline report created: "
        f"{(REPORTS_DIR / 'predictive_historical_data_pipeline_report.md').resolve()}"
    )
    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
