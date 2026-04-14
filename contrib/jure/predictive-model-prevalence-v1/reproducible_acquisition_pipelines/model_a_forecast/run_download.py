from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import MODEL_A_OUTPUT_ROOT, SLOVENIA_BBOX_NWSE, clear_proxy_environment, ensure_dirs, timestamp_utc, write_json


DATASET_NAME = "seasonal-monthly-single-levels"
SYSTEM = "51"
ORIGINATING_CENTRE = "ecmwf"
LEADTIME_MONTHS = ["1", "2", "3", "4", "5", "6"]
RAW_ROOT = MODEL_A_OUTPUT_ROOT / "raw" / "copernicus_forecast"
REPORTS_ROOT = MODEL_A_OUTPUT_ROOT / "reports" / "runs"
FAMILY_MAP = {
    "copernicus_temperature": {
        "variables": ["2m_temperature"],
        "match_label": "air_temperature_c_mean",
    },
    "copernicus_humidity": {
        "variables": ["2m_temperature", "2m_dewpoint_temperature"],
        "match_label": "relative_humidity_pct_mean via temperature and dewpoint",
    },
    "copernicus_precipitation": {
        "variables": ["total_precipitation"],
        "match_label": "precipitation_sum_mm",
    },
    "copernicus_soil": {
        "variables": [
            "soil_temperature_level_1",
            "soil_temperature_level_2",
            "volumetric_soil_water_layer_1",
            "volumetric_soil_water_layer_2",
        ],
        "match_label": "soil temperature and soil water backbone",
    },
}


def build_parser() -> argparse.ArgumentParser:
    current_year = str(datetime.now().year)
    parser = argparse.ArgumentParser(
        description=(
            "Self-contained Model A Slovenia forecast acquisition pipeline. "
            "Outputs stay inside this reproducible_acquisition_pipelines folder."
        )
    )
    parser.add_argument("--year", default=current_year, help=f"Initialization year. Default: {current_year}.")
    parser.add_argument(
        "--months",
        nargs="+",
        help="Initialization months in MM format. Default: Jan through current month for the current year.",
    )
    parser.add_argument(
        "--family",
        nargs="+",
        choices=sorted(FAMILY_MAP),
        default=list(FAMILY_MAP),
        help="Forecast families to download. Default: all four Model A families.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write reports only without downloading files.")
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    parser.add_argument("--clear-proxy-env", action="store_true", help="Clear proxy environment variables.")
    parser.add_argument("--retry-max", type=int, default=3, help="Maximum CDS retries. Default: 3.")
    parser.add_argument("--sleep-max", type=int, default=10, help="Maximum CDS retry sleep seconds. Default: 10.")
    return parser


def normalize_months(year: str, months: list[str] | None) -> list[str]:
    if months is None:
        now = datetime.now()
        if year == str(now.year):
            return [f"{month:02d}" for month in range(1, now.month + 1)]
        return [f"{month:02d}" for month in range(1, 13)]

    normalized: list[str] = []
    for month in months:
        if not month.isdigit():
            raise ValueError(f"Invalid month: {month}")
        value = int(month)
        if value < 1 or value > 12:
            raise ValueError(f"Invalid month: {month}")
        normalized.append(f"{value:02d}")
    return normalized


def family_output_dir(family: str) -> Path:
    return RAW_ROOT / family / DATASET_NAME


def target_path(family: str, year: str, month: str) -> Path:
    filename = (
        f"{DATASET_NAME}_{ORIGINATING_CENTRE}_system_{SYSTEM}_{family}_"
        f"init_{year}_{month}_lead_1-6.grib"
    )
    return family_output_dir(family) / filename


def build_request(family: str, year: str, month: str) -> dict[str, object]:
    variables = FAMILY_MAP[family]["variables"]
    return {
        "format": "grib",
        "originating_centre": ORIGINATING_CENTRE,
        "system": SYSTEM,
        "variable": variables if len(variables) > 1 else variables[0],
        "year": year,
        "month": month,
        "area": list(SLOVENIA_BBOX_NWSE),
        "product_type": "monthly_mean",
        "leadtime_month": list(LEADTIME_MONTHS),
    }


def write_manifest(family: str, year: str, months: list[str]) -> None:
    manifest = {
        "generated_at_utc": timestamp_utc(),
        "dataset_name": DATASET_NAME,
        "family": family,
        "match_label": FAMILY_MAP[family]["match_label"],
        "year": year,
        "months": months,
        "area": list(SLOVENIA_BBOX_NWSE),
        "requests": [
            {
                "year": year,
                "month": month,
                "target_path": str(target_path(family, year, month)),
                "request": build_request(family, year, month),
            }
            for month in months
        ],
    }
    write_json(family_output_dir(family) / "request_manifest.json", manifest)


