from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline_utils import ensure_project_dirs, forecast_output_dir, timestamp_utc, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COPERNICUS_DATA_DIR = PROJECT_ROOT / "Copernicus_predictive_data"
MODEL_A_DIR = COPERNICUS_DATA_DIR / "model_a_operational"
RUNS_DIR = MODEL_A_DIR / "runs"
SLOVENIA_BBOX_NWSE = [46.9, 13.3, 45.3, 16.6]
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]

MODEL_A_APPLICABLE_FAMILIES = [
    "copernicus_temperature",
    "copernicus_humidity",
    "copernicus_precipitation",
    "copernicus_soil",
]
DEFAULT_FAMILIES = ["copernicus_humidity", "copernicus_precipitation"]
DEFAULT_LEADTIME_MONTHS = ["1", "2", "3", "4", "5", "6"]
VARIABLE_FAMILY_MAP = {
    "copernicus_temperature": ["2m_temperature"],
    "copernicus_humidity": ["2m_temperature", "2m_dewpoint_temperature"],
    "copernicus_precipitation": ["total_precipitation"],
    "copernicus_soil": ["soil_temperature_level_1"],
}
VARIABLE_FAMILY_REQUEST_MODE = {
    "copernicus_temperature": "combined_file",
    "copernicus_humidity": "combined_file",
    "copernicus_precipitation": "combined_file",
    "copernicus_soil": "split_files",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def month_range_label(months: list[str]) -> str:
    if not months:
        return "no-months"
    if len(months) == 1:
        return months[0]
    return f"{months[0]}-{months[-1]}"


def default_months_for_year(year: str) -> list[str]:
    now = datetime.now()
    if year == str(now.year):
        return [f"{month:02d}" for month in range(1, now.month + 1)]
    return [f"{month:02d}" for month in range(1, 13)]


def build_parser() -> argparse.ArgumentParser:
    current_year = str(datetime.now().year)
    parser = argparse.ArgumentParser(
        description=(
            "Run the Slovenia-only Model A operational Copernicus forecast download "
            "in partitioned batches with per-batch reports."
        )
    )
    parser.add_argument(
        "--year",
        default=current_year,
        help=f"Initialization year to download. Default: {current_year}.",
    )
    parser.add_argument(
        "--months",
        nargs="+",
        help="Initialization months in MM format. Default: Jan through current month for the current year.",
    )
    parser.add_argument(
        "--variable-family",
        nargs="+",
        choices=MODEL_A_APPLICABLE_FAMILIES,
        default=list(DEFAULT_FAMILIES),
        help="Model A forecast families to download. Default: humidity and precipitation.",
    )
    parser.add_argument(
        "--leadtime-months",
        nargs="+",
        default=list(DEFAULT_LEADTIME_MONTHS),
        help="Lead months to request. Default: 1 2 3 4 5 6.",
    )
    parser.add_argument(
        "--system",
        default="51",
        help="Seasonal system identifier. Default: 51.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download existing files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write manifests and reports only without live CDS downloads.",
    )
    parser.add_argument(
        "--clear-proxy-env",
        action="store_true",
        help="Temporarily clear proxy environment variables for this CDS run.",
    )
    parser.add_argument(
        "--retry-max",
        type=int,
        default=3,
        help="Maximum CDS client retries for recoverable errors. Default: 3.",
    )
    parser.add_argument(
        "--sleep-max",
        type=int,
        default=10,
        help="Maximum retry sleep seconds for the CDS client. Default: 10.",
    )
    return parser


def normalize_months(months: list[str]) -> list[str]:
    normalized: list[str] = []
    for month in months:
        if not month.isdigit():
            raise ValueError(f"Invalid month: {month}")
        value = int(month)
        if value < 1 or value > 12:
            raise ValueError(f"Invalid month: {month}")
        normalized.append(f"{value:02d}")
    return normalized


def count_grib_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*.grib"))


def clear_proxy_environment() -> list[str]:
    cleared: list[str] = []
    for name in PROXY_ENV_VARS:
        if os.environ.get(name):
            os.environ.pop(name, None)
            cleared.append(name)
    return cleared


def build_request(
    *,
    variable_family: str,
    system: str,
    year: str,
    month: str,
    leadtime_months: list[str],
    requested_variables: list[str] | None = None,
) -> dict[str, object]:
    variables = requested_variables or VARIABLE_FAMILY_MAP[variable_family]
    return {
        "format": "grib",
        "originating_centre": "ecmwf",
        "system": str(system),
        "variable": variables if len(variables) > 1 else variables[0],
        "year": year,
        "month": month,
        "area": list(SLOVENIA_BBOX_NWSE),
        "product_type": "monthly_mean",
        "leadtime_month": list(leadtime_months),
    }


def build_target_path(
    output_dir: Path,
    *,
    variable_family: str,
    system: str,
    year: str,
    month: str,
    leadtime_months: list[str],
    request_variable_name: str | None = None,
) -> Path:
    lead_min = min(int(value) for value in leadtime_months)
    lead_max = max(int(value) for value in leadtime_months)
    variable_suffix = ""
    if request_variable_name:
        variable_suffix = f"_rawvar_{request_variable_name}"
    filename = (
        f"seasonal-monthly-single-levels_ecmwf_system_{system}_{variable_family}_"
        f"init_{year}_{month}_lead_{lead_min}-{lead_max}{variable_suffix}.grib"
    )
    return output_dir / filename


def request_units_for_family(
    *,
    variable_family: str,
    year: str,
    months: list[str],
    leadtime_months: list[str],
    system: str,
    output_dir: Path,
) -> list[dict[str, object]]:
    request_mode = VARIABLE_FAMILY_REQUEST_MODE.get(variable_family, "combined_file")
    units: list[dict[str, object]] = []
    family_variables = list(VARIABLE_FAMILY_MAP[variable_family])

    for month in months:
        if request_mode == "split_files":
            for raw_variable in family_variables:
                requested_variables = [raw_variable]
                units.append(
                    {
                        "year": year,
                        "month": month,
                        "request_mode": request_mode,
                        "requested_variables": requested_variables,
                        "request_variable_name": raw_variable,
                        "target_path": build_target_path(
                            output_dir,
                            variable_family=variable_family,
                            system=system,
                            year=year,
                            month=month,
                            leadtime_months=leadtime_months,
                            request_variable_name=raw_variable,
                        ),
                    }
                )
        else:
            units.append(
                {
                    "year": year,
                    "month": month,
                    "request_mode": request_mode,
                    "requested_variables": family_variables,
                    "request_variable_name": None,
                    "target_path": build_target_path(
                        output_dir,
                        variable_family=variable_family,
                        system=system,
                        year=year,
                        month=month,
                        leadtime_months=leadtime_months,
                        request_variable_name=None,
                    ),
                }
            )
    return units


def write_request_manifest(
    *,
    output_dir: Path,
    variable_family: str,
    year: str,
    months: list[str],
    leadtime_months: list[str],
    system: str,
) -> None:
    request_units = request_units_for_family(
        variable_family=variable_family,
        year=year,
        months=months,
        leadtime_months=leadtime_months,
        system=system,
        output_dir=output_dir,
    )
    manifest = {
        "generated_at_utc": timestamp_utc(),
        "dataset_kind": "monthly_stats",
        "dataset_name": "seasonal-monthly-single-levels",
        "variable_family": variable_family,
        "request_mode": VARIABLE_FAMILY_REQUEST_MODE.get(variable_family, "combined_file"),
        "originating_centre": "ecmwf",
        "system": str(system),
        "variables": list(VARIABLE_FAMILY_MAP[variable_family]),
        "leadtime_months": list(leadtime_months),
        "bbox_nwse": list(SLOVENIA_BBOX_NWSE),
        "format": "grib",
        "output_dir": str(output_dir),
        "request_count": len(request_units),
        "requests": [
            {
                "dataset_name": "seasonal-monthly-single-levels",
                "variable_family": variable_family,
                "year": unit["year"],
                "month": unit["month"],
                "request_mode": unit["request_mode"],
                "requested_variables": unit["requested_variables"],
                "request_variable_name": unit["request_variable_name"],
                "target_path": str(unit["target_path"]),
                "request": build_request(
                    variable_family=variable_family,
                    system=system,
                    year=str(unit["year"]),
                    month=str(unit["month"]),
                    leadtime_months=leadtime_months,
                    requested_variables=list(unit["requested_variables"]),
                ),
            }
            for unit in request_units
        ],
        "mode": "live",
    }
    write_json(output_dir / "request_manifest.json", manifest)


def write_markdown_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model A Partitioned Download Report",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- batch id: `{payload['batch_id']}`",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- mode: `{payload['mode']}`",
        f"- dataset: `{payload['dataset_kind']}`",
        f"- variable family: `{payload['variable_family']}`",
        f"- request mode: `{payload['request_mode']}`",
        f"- year: `{payload['year']}`",
        f"- months: `{', '.join(payload['months'])}`",
        f"- lead months: `{', '.join(payload['leadtime_months'])}`",
        f"- slovenia-only extraction: `{payload['slovenia_only_extraction']}`",
        f"- exit code: `{payload['exit_code']}`",
        f"- duration seconds: `{payload['duration_seconds']}`",
        f"- grib files before: `{payload['grib_count_before']}`",
        f"- grib files after: `{payload['grib_count_after']}`",
        f"- new grib files detected: `{payload['new_grib_files']}`",
        "",
        "## Requests",
        "",
        "```json",
        json.dumps(payload["requests"], indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_summary_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model A Run Summary",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- year: `{payload['year']}`",
        f"- months: `{', '.join(payload['months'])}`",
        f"- total batches: `{payload['total_batches']}`",
        f"- successful batches: `{payload['successful_batches']}`",
        f"- total new grib files: `{payload['total_new_grib_files']}`",
        f"- total duration seconds: `{payload['total_duration_seconds']}`",
        "",
        "## Batch Results",
        "",
    ]

    for batch in payload["batches"]:
        lines.extend(
            [
                f"### {batch['batch_id']}",
                "",
                f"- family: `{batch['variable_family']}`",
                f"- exit code: `{batch['exit_code']}`",
                f"- duration seconds: `{batch['duration_seconds']}`",
                f"- new grib files: `{batch['new_grib_files']}`",
                f"- json report: `{batch['json_report']}`",
                f"- markdown report: `{batch['markdown_report']}`",
                "",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch(
    *,
    run_id: str,
    dataset_kind: str,
    variable_family: str,
    year: str,
    months: list[str],
    leadtime_months: list[str],
    system: str,
    force: bool,
    run_dir: Path,
    client: object | None,
    dry_run: bool,
) -> dict[str, object]:
    output_dir = forecast_output_dir(variable_family, dataset_kind)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_request_manifest(
        output_dir=output_dir,
        variable_family=variable_family,
        year=year,
        months=months,
        leadtime_months=leadtime_months,
        system=system,
    )
    grib_count_before = count_grib_files(output_dir)
    batch_id = f"{dataset_kind}_{variable_family}_{year}_{month_range_label(months)}"
    requests_payload: list[dict[str, object]] = []

    batch_start = time.perf_counter()
    exit_code = 0
    request_units = request_units_for_family(
        variable_family=variable_family,
        year=year,
        months=months,
        leadtime_months=leadtime_months,
        system=system,
        output_dir=output_dir,
    )
    for unit in request_units:
        request = build_request(
            variable_family=variable_family,
            system=system,
            year=str(unit["year"]),
            month=str(unit["month"]),
            leadtime_months=leadtime_months,
            requested_variables=list(unit["requested_variables"]),
        )
        target_path = Path(unit["target_path"])
        requests_payload.append(
            {
                "year": unit["year"],
                "month": unit["month"],
                "request_mode": unit["request_mode"],
                "requested_variables": list(unit["requested_variables"]),
                "request_variable_name": unit["request_variable_name"],
                "target_path": str(target_path),
                "request": request,
            }
        )
        if target_path.exists() and not force:
            continue
        if dry_run:
            continue
        try:
            client.retrieve("seasonal-monthly-single-levels", request, str(target_path))
        except Exception as exc:
            requests_payload[-1]["error"] = str(exc)
            exit_code = 1
            break
    duration_seconds = round(time.perf_counter() - batch_start, 1)
    grib_count_after = count_grib_files(output_dir)

    json_report = run_dir / f"{batch_id}.json"
    markdown_report = run_dir / f"{batch_id}.md"
    payload = {
        "run_id": run_id,
        "batch_id": batch_id,
        "generated_at_utc": timestamp_utc(),
        "mode": "dry_run" if dry_run else "live",
        "dataset_kind": dataset_kind,
        "variable_family": variable_family,
        "request_mode": VARIABLE_FAMILY_REQUEST_MODE.get(variable_family, "combined_file"),
        "year": year,
        "months": months,
        "leadtime_months": leadtime_months,
        "system": system,
        "slovenia_only_extraction": True,
        "output_dir": str(output_dir),
        "grib_count_before": grib_count_before,
        "grib_count_after": grib_count_after,
        "new_grib_files": grib_count_after - grib_count_before,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "requests": requests_payload,
        "json_report": str(json_report),
        "markdown_report": str(markdown_report),
    }
    write_json(json_report, payload)
    write_markdown_report(markdown_report, payload)
    return payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_project_dirs()

    try:
        months = normalize_months(args.months or default_months_for_year(args.year))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

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

    print(
        f"Starting Model A partitioned download run `{run_id}` for year {args.year} "
        f"and months {', '.join(months)}.",
        flush=True,
    )
    if cleared_proxy_vars:
        print(
            "Cleared proxy environment variables for this run: "
            + ", ".join(cleared_proxy_vars),
            flush=True,
        )

    batches: list[dict[str, object]] = []
    dataset_kind = "monthly_stats"
    run_start = time.perf_counter()
    for index, variable_family in enumerate(args.variable_family, start=1):
        print(
            f"[batch {index}/{len(args.variable_family)}] "
            f"{dataset_kind} -> {variable_family}",
            flush=True,
        )
        payload = run_batch(
            run_id=run_id,
            dataset_kind=dataset_kind,
            variable_family=variable_family,
            year=args.year,
            months=months,
            leadtime_months=args.leadtime_months,
            system=args.system,
            force=args.force,
            run_dir=run_dir,
            client=client,
            dry_run=args.dry_run,
        )
        batches.append(payload)
        print(
            f"Completed {payload['batch_id']} with exit {payload['exit_code']} "
            f"and {payload['new_grib_files']} new files.",
            flush=True,
        )
        if payload["exit_code"] != 0:
            print(
                f"Stopping run because batch {payload['batch_id']} failed. "
                f"See {payload['markdown_report']}",
                file=sys.stderr,
                flush=True,
            )
            break

    total_duration_seconds = round(time.perf_counter() - run_start, 1)
    successful_batches = sum(1 for batch in batches if batch["exit_code"] == 0)
    summary_payload = {
        "run_id": run_id,
        "generated_at_utc": timestamp_utc(),
        "year": args.year,
        "months": months,
        "dataset_kind": dataset_kind,
        "slovenia_only_extraction": True,
        "total_batches": len(batches),
        "successful_batches": successful_batches,
        "total_new_grib_files": sum(batch["new_grib_files"] for batch in batches),
        "total_duration_seconds": total_duration_seconds,
        "batches": batches,
    }
    summary_json = run_dir / "run_summary.json"
    summary_md = run_dir / "run_summary.md"
    write_json(summary_json, summary_payload)
    write_run_summary_markdown(summary_md, summary_payload)

    print(f"Run summary written to: {summary_md}", flush=True)
    return 0 if successful_batches == len(args.variable_family) else 1


if __name__ == "__main__":
    raise SystemExit(main())
