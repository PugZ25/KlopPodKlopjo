#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_API_URL = "https://pxweb.stat.si/SiStatData/api/v1/en/Data/2640010S.px"
DEFAULT_OUTPUT = Path("data/raw/surs/obcina_population_sistat.json")
POPULATION_MEASURE_CODE = "45"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download municipality population total data from the official "
            "SURS SiStat API table 2640010S."
        )
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="SURS PxWeb API endpoint for the municipality table.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path for the raw SURS dataset.",
    )
    parser.add_argument(
        "--years",
        help="Optional comma-separated year list. Defaults to all years exposed by the API.",
    )
    parser.add_argument(
        "--include-slovenia",
        action="store_true",
        help="Include the aggregate SLOVENIA row in the raw export.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        metadata = _fetch_json(args.api_url)
        query = _build_query(
            metadata,
            years=_parse_years(args.years),
            include_slovenia=args.include_slovenia,
        )
        dataset = _fetch_json(args.api_url, payload=query)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    municipality_count = dataset.get("size", [0, 0, 0])[1] if isinstance(dataset.get("size"), list) else 0
    year_count = dataset.get("size", [0, 0, 0])[2] if isinstance(dataset.get("size"), list) else 0

    print("SURS municipality population download completed.")
    print(f"- api_url: {args.api_url}")
    print(f"- municipalities: {municipality_count}")
    print(f"- years: {year_count}")
    print(f"- output: {output_path.resolve()}")
    return 0


def _fetch_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch SURS API URL {url}: {exc}") from exc


def _build_query(
    metadata: dict[str, object],
    *,
    years: list[str] | None,
    include_slovenia: bool,
) -> dict[str, object]:
    variables = metadata.get("variables")
    if not isinstance(variables, list):
        raise ValueError("SURS metadata response is missing the variables list.")

    variable_map = {
        variable.get("code"): variable
        for variable in variables
        if isinstance(variable, dict) and variable.get("code")
    }

    municipality_values = list(_require_values(variable_map, "OBČINE"))
    if not include_slovenia:
        municipality_values = [value for value in municipality_values if value != "0"]

    available_years = list(_require_values(variable_map, "LETO"))
    selected_years = years or available_years
    unknown_years = [year for year in selected_years if year not in available_years]
    if unknown_years:
        raise ValueError("Unknown SURS years requested: " + ", ".join(unknown_years))

    return {
        "query": [
            {
                "code": "MERITVE",
                "selection": {
                    "filter": "item",
                    "values": [POPULATION_MEASURE_CODE],
                },
            },
            {
                "code": "OBČINE",
                "selection": {
                    "filter": "item",
                    "values": municipality_values,
                },
            },
            {
                "code": "LETO",
                "selection": {
                    "filter": "item",
                    "values": selected_years,
                },
            },
        ],
        "response": {"format": "json-stat2"},
    }


def _require_values(variable_map: dict[object, dict[str, object]], code: str) -> list[str]:
    variable = variable_map.get(code)
    if not isinstance(variable, dict):
        raise ValueError(f"SURS metadata response is missing variable {code}.")

    values = variable.get("values")
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"SURS metadata response has invalid values for variable {code}.")
    return values


def _parse_years(raw_years: str | None) -> list[str] | None:
    if raw_years is None:
        return None

    years = [value.strip() for value in raw_years.split(",") if value.strip()]
    if not years:
        raise ValueError("When --years is provided, it must contain at least one year.")
    return years


if __name__ == "__main__":
    raise SystemExit(main())
