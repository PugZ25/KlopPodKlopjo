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

from common import MODEL_C_OUTPUT_ROOT, SLOVENIA_BBOX_NWSE, clear_proxy_environment, ensure_dirs, timestamp_utc, write_json


DATASET_NAME = "multi-origin-c3s-atlas"
RAW_ROOT = MODEL_C_OUTPUT_ROOT / "raw" / "climate_atlas"
REPORTS_ROOT = MODEL_C_OUTPUT_ROOT / "reports" / "runs"
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Self-contained Model C Slovenia climate acquisition pipeline. "
            "Outputs stay inside this reproducible_acquisition_pipelines folder."
        )
    )
    parser.add_argument(
        "--chunk-id",
        nargs="+",
        help="Optional subset of chunk ids to run. Default: full first-pass Model C package.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write reports only without downloading files.")
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    parser.add_argument("--clear-proxy-env", action="store_true", help="Clear proxy environment variables.")
    parser.add_argument("--retry-max", type=int, default=3, help="Maximum CDS retries. Default: 3.")
    parser.add_argument("--sleep-max", type=int, default=10, help="Maximum CDS retry sleep seconds. Default: 10.")
    return parser


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


def selected_chunks(chunk_ids: list[str] | None) -> list[dict[str, str]]:
    if not chunk_ids:
        return list(CHUNK_PLAN)
    wanted = set(chunk_ids)
    selected = [chunk for chunk in CHUNK_PLAN if chunk_id(chunk) in wanted]
    missing = sorted(wanted - {chunk_id(chunk) for chunk in selected})
    if missing:
        raise ValueError(f"Unknown chunk ids: {', '.join(missing)}")
    return selected


def target_path(chunk: dict[str, str]) -> Path:
    filename = f"{DATASET_NAME}_{chunk_id(chunk)}.zip"
    return RAW_ROOT / DATASET_NAME / chunk["origin"] / chunk["variable"] / filename


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


def write_chunk_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Model C Chunk Report",
        "",
        f"- run id: `{payload['run_id']}`",
        f"- chunk id: `{payload['chunk_id']}`",
        f"- origin: `{payload['origin']}`",
        f"- domain: `{payload['domain']}`",
        f"- experiment: `{payload['experiment']}`",
        f"- period: `{payload['period']}`",
        f"- variable: `{payload['variable']}`",
        f"- past-variable match: `{payload['match_label']}`",
        f"- mode: `{payload['mode']}`",
        f"- status: `{payload['status']}`",
        f"- duration seconds: `{payload['duration_seconds']}`",
        f"- file size bytes: `{payload['file_size_bytes']}`",
        f"- output path: `{payload['target_path']}`",
        "",
        "## Request",
        "",
        "```json",
        json.dumps(payload["request"], indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_summary(path: Path, payload: dict[str, object]) -> None:
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
    ]
    for item in payload["chunks"]:
        lines.extend(
            [
                f"## {item['chunk_id']}",
                "",
                f"- status: `{item['status']}`",
                f"- duration seconds: `{item['duration_seconds']}`",
                f"- file size bytes: `{item['file_size_bytes']}`",
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

    run_id = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPORTS_ROOT / run_id
    ensure_dirs(run_dir)

    print(f"Starting clean Model C pipeline run `{run_id}` for {len(chunks)} chunks.", flush=True)
    if cleared_proxy_vars:
        print(
            "Cleared proxy environment variables for this run: "
            + ", ".join(cleared_proxy_vars),
            flush=True,
        )

    chunk_results: list[dict[str, object]] = []
    run_started = time.perf_counter()
    for index, chunk in enumerate(chunks, start=1):
        started = time.perf_counter()
        print(
            f"[chunk {index}/{len(chunks)}] {chunk['origin']} {chunk['experiment']} "
            f"{chunk['period']} {chunk['variable']}",
            flush=True,
        )
        request = build_request(chunk)
        output_file = target_path(chunk)
        ensure_dirs(output_file.parent)
        file_size_bytes = output_file.stat().st_size if output_file.exists() else 0
        status = "planned_download"

        if args.dry_run:
            status = "planned_download"
        else:
            if output_file.exists() and not args.force:
                status = "skipped_existing"
            else:
                try:
                    assert client is not None
                    client.retrieve(DATASET_NAME, request, str(output_file))
                    status = "downloaded"
                except Exception:
                    status = "failed"
                file_size_bytes = output_file.stat().st_size if output_file.exists() else 0

        duration_seconds = round(time.perf_counter() - started, 1)
        payload = {
            "run_id": run_id,
            "generated_at_utc": timestamp_utc(),
            "chunk_id": chunk_id(chunk),
            "origin": chunk["origin"],
            "domain": chunk["domain"],
            "experiment": chunk["experiment"],
            "period": chunk["period"],
            "variable": chunk["variable"],
            "match_label": chunk["match_label"],
            "mode": "dry-run" if args.dry_run else "live",
            "status": status,
            "duration_seconds": duration_seconds,
            "file_size_bytes": file_size_bytes,
            "target_path": str(output_file),
            "request": request,
        }
        json_report = run_dir / f"{payload['chunk_id']}.json"
        markdown_report = run_dir / f"{payload['chunk_id']}.md"
        payload["json_report"] = str(json_report)
        payload["markdown_report"] = str(markdown_report)
        write_json(json_report, payload)
        write_chunk_report(markdown_report, payload)
        chunk_results.append(payload)
        print(
            f"Completed {payload['chunk_id']} with status {status} "
            f"and size {file_size_bytes} bytes.",
            flush=True,
        )
        if status == "failed":
            print(f"Stopping after failure in {payload['chunk_id']}.", file=sys.stderr, flush=True)
            break

    summary = {
        "run_id": run_id,
        "generated_at_utc": timestamp_utc(),
        "chunk_count": len(chunk_results),
        "successful_chunks": sum(1 for item in chunk_results if item["status"] != "failed"),
        "total_downloaded_bytes": sum(item["file_size_bytes"] for item in chunk_results),
        "total_duration_seconds": round(time.perf_counter() - run_started, 1),
        "chunks": chunk_results,
    }
    write_json(run_dir / "run_summary.json", summary)
    write_run_summary(run_dir / "run_summary.md", summary)
    print(f"Run summary written to: {run_dir / 'run_summary.md'}", flush=True)
    return 0 if summary["successful_chunks"] == len(chunks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
