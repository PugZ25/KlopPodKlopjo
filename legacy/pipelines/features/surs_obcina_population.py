from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RAW_INPUT = Path("data/raw/surs/obcina_population_sistat.json")
DEFAULT_OUTPUT = Path("data/processed/training/obcina_surs_log_population_yearly_features.csv")
DEFAULT_MANIFEST_OUTPUT = Path(
    "data/processed/training/obcina_surs_log_population_yearly_features_manifest.json"
)
TABLE_ID = "2640010S"
POPULATION_MEASURE_CODE = "45"
SLOVENIA_CODE = "0"
REQUIRED_DIMENSIONS = ("MERITVE", "OBČINE", "LETO")


@dataclass(frozen=True)
class SursPopulationTables:
    yearly_features: Any
    manifest: dict[str, Any]


def build_obcina_surs_population_yearly_features(
    *,
    raw_input: Path = DEFAULT_RAW_INPUT,
) -> SursPopulationTables:
    import pandas as pd

    if not raw_input.exists():
        raise FileNotFoundError(f"SURS raw JSON not found: {raw_input}")

    payload = json.loads(raw_input.read_text(encoding="utf-8"))
    if "data" in payload:
        payload = payload["data"]

    dimensions = tuple(payload.get("id", []))
    if dimensions != REQUIRED_DIMENSIONS:
        raise ValueError(
            "Unexpected SURS dimension order. "
            f"Expected {REQUIRED_DIMENSIONS}, got {dimensions}."
        )

    size = payload.get("size")
    values = payload.get("value")
    statuses = payload.get("status", {})
    dimension_meta = payload.get("dimension", {})
    if not isinstance(size, list) or not isinstance(values, list):
        raise ValueError("SURS raw JSON is missing size/value arrays.")

    measures = _require_dimension(dimension_meta, "MERITVE")
    municipalities = _require_dimension(dimension_meta, "OBČINE")
    years = _require_dimension(dimension_meta, "LETO")

    if POPULATION_MEASURE_CODE not in measures["index"]:
        raise ValueError(f"SURS raw JSON is missing measure code {POPULATION_MEASURE_CODE}.")

    rows: list[dict[str, Any]] = []
    for municipality_code, municipality_idx in _sorted_items_by_index(municipalities["index"]):
        if municipality_code == SLOVENIA_CODE:
            continue

        municipality_name = municipalities["label"][municipality_code]
        normalized_code = _normalize_municipality_code(municipality_code)

        for year_code, year_idx in _sorted_items_by_index(years["index"]):
            population_value, population_status = _read_dataset_cell(
                values=values,
                statuses=statuses,
                size=size,
                measure_idx=measures["index"][POPULATION_MEASURE_CODE],
                municipality_idx=municipality_idx,
                year_idx=year_idx,
            )

            rows.append(
                {
                    "year": int(year_code),
                    "obcina_sifra": normalized_code,
                    "obcina_naziv": municipality_name,
                    "log_population_total": (
                        math.log1p(float(population_value)) if population_value is not None else None
                    ),
                    "population_total_status": population_status,
                }
            )

    yearly_features = pd.DataFrame(rows)
    if yearly_features.empty:
        raise ValueError("SURS raw JSON did not contain any municipality rows.")

    yearly_features["year"] = yearly_features["year"].astype(int)
    yearly_features["log_population_total"] = pd.to_numeric(
        yearly_features["log_population_total"],
        errors="coerce",
    )

    yearly_features["_obcina_sort_key"] = yearly_features["obcina_sifra"].astype(int)
    yearly_features = yearly_features.sort_values(
        ["year", "_obcina_sort_key"],
        kind="stable",
    ).drop(columns=["_obcina_sort_key"])

    available_years = sorted(
        int(value)
        for value in yearly_features.loc[yearly_features["log_population_total"].notna(), "year"].unique()
    )
    missing_years = sorted(
        int(year)
        for year, count in yearly_features.groupby("year")["log_population_total"].apply(
            lambda column: int(column.isna().sum())
        ).items()
        if count > 0
    )

    yearly_features = yearly_features[
        ["year", "obcina_sifra", "obcina_naziv", "log_population_total"]
    ].reset_index(drop=True)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_input": str(raw_input.resolve()),
        "source_title": payload.get("label", ""),
        "source": payload.get("source", ""),
        "table_id": TABLE_ID,
        "measure_code": POPULATION_MEASURE_CODE,
        "feature_formula": "log(1 + population_total)",
        "row_count": int(len(yearly_features)),
        "municipality_count": int(yearly_features["obcina_sifra"].nunique()),
        "year_count": int(yearly_features["year"].nunique()),
        "year_min": int(yearly_features["year"].min()),
        "year_max": int(yearly_features["year"].max()),
        "latest_available_year": max(available_years) if available_years else None,
        "years_with_missing_values": missing_years,
        "columns": yearly_features.columns.tolist(),
    }
    return SursPopulationTables(yearly_features=yearly_features, manifest=manifest)


def write_obcina_surs_population_yearly_features(
    tables: SursPopulationTables,
    *,
    output_path: Path = DEFAULT_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.yearly_features.to_csv(output_path, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")


def _require_dimension(dimension_meta: dict[str, Any], code: str) -> dict[str, Any]:
    dimension = dimension_meta.get(code)
    if not isinstance(dimension, dict):
        raise ValueError(f"SURS raw JSON is missing dimension {code}.")

    category = dimension.get("category")
    if not isinstance(category, dict):
        raise ValueError(f"SURS raw JSON is missing category data for dimension {code}.")

    index = category.get("index")
    labels = category.get("label")
    if not isinstance(index, dict) or not isinstance(labels, dict):
        raise ValueError(f"SURS raw JSON has invalid category metadata for dimension {code}.")

    return {"index": index, "label": labels}


def _sorted_items_by_index(index_map: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(index_map.items(), key=lambda item: int(item[1]))


def _normalize_municipality_code(raw_code: str) -> str:
    normalized = str(raw_code).strip().lstrip("0")
    return normalized or "0"


def _read_dataset_cell(
    *,
    values: list[Any],
    statuses: dict[str, Any],
    size: list[int],
    measure_idx: int,
    municipality_idx: int,
    year_idx: int,
) -> tuple[Any, str]:
    flat_index = _flat_index((measure_idx, municipality_idx, year_idx), size)
    if flat_index >= len(values):
        raise ValueError(
            f"SURS raw JSON is truncated at flat index {flat_index}; value array length is {len(values)}."
        )
    return values[flat_index], str(statuses.get(str(flat_index), "")).strip()


def _flat_index(indices: tuple[int, ...], size: list[int]) -> int:
    if len(indices) != len(size):
        raise ValueError(f"Index arity {len(indices)} does not match dataset rank {len(size)}.")

    flat_index = 0
    stride = 1
    for dimension_index, dimension_size in zip(reversed(indices), reversed(size), strict=True):
        flat_index += dimension_index * stride
        stride *= dimension_size
    return flat_index
