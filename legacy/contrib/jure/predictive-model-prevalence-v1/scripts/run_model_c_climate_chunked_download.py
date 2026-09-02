from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline_utils import CLIMATE_ATLAS_RAW_DIR, ensure_project_dirs, timestamp_utc, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COPERNICUS_DATA_DIR = PROJECT_ROOT / "Copernicus_predictive_data"
MODEL_C_DIR = COPERNICUS_DATA_DIR / "model_c_climate"
RUNS_DIR = MODEL_C_DIR / "runs"
SLOVENIA_BBOX_NWSE = [46.9, 13.3, 45.3, 16.6]
DATASET_NAME = "multi-origin-c3s-atlas"
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]

CHUNK_PLAN = [
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "historical",
        "period": "1970-2005",
        "variable": "monthly_temperature",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "air_temperature_c_mean",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "historical",
        "period": "1970-2005",
        "variable": "monthly_precipitation",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "precipitation_sum_mm",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "historical",
        "period": "1970-2005",
        "variable": "monthly_near_surface_specific_humidity",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "relative_humidity_pct_mean (proxy)",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_4_5",
        "period": "2006-2100",
        "variable": "monthly_temperature",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "air_temperature_c_mean",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_4_5",
        "period": "2006-2100",
        "variable": "monthly_precipitation",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "precipitation_sum_mm",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_4_5",
        "period": "2006-2100",
        "variable": "monthly_near_surface_specific_humidity",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "relative_humidity_pct_mean (proxy)",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_8_5",
        "period": "2006-2100",
        "variable": "monthly_temperature",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "air_temperature_c_mean",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_8_5",
        "period": "2006-2100",
        "variable": "monthly_precipitation",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "precipitation_sum_mm",
    },
    {
        "origin": "cordex_eur_11",
        "domain": "euro_cordex",
        "experiment": "rcp_8_5",
        "period": "2006-2100",
        "variable": "monthly_near_surface_specific_humidity",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "relative_humidity_pct_mean (proxy)",
    },
    {
        "origin": "cmip6",
        "domain": "global",
        "experiment": "historical",
        "period": "1850-2014",
        "variable": "monthly_soil_moisture_in_upper_soil_portion",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "soil_water_layer_1_m3_m3_mean (proxy)",
    },
    {
        "origin": "cmip6",
        "domain": "global",
        "experiment": "ssp2_4_5",
        "period": "2015-2100",
        "variable": "monthly_soil_moisture_in_upper_soil_portion",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "soil_water_layer_1_m3_m3_mean (proxy)",
    },
    {
        "origin": "cmip6",
        "domain": "global",
        "experiment": "ssp5_8_5",
        "period": "2015-2100",
        "variable": "monthly_soil_moisture_in_upper_soil_portion",
        "bias_adjustment": "no_bias_adjustment",
        "match_label": "soil_water_layer_1_m3_m3_mean (proxy)",
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clear_proxy_environment() -> list[str]:
    cleared: list[str] = []
    for name in PROXY_ENV_VARS:
        if os.environ.get(name):
            os.environ.pop(name, None)
            cleared.append(name)
    return cleared


def chunk_id(chunk: dict[str, str]) -> str:
    return "_".join(
        [
            chunk["origin"],
            chunk["experiment"],
            chunk["period"],
            chunk["variable"],
            "slovenia",
        ]
    )


def target_path_for_chunk(chunk: dict[str, str]) -> Path:
    filename = f"{DATASET_NAME}_{chunk_id(chunk)}.zip"
    return CLIMATE_ATLAS_RAW_DIR / DATASET_NAME / chunk["origin"] / chunk["variable"] / filename


def build_request(chunk: dict[str, str]) -> dict[str, object]:
    return {
        "origin": chunk["origin"],
        "domain": chunk["domain"],
        "experiment": chunk["experiment"],
        "period": chunk["period"],
        "variable": chunk["variable"],
        "bias_adjustment": chunk["bias_adjustment"],
        "area": list(SLOVENIA_BBOX_NWSE),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Model C Slovenia climate-effect Atlas download in reproducible "
            "chunks with per-chunk reports."
        )
    )
    parser.add_argument(
        "--chunk-id",
        nargs="+",
        help="Optional subset of chunk ids to run. Defaults to the full Model C first-pass plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write reports only without live CDS downloads.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download existing chunk files.",
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


def selected_chunks(chunk_ids: list[str] | None) -> list[dict[str, str]]:
    if not chunk_ids:
        return list(CHUNK_PLAN)

    wanted = set(chunk_ids)
    selected = [chunk for chunk in CHUNK_PLAN if chunk_id(chunk) in wanted]
    missing = sorted(wanted - {chunk_id(chunk) for chunk in selected})
    if missing:
        raise ValueError(f"Unknown chunk ids: {', '.join(missing)}")
    return selected


def write_markdown_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model C Chunk Report",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- chunk id: `{payload['chunk_id']}`",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- dataset: `{payload['dataset_name']}`",
        f"- origin: `{payload['origin']}`",
        f"- domain: `{payload['domain']}`",
        f"- experiment: `{payload['experiment']}`",
        f"- period: `{payload['period']}`",
        f"- variable: `{payload['variable']}`",
        f"- past-variable match: `{payload['match_label']}`",
        f"- slovenia bbox: `{payload['area']}`",
        f"- mode: `{payload['mode']}`",
        f"- status: `{payload['status']}`",
        f"- exit code: `{payload['exit_code']}`",
        f"- duration seconds: `{payload['duration_seconds']}`",
        f"- file existed before run: `{payload['file_existed_before']}`",
        f"- file exists after run: `{payload['file_exists_after']}`",
        f"- file size bytes: `{payload['file_size_bytes']}`",
        f"- output path: `{payload['target_path']}`",
        "",
        "## Request",
        "",
        "```json",
        str(payload["request"]),
        "```",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_summary_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model C Run Summary",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- generated at: `{payload['generated_at_utc']}`",
        f"- chunk count: `{payload['chunk_count']}`",
        f"- successful chunks: `{payload['successful_chunks']}`",
        f"- total downloaded bytes: `{payload['total_downloaded_bytes']}`",
        f"- total duration seconds: `{payload['total_duration_seconds']}`",
        "",
        "## Chunk Results",
        "",
    ]
    for chunk in payload["chunks"]:
        lines.extend(
            [
                f"### {chunk['chunk_id']}",
                "",
                f"- origin: `{chunk['origin']}`",
                f"- experiment: `{chunk['experiment']}`",
                f"- period: `{chunk['period']}`",
                f"- variable: `{chunk['variable']}`",
                f"- status: `{chunk['status']}`",
                f"- duration seconds: `{chunk['duration_seconds']}`",
                f"- file size bytes: `{chunk['file_size_bytes']}`",
                f"- markdown report: `{chunk['markdown_report']}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_chunk(
    *,
    client: object | None,
    chunk: dict[str, str],
    run_id: str,
    run_dir: Path,
    dry_run: bool,
    force: bool,
) -> dict[str, object]:
    target_path = target_path_for_chunk(chunk)
    request = build_request(chunk)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    existed_before = target_path.exists()
    status = "planned"
    exit_code = 0
    duration_seconds = 0.0

    if dry_run:
        if existed_before and not force:
            status = "skipped_existing"
        else:
            status = "planned_download"
    else:
        if existed_before and not force:
            status = "skipped_existing"
        else:
            started = time.perf_counter()
            try:
                assert client is not None
                client.retrieve(DATASET_NAME, request, str(target_path))
                status = "downloaded"
            except Exception:
                status = "failed"
                exit_code = 1
                if target_path.exists() and not existed_before:
                    target_path.unlink(missing_ok=True)
            duration_seconds = round(time.perf_counter() - started, 1)

    file_exists_after = target_path.exists()
    file_size_bytes = target_path.stat().st_size if file_exists_after else 0
    payload = {
        "run_id": run_id,
        "chunk_id": chunk_id(chunk),
        "generated_at_utc": timestamp_utc(),
        "dataset_name": DATASET_NAME,
        "origin": chunk["origin"],
        "domain": chunk["domain"],
        "experiment": chunk["experiment"],
        "period": chunk["period"],
        "variable": chunk["variable"],
        "match_label": chunk["match_label"],
        "area": list(SLOVENIA_BBOX_NWSE),
        "request": request,
        "mode": "dry-run" if dry_run else "live",
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration_seconds,
        "file_existed_before": existed_before,
        "file_exists_after": file_exists_after,
        "file_size_bytes": file_size_bytes,
        "target_path": str(target_path),
    }

    json_report = run_dir / f"{payload['chunk_id']}.json"
    markdown_report = run_dir / f"{payload['chunk_id']}.md"
    payload["json_report"] = str(json_report)
    payload["markdown_report"] = str(markdown_report)
    write_json(json_report, payload)
    write_markdown_report(markdown_report, payload)
    return payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_project_dirs()

    try:
        chunks = selected_chunks(args.chunk_id)
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

    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Starting Model C chunked download run `{run_id}` for {len(chunks)} chunks.",
        flush=True,
    )
    if cleared_proxy_vars:
        print(
            "Cleared proxy environment variables for this run: "
            + ", ".join(cleared_proxy_vars),
            flush=True,
        )

    run_start = time.perf_counter()
    chunk_results: list[dict[str, object]] = []
    for index, chunk in enumerate(chunks, start=1):
        label = (
            f"{chunk['origin']} {chunk['experiment']} {chunk['period']} "
            f"{chunk['variable']}"
        )
        print(f"[chunk {index}/{len(chunks)}] {label}", flush=True)
        payload = run_chunk(
            client=client,
            chunk=chunk,
            run_id=run_id,
            run_dir=run_dir,
            dry_run=args.dry_run,
            force=args.force,
        )
        chunk_results.append(payload)
        print(
            f"Completed {payload['chunk_id']} with status {payload['status']} "
            f"and size {payload['file_size_bytes']} bytes.",
            flush=True,
        )
        if payload["exit_code"] != 0:
            print(
                f"Stopping run after failure in {payload['chunk_id']}.",
                file=sys.stderr,
                flush=True,
            )
            break

    summary_payload = {
        "run_id": run_id,
        "generated_at_utc": timestamp_utc(),
        "dataset_name": DATASET_NAME,
        "slovenia_bbox_nwse": list(SLOVENIA_BBOX_NWSE),
        "chunk_count": len(chunk_results),
        "successful_chunks": sum(1 for chunk in chunk_results if chunk["exit_code"] == 0),
        "total_downloaded_bytes": sum(chunk["file_size_bytes"] for chunk in chunk_results),
        "total_duration_seconds": round(time.perf_counter() - run_start, 1),
        "chunks": chunk_results,
    }
    summary_json = run_dir / "run_summary.json"
    summary_md = run_dir / "run_summary.md"
    write_json(summary_json, summary_payload)
    write_run_summary_markdown(summary_md, summary_payload)
    print(f"Run summary written to: {summary_md}", flush=True)

    return 0 if summary_payload["successful_chunks"] == len(chunks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