def write_batch_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model A Batch Report",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- family: `{payload['family']}`",
        f"- year: `{payload['year']}`",
        f"- months: `{', '.join(payload['months'])}`",
        f"- mode: `{payload['mode']}`",
        f"- status: `{payload['status']}`",
        f"- downloaded files: `{payload['downloaded_files']}`",
        f"- skipped existing files: `{payload['skipped_existing_files']}`",
        f"- duration seconds: `{payload['duration_seconds']}`",
        "",
        "## Requests",
        "",
        "```json",
        json.dumps(payload["requests"], indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_summary(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model A Run Summary",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- family count: `{payload['family_count']}`",
        f"- successful families: `{payload['successful_families']}`",
        f"- total downloaded files: `{payload['total_downloaded_files']}`",
        f"- total duration seconds: `{payload['total_duration_seconds']}`",
        "",
    ]
    for item in payload["families"]:
        lines.extend(
            [
                f"## {item['family']}",
                "",
                f"- status: `{item['status']}`",
                f"- downloaded files: `{item['downloaded_files']}`",
                f"- skipped existing files: `{item['skipped_existing_files']}`",
                f"- duration seconds: `{item['duration_seconds']}`",
                f"- report: `{item['markdown_report']}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_dirs(RAW_ROOT, REPORTS_ROOT)

    try:
        months = normalize_months(args.year, args.months)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    cleared_proxy_vars: list[str] = []
    if args.clear_proxy_env:
        cleared_proxy_vars = clear_proxy_environment()

    client = None
    if not args.dry_run:
        try:
            import cdsapi
        except ImportError:
            print("Missing dependency: cdsapi", file=sys.stderr)
            return 1
        client = cdsapi.Client(
            quiet=False,
            debug=False,
            progress=True,
            retry_max=args.retry_max,
            sleep_max=args.sleep_max,
        )

    run_id = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPORTS_ROOT / run_id
    ensure_dirs(run_dir)

    print(
        f"Starting clean Model A pipeline run `{run_id}` for families "
        f"{', '.join(args.family)} and months {', '.join(months)}.",
        flush=True,
    )
    if cleared_proxy_vars:
        print(
            "Cleared proxy environment variables for this run: "
            + ", ".join(cleared_proxy_vars),
            flush=True,
        )

    family_results: list[dict[str, object]] = []
    run_started = time.perf_counter()
    for index, family in enumerate(args.family, start=1):
        started = time.perf_counter()
        print(f"[family {index}/{len(args.family)}] {family}", flush=True)
        ensure_dirs(family_output_dir(family))
        write_manifest(family, args.year, months)
        requests = [build_request(family, args.year, month) for month in months]
        downloaded_files = 0
        skipped_existing_files = 0
        status = "planned_download"

        if args.dry_run:
            status = "planned_download"
        else:
            status = "downloaded"
            for month in months:
                target = target_path(family, args.year, month)
                if target.exists() and not args.force:
                    skipped_existing_files += 1
                    continue
                try:
                    assert client is not None
                    client.retrieve(DATASET_NAME, build_request(family, args.year, month), str(target))
                    downloaded_files += 1
                except Exception:
                    status = "failed"
                    break

        duration_seconds = round(time.perf_counter() - started, 1)
        payload = {
            "run_id": run_id,
            "generated_at_utc": timestamp_utc(),
            "family": family,
            "year": args.year,
            "months": months,
            "mode": "dry-run" if args.dry_run else "live",
            "status": status,
            "downloaded_files": downloaded_files,
            "skipped_existing_files": skipped_existing_files,
            "duration_seconds": duration_seconds,
            "requests": requests,
        }
        json_report = run_dir / f"{family}_{args.year}_{months[0]}-{months[-1]}.json"
        markdown_report = run_dir / f"{family}_{args.year}_{months[0]}-{months[-1]}.md"
        payload["json_report"] = str(json_report)
        payload["markdown_report"] = str(markdown_report)
        write_json(json_report, payload)
        write_batch_report(markdown_report, payload)
        family_results.append(payload)
        print(
            f"Completed {family} with status {status}, "
            f"{downloaded_files} downloaded, {skipped_existing_files} skipped.",
            flush=True,
        )
        if status == "failed":
            print(f"Stopping after failure in {family}.", file=sys.stderr, flush=True)
            break

    summary = {
        "run_id": run_id,
        "generated_at_utc": timestamp_utc(),
        "family_count": len(family_results),
        "successful_families": sum(1 for item in family_results if item["status"] != "failed"),
        "total_downloaded_files": sum(item["downloaded_files"] for item in family_results),
        "total_duration_seconds": round(time.perf_counter() - run_started, 1),
        "families": family_results,
    }
    write_json(run_dir / "run_summary.json", summary)
    write_run_summary(run_dir / "run_summary.md", summary)
    print(f"Run summary written to: {run_dir / 'run_summary.md'}", flush=True)
    return 0 if summary["successful_families"] == len(args.family) else 1


if __name__ == "__main__":
    raise SystemExit(main())
