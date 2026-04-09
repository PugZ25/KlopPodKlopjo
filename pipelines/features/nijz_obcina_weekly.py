from __future__ import annotations

import csv
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_LYME_INPUT = Path("data/raw/nijz/lyme_2015_2025_student.xlsx")
DEFAULT_KME_INPUT = Path("data/raw/nijz/KME_2015_2025_student.xlsx")
DEFAULT_MUNICIPALITY_REFERENCE = Path("data/processed/training/obcina_dem_features.csv")
DEFAULT_OUTPUT = Path("data/processed/training/obcina_weekly_epidemiology.csv")
DEFAULT_MANIFEST_OUTPUT = Path(
    "data/processed/training/obcina_weekly_epidemiology_manifest.json"
)
RAW_MUNICIPALITY_NAME_ALIASES = {
    "SV TROJICA V SLOV GORICAH": "SVETA TROJICA V SLOVENSKIH GORICAH",
    "SVETI JURIJ V SLOV GORICAH": "SVETI JURIJ V SLOVENSKIH GORICAH",
}
WORKBOOK_NAMESPACE = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
CELL_REFERENCE_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")
WEEK_LABEL_PATTERN = re.compile(r"^(?P<iso_year>\d{4})-(?P<iso_week>\d{2})$")
TOTAL_LABEL = "SKUPAJ"
DISEASE_COLUMNS = ("lyme_cases", "kme_cases")
OUTPUT_FIELDNAMES = [
    "week_start",
    "week_end",
    "iso_year",
    "iso_week",
    "obcina_sifra",
    "obcina_naziv",
    "lyme_cases",
    "kme_cases",
    "tick_borne_cases_total",
]


@dataclass(frozen=True)
class EpidemiologyTables:
    rows: list[dict[str, Any]]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class EpidemiologyVerificationResult:
    report: dict[str, Any]

    @property
    def is_valid(self) -> bool:
        return (
            not self.report["csv_row_issues"]
            and not self.report["value_mismatches"]
            and not self.report["missing_csv_keys"]
            and not self.report["unexpected_csv_keys"]
            and not self.report["municipality_row_total_mismatches"]
        )


def normalize_name_for_match(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name)
    without_accents = "".join(ch for ch in ascii_name if not unicodedata.combining(ch))
    normalized = without_accents.upper()
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace(".", " ")
    normalized = normalized.replace("(", " ")
    normalized = normalized.replace(")", " ")
    return " ".join(normalized.split())


def resolve_nijz_municipality_name(raw_name: str) -> str:
    normalized = normalize_name_for_match(raw_name)
    alias_target = RAW_MUNICIPALITY_NAME_ALIASES.get(normalized, normalized)
    return normalize_name_for_match(alias_target)


def iso_week_bounds(iso_year: int, iso_week: int) -> tuple[date, date]:
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def load_municipality_reference(reference_path: Path) -> dict[str, dict[str, str]]:
    if not reference_path.exists():
        raise FileNotFoundError(f"Municipality reference CSV not found: {reference_path}")

    with reference_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Municipality reference CSV has no header: {reference_path}")
        required_columns = {"obcina_sifra", "obcina_naziv"}
        missing_columns = sorted(required_columns.difference(reader.fieldnames))
        if missing_columns:
            raise ValueError(
                f"Municipality reference CSV is missing required columns: {', '.join(missing_columns)}"
            )

        mapping: dict[str, dict[str, str]] = {}
        for row in reader:
            code = str(row["obcina_sifra"]).strip()
            name = str(row["obcina_naziv"]).strip()
            if not code or not name:
                continue
            normalized_name = normalize_name_for_match(name)
            current = mapping.get(normalized_name)
            if current and current["obcina_sifra"] != code:
                raise ValueError(
                    "Municipality reference contains conflicting codes for "
                    f"{name}: {current['obcina_sifra']} vs {code}"
                )
            mapping[normalized_name] = {"obcina_sifra": code, "obcina_naziv": name}

    if not mapping:
        raise ValueError(f"Municipality reference CSV has no municipality rows: {reference_path}")

    return mapping


def build_obcina_weekly_epidemiology(
    *,
    lyme_input: Path = DEFAULT_LYME_INPUT,
    kme_input: Path = DEFAULT_KME_INPUT,
    municipality_reference: Path = DEFAULT_MUNICIPALITY_REFERENCE,
) -> EpidemiologyTables:
    reference_mapping = load_municipality_reference(municipality_reference)
    combined_records: dict[tuple[str, str], dict[str, Any]] = {}
    disease_summaries: dict[str, dict[str, Any]] = {}
    applied_aliases: dict[str, str] = {}

    for disease_column, workbook_path in (
        ("lyme_cases", lyme_input),
        ("kme_cases", kme_input),
    ):
        disease_summary = _ingest_workbook(
            workbook_path=workbook_path,
            disease_column=disease_column,
            reference_mapping=reference_mapping,
            combined_records=combined_records,
            applied_aliases=applied_aliases,
        )
        disease_summaries[disease_column] = disease_summary

    rows = list(combined_records.values())
    for row in rows:
        for disease_column in DISEASE_COLUMNS:
            row.setdefault(disease_column, 0)
        row["tick_borne_cases_total"] = int(row["lyme_cases"]) + int(row["kme_cases"])

    rows.sort(key=_record_sort_key)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "lyme_input": str(lyme_input.resolve()),
        "kme_input": str(kme_input.resolve()),
        "municipality_reference": str(municipality_reference.resolve()),
        "row_count": len(rows),
        "municipality_count": len({row["obcina_sifra"] for row in rows}),
        "week_count": len({row["week_start"] for row in rows}),
        "week_start_min": rows[0]["week_start"] if rows else None,
        "week_start_max": rows[-1]["week_start"] if rows else None,
        "lyme_case_total": int(sum(int(row["lyme_cases"]) for row in rows)),
        "kme_case_total": int(sum(int(row["kme_cases"]) for row in rows)),
        "tick_borne_case_total": int(sum(int(row["tick_borne_cases_total"]) for row in rows)),
        "name_aliases_applied": [
            {"raw_name": raw_name, "matched_name": matched_name}
            for raw_name, matched_name in sorted(applied_aliases.items())
        ],
        "validation_notes": [
            "Municipality row totals are enforced.",
            "Workbook SKUPAJ aggregates are recorded as diagnostics when they disagree with municipality rows.",
        ],
        "disease_summaries": disease_summaries,
        "columns": OUTPUT_FIELDNAMES,
    }
    return EpidemiologyTables(rows=rows, manifest=manifest)


def write_obcina_weekly_epidemiology(
    tables: EpidemiologyTables,
    *,
    output_path: Path = DEFAULT_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        for row in tables.rows:
            writer.writerow({column: row[column] for column in OUTPUT_FIELDNAMES})

    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")


def verify_obcina_weekly_epidemiology(
    *,
    csv_path: Path = DEFAULT_OUTPUT,
    lyme_input: Path = DEFAULT_LYME_INPUT,
    kme_input: Path = DEFAULT_KME_INPUT,
    municipality_reference: Path = DEFAULT_MUNICIPALITY_REFERENCE,
) -> EpidemiologyVerificationResult:
    reference_mapping = load_municipality_reference(municipality_reference)
    csv_rows, csv_row_issues = _load_csv_records_for_verification(csv_path)

    expected_pairs: set[tuple[str, str]] = set()
    value_mismatches: list[dict[str, Any]] = []
    missing_csv_keys: list[dict[str, Any]] = []
    municipality_row_total_mismatches: list[dict[str, Any]] = []
    aggregated_total_mismatches: dict[str, list[dict[str, Any]]] = {}

    for disease_column, workbook_path in (
        ("lyme_cases", lyme_input),
        ("kme_cases", kme_input),
    ):
        (
            disease_expected_pairs,
            disease_value_mismatches,
            disease_missing_csv_keys,
            disease_row_total_mismatches,
            disease_aggregate_mismatches,
        ) = _verify_workbook_against_csv(
            workbook_path=workbook_path,
            disease_column=disease_column,
            reference_mapping=reference_mapping,
            csv_rows=csv_rows,
        )
        expected_pairs.update(disease_expected_pairs)
        value_mismatches.extend(disease_value_mismatches)
        missing_csv_keys.extend(disease_missing_csv_keys)
        municipality_row_total_mismatches.extend(disease_row_total_mismatches)
        aggregated_total_mismatches[disease_column] = disease_aggregate_mismatches

    unexpected_csv_keys = [
        {"week_start": week_start, "obcina_sifra": obcina_sifra}
        for week_start, obcina_sifra in sorted(set(csv_rows).difference(expected_pairs))
    ]

    report = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "csv_path": str(csv_path.resolve()),
        "lyme_input": str(lyme_input.resolve()),
        "kme_input": str(kme_input.resolve()),
        "municipality_reference": str(municipality_reference.resolve()),
        "csv_row_count": len(csv_rows),
        "expected_pair_count": len(expected_pairs),
        "csv_row_issues": csv_row_issues,
        "value_mismatches": value_mismatches,
        "missing_csv_keys": missing_csv_keys,
        "unexpected_csv_keys": unexpected_csv_keys,
        "municipality_row_total_mismatches": municipality_row_total_mismatches,
        "aggregated_total_mismatches": aggregated_total_mismatches,
    }
    return EpidemiologyVerificationResult(report=report)


def _ingest_workbook(
    *,
    workbook_path: Path,
    disease_column: str,
    reference_mapping: dict[str, dict[str, str]],
    combined_records: dict[tuple[str, str], dict[str, Any]],
    applied_aliases: dict[str, str],
) -> dict[str, Any]:
    if not workbook_path.exists():
        raise FileNotFoundError(f"NIJZ workbook not found: {workbook_path}")

    sheet_count = 0
    municipality_names: set[str] = set()
    case_total = 0
    yearly_grand_totals: dict[str, int] = {}
    aggregated_total_mismatches: list[dict[str, Any]] = []

    for sheet_name, rows in iter_xlsx_rows(workbook_path):
        sheet_count += 1
        week_columns, total_column = _parse_header_row(rows[0], sheet_name=sheet_name)
        total_row: dict[int, str] | None = None
        municipality_count = 0
        computed_week_totals = {column: 0 for column, _, _ in week_columns}
        computed_sheet_total = 0

        for row in rows[1:]:
            raw_name = str(row.get(2, "")).strip()
            if not raw_name:
                continue

            if normalize_name_for_match(raw_name) == TOTAL_LABEL:
                total_row = row
                continue

            municipality_key = resolve_nijz_municipality_name(raw_name)
            municipality = reference_mapping.get(municipality_key)
            if municipality is None:
                raise ValueError(
                    f"Municipality '{raw_name}' from {workbook_path.name} sheet {sheet_name} "
                    "could not be matched to the municipality reference."
                )
            if municipality_key != normalize_name_for_match(raw_name):
                applied_aliases[raw_name] = municipality["obcina_naziv"]

            municipality_count += 1
            municipality_names.add(municipality["obcina_sifra"])

            row_sum = 0
            for column_index, iso_year, iso_week in week_columns:
                case_count = _parse_case_count(
                    row.get(column_index, ""),
                    workbook_name=workbook_path.name,
                    sheet_name=sheet_name,
                    municipality_name=raw_name,
                    week_label=f"{iso_year:04d}-{iso_week:02d}",
                )
                row_sum += case_count
                computed_week_totals[column_index] += case_count

                week_start, week_end = iso_week_bounds(iso_year, iso_week)
                record_key = (week_start.isoformat(), municipality["obcina_sifra"])
                record = combined_records.setdefault(
                    record_key,
                    {
                        "week_start": week_start.isoformat(),
                        "week_end": week_end.isoformat(),
                        "iso_year": iso_year,
                        "iso_week": iso_week,
                        "obcina_sifra": municipality["obcina_sifra"],
                        "obcina_naziv": municipality["obcina_naziv"],
                    },
                )
                if record["obcina_naziv"] != municipality["obcina_naziv"]:
                    raise ValueError(
                        "Municipality name mismatch while combining epidemiology rows for code "
                        f"{municipality['obcina_sifra']}: '{record['obcina_naziv']}' vs "
                        f"'{municipality['obcina_naziv']}'"
                    )
                if disease_column in record:
                    raise ValueError(
                        f"Duplicate epidemiology row for {disease_column} at "
                        f"{record['week_start']} / {record['obcina_sifra']}"
                    )
                record[disease_column] = case_count

            expected_row_total = _parse_case_count(
                row.get(total_column, ""),
                workbook_name=workbook_path.name,
                sheet_name=sheet_name,
                municipality_name=raw_name,
                week_label=TOTAL_LABEL,
            )
            if row_sum != expected_row_total:
                raise ValueError(
                    f"Row total mismatch in {workbook_path.name} sheet {sheet_name} for "
                    f"municipality '{raw_name}': computed {row_sum}, workbook {expected_row_total}"
                )
            computed_sheet_total += row_sum

        if total_row is None:
            raise ValueError(f"Sheet {sheet_name} in {workbook_path.name} is missing the total row.")

        for column_index, iso_year, iso_week in week_columns:
            expected_week_total = _parse_case_count(
                total_row.get(column_index, ""),
                workbook_name=workbook_path.name,
                sheet_name=sheet_name,
                municipality_name=TOTAL_LABEL,
                week_label=f"{iso_year:04d}-{iso_week:02d}",
            )
            actual_week_total = computed_week_totals[column_index]
            if actual_week_total != expected_week_total:
                aggregated_total_mismatches.append(
                    {
                        "sheet_name": sheet_name,
                        "scope": "week",
                        "week_label": f"{iso_year:04d}-{iso_week:02d}",
                        "computed_total": actual_week_total,
                        "workbook_total": expected_week_total,
                    }
                )

        expected_sheet_total = _parse_case_count(
            total_row.get(total_column, ""),
            workbook_name=workbook_path.name,
            sheet_name=sheet_name,
            municipality_name=TOTAL_LABEL,
            week_label=TOTAL_LABEL,
        )
        if computed_sheet_total != expected_sheet_total:
            aggregated_total_mismatches.append(
                {
                    "sheet_name": sheet_name,
                    "scope": "sheet",
                    "computed_total": computed_sheet_total,
                    "workbook_total": expected_sheet_total,
                }
            )

        case_total += computed_sheet_total
        yearly_grand_totals[sheet_name] = expected_sheet_total

        if municipality_count != len(reference_mapping):
            raise ValueError(
                f"Unexpected municipality count in {workbook_path.name} sheet {sheet_name}: "
                f"found {municipality_count}, expected {len(reference_mapping)}"
            )

    return {
        "input_path": str(workbook_path.resolve()),
        "sheet_count": sheet_count,
        "municipality_count": len(municipality_names),
        "case_total": case_total,
        "yearly_grand_totals": yearly_grand_totals,
        "aggregated_total_mismatches": aggregated_total_mismatches,
    }


def _load_csv_records_for_verification(
    csv_path: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Epidemiology CSV not found: {csv_path}")

    csv_rows: dict[tuple[str, str], dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Epidemiology CSV has no header: {csv_path}")

        missing_columns = [column for column in OUTPUT_FIELDNAMES if column not in reader.fieldnames]
        if missing_columns:
            raise ValueError(
                f"Epidemiology CSV is missing required columns: {', '.join(missing_columns)}"
            )

        for row_number, row in enumerate(reader, start=2):
            week_start = str(row["week_start"]).strip()
            week_end = str(row["week_end"]).strip()
            obcina_sifra = str(row["obcina_sifra"]).strip()
            obcina_naziv = str(row["obcina_naziv"]).strip()
            key = (week_start, obcina_sifra)

            if key in csv_rows:
                issues.append(
                    {
                        "type": "duplicate_csv_key",
                        "row_number": row_number,
                        "week_start": week_start,
                        "obcina_sifra": obcina_sifra,
                    }
                )
                continue

            try:
                iso_year = int(str(row["iso_year"]).strip())
                iso_week = int(str(row["iso_week"]).strip())
                lyme_cases = int(str(row["lyme_cases"]).strip())
                kme_cases = int(str(row["kme_cases"]).strip())
                tick_borne_total = int(str(row["tick_borne_cases_total"]).strip())
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value in CSV row {row_number}.") from exc

            expected_week_start, expected_week_end = iso_week_bounds(iso_year, iso_week)
            if week_start != expected_week_start.isoformat() or week_end != expected_week_end.isoformat():
                issues.append(
                    {
                        "type": "week_bounds_mismatch",
                        "row_number": row_number,
                        "week_start": week_start,
                        "week_end": week_end,
                        "expected_week_start": expected_week_start.isoformat(),
                        "expected_week_end": expected_week_end.isoformat(),
                    }
                )

            if tick_borne_total != lyme_cases + kme_cases:
                issues.append(
                    {
                        "type": "tick_borne_total_mismatch",
                        "row_number": row_number,
                        "week_start": week_start,
                        "obcina_sifra": obcina_sifra,
                        "tick_borne_cases_total": tick_borne_total,
                        "expected_total": lyme_cases + kme_cases,
                    }
                )

            csv_rows[key] = {
                "week_start": week_start,
                "week_end": week_end,
                "iso_year": iso_year,
                "iso_week": iso_week,
                "obcina_sifra": obcina_sifra,
                "obcina_naziv": obcina_naziv,
                "lyme_cases": lyme_cases,
                "kme_cases": kme_cases,
                "tick_borne_cases_total": tick_borne_total,
            }

    return csv_rows, issues


def _verify_workbook_against_csv(
    *,
    workbook_path: Path,
    disease_column: str,
    reference_mapping: dict[str, dict[str, str]],
    csv_rows: dict[tuple[str, str], dict[str, Any]],
) -> tuple[
    set[tuple[str, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    expected_pairs: set[tuple[str, str]] = set()
    value_mismatches: list[dict[str, Any]] = []
    missing_csv_keys: list[dict[str, Any]] = []
    municipality_row_total_mismatches: list[dict[str, Any]] = []
    aggregated_total_mismatches: list[dict[str, Any]] = []

    for sheet_name, rows in iter_xlsx_rows(workbook_path):
        week_columns, total_column = _parse_header_row(rows[0], sheet_name=sheet_name)
        total_row: dict[int, str] | None = None
        computed_week_totals = {column: 0 for column, _, _ in week_columns}
        computed_sheet_total = 0

        for row in rows[1:]:
            raw_name = str(row.get(2, "")).strip()
            if not raw_name:
                continue
            if normalize_name_for_match(raw_name) == TOTAL_LABEL:
                total_row = row
                continue

            municipality_key = resolve_nijz_municipality_name(raw_name)
            municipality = reference_mapping.get(municipality_key)
            if municipality is None:
                raise ValueError(
                    f"Municipality '{raw_name}' from {workbook_path.name} sheet {sheet_name} "
                    "could not be matched to the municipality reference."
                )

            expected_name = municipality["obcina_naziv"]
            expected_code = municipality["obcina_sifra"]
            row_sum = 0

            for column_index, iso_year, iso_week in week_columns:
                case_count = _parse_case_count(
                    row.get(column_index, ""),
                    workbook_name=workbook_path.name,
                    sheet_name=sheet_name,
                    municipality_name=raw_name,
                    week_label=f"{iso_year:04d}-{iso_week:02d}",
                )
                row_sum += case_count
                computed_week_totals[column_index] += case_count

                week_start, week_end = iso_week_bounds(iso_year, iso_week)
                key = (week_start.isoformat(), expected_code)
                expected_pairs.add(key)
                csv_row = csv_rows.get(key)
                if csv_row is None:
                    missing_csv_keys.append(
                        {
                            "disease_column": disease_column,
                            "workbook": workbook_path.name,
                            "sheet_name": sheet_name,
                            "week_start": week_start.isoformat(),
                            "obcina_sifra": expected_code,
                            "obcina_naziv": expected_name,
                        }
                    )
                    continue

                if csv_row["week_end"] != week_end.isoformat():
                    value_mismatches.append(
                        {
                            "type": "week_end_mismatch",
                            "disease_column": disease_column,
                            "week_start": week_start.isoformat(),
                            "obcina_sifra": expected_code,
                            "csv_value": csv_row["week_end"],
                            "expected_value": week_end.isoformat(),
                        }
                    )
                if csv_row["iso_year"] != iso_year or csv_row["iso_week"] != iso_week:
                    value_mismatches.append(
                        {
                            "type": "iso_week_mismatch",
                            "disease_column": disease_column,
                            "week_start": week_start.isoformat(),
                            "obcina_sifra": expected_code,
                            "csv_iso_year": csv_row["iso_year"],
                            "csv_iso_week": csv_row["iso_week"],
                            "expected_iso_year": iso_year,
                            "expected_iso_week": iso_week,
                        }
                    )
                if csv_row["obcina_naziv"] != expected_name:
                    value_mismatches.append(
                        {
                            "type": "municipality_name_mismatch",
                            "disease_column": disease_column,
                            "week_start": week_start.isoformat(),
                            "obcina_sifra": expected_code,
                            "csv_value": csv_row["obcina_naziv"],
                            "expected_value": expected_name,
                        }
                    )
                if csv_row[disease_column] != case_count:
                    value_mismatches.append(
                        {
                            "type": "case_count_mismatch",
                            "disease_column": disease_column,
                            "week_start": week_start.isoformat(),
                            "obcina_sifra": expected_code,
                            "obcina_naziv": expected_name,
                            "csv_value": csv_row[disease_column],
                            "expected_value": case_count,
                        }
                    )

            expected_row_total = _parse_case_count(
                row.get(total_column, ""),
                workbook_name=workbook_path.name,
                sheet_name=sheet_name,
                municipality_name=raw_name,
                week_label=TOTAL_LABEL,
            )
            if row_sum != expected_row_total:
                municipality_row_total_mismatches.append(
                    {
                        "disease_column": disease_column,
                        "workbook": workbook_path.name,
                        "sheet_name": sheet_name,
                        "municipality_name": raw_name,
                        "computed_total": row_sum,
                        "workbook_total": expected_row_total,
                    }
                )
            computed_sheet_total += row_sum

        if total_row is None:
            raise ValueError(f"Sheet {sheet_name} in {workbook_path.name} is missing the total row.")

        for column_index, iso_year, iso_week in week_columns:
            workbook_total = _parse_case_count(
                total_row.get(column_index, ""),
                workbook_name=workbook_path.name,
                sheet_name=sheet_name,
                municipality_name=TOTAL_LABEL,
                week_label=f"{iso_year:04d}-{iso_week:02d}",
            )
            computed_total = computed_week_totals[column_index]
            if computed_total != workbook_total:
                aggregated_total_mismatches.append(
                    {
                        "sheet_name": sheet_name,
                        "scope": "week",
                        "week_label": f"{iso_year:04d}-{iso_week:02d}",
                        "computed_total": computed_total,
                        "workbook_total": workbook_total,
                    }
                )

        workbook_sheet_total = _parse_case_count(
            total_row.get(total_column, ""),
            workbook_name=workbook_path.name,
            sheet_name=sheet_name,
            municipality_name=TOTAL_LABEL,
            week_label=TOTAL_LABEL,
        )
        if computed_sheet_total != workbook_sheet_total:
            aggregated_total_mismatches.append(
                {
                    "sheet_name": sheet_name,
                    "scope": "sheet",
                    "computed_total": computed_sheet_total,
                    "workbook_total": workbook_sheet_total,
                }
            )

    return (
        expected_pairs,
        value_mismatches,
        missing_csv_keys,
        municipality_row_total_mismatches,
        aggregated_total_mismatches,
    )


def iter_xlsx_rows(workbook_path: Path) -> list[tuple[str, list[dict[int, str]]]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = _load_shared_strings(archive)
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in rels_root.findall("pkgrel:Relationship", WORKBOOK_NAMESPACE)
        }

        sheets: list[tuple[str, list[dict[int, str]]]] = []
        for sheet in workbook_root.findall("main:sheets/main:sheet", WORKBOOK_NAMESPACE):
            sheet_name = sheet.attrib["name"]
            relation_id = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            target = relation_targets[relation_id]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            sheet_root = ET.fromstring(archive.read(target))
            sheet_rows = []
            for row in sheet_root.findall(".//main:sheetData/main:row", WORKBOOK_NAMESPACE):
                parsed_row: dict[int, str] = {}
                for cell in row.findall("main:c", WORKBOOK_NAMESPACE):
                    reference = cell.attrib.get("r", "")
                    match = CELL_REFERENCE_PATTERN.match(reference)
                    if not match:
                        continue
                    parsed_row[_column_letters_to_index(match.group(1))] = _read_xlsx_cell(
                        cell,
                        shared_strings,
                    )
                sheet_rows.append(parsed_row)
            if not sheet_rows:
                raise ValueError(f"Sheet {sheet_name} in {workbook_path.name} has no rows.")
            sheets.append((sheet_name, sheet_rows))
        return sheets


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    shared_strings_path = "xl/sharedStrings.xml"
    if shared_strings_path not in archive.namelist():
        return []

    root = ET.fromstring(archive.read(shared_strings_path))
    shared_strings: list[str] = []
    for item in root.findall("main:si", WORKBOOK_NAMESPACE):
        shared_strings.append("".join(node.text or "" for node in item.iterfind(".//main:t", WORKBOOK_NAMESPACE)))
    return shared_strings


def _read_xlsx_cell(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("main:v", WORKBOOK_NAMESPACE)
    inline_string = cell.find("main:is", WORKBOOK_NAMESPACE)

    if cell_type == "s" and value_node is not None:
        return shared_strings[int(value_node.text or "0")]
    if cell_type == "inlineStr" and inline_string is not None:
        return "".join(
            node.text or "" for node in inline_string.iterfind(".//main:t", WORKBOOK_NAMESPACE)
        )
    if value_node is not None:
        return value_node.text or ""
    return ""


def _column_letters_to_index(column_letters: str) -> int:
    index = 0
    for character in column_letters:
        index = (index * 26) + (ord(character) - ord("A") + 1)
    return index


def _parse_header_row(
    header_row: dict[int, str],
    *,
    sheet_name: str,
) -> tuple[list[tuple[int, int, int]], int]:
    week_columns: list[tuple[int, int, int]] = []
    total_column: int | None = None

    for column_index, raw_value in sorted(header_row.items()):
        label = str(raw_value).strip()
        if not label:
            continue
        week_match = WEEK_LABEL_PATTERN.match(label)
        if week_match:
            iso_year = int(week_match.group("iso_year"))
            iso_week = int(week_match.group("iso_week"))
            if str(iso_year) != str(sheet_name):
                raise ValueError(
                    f"Header year {iso_year} does not match sheet name {sheet_name}."
                )
            week_columns.append((column_index, iso_year, iso_week))
            continue
        if normalize_name_for_match(label) == TOTAL_LABEL:
            total_column = column_index

    if not week_columns:
        raise ValueError(f"Sheet {sheet_name} does not contain any week columns.")
    if total_column is None:
        raise ValueError(f"Sheet {sheet_name} is missing the total column.")

    return week_columns, total_column


def _parse_case_count(
    value: str,
    *,
    workbook_name: str,
    sheet_name: str,
    municipality_name: str,
    week_label: str,
) -> int:
    cleaned = str(value).strip()
    if not cleaned:
        return 0
    try:
        numeric_value = float(cleaned)
    except ValueError as exc:
        raise ValueError(
            f"Invalid case count '{value}' in {workbook_name} sheet {sheet_name} for "
            f"municipality '{municipality_name}', column {week_label}."
        ) from exc
    if not numeric_value.is_integer():
        raise ValueError(
            f"Case count must be an integer in {workbook_name} sheet {sheet_name} for "
            f"municipality '{municipality_name}', column {week_label}: got '{value}'."
        )
    return int(numeric_value)


def _record_sort_key(row: dict[str, Any]) -> tuple[str, int | str]:
    code = str(row["obcina_sifra"])
    return row["week_start"], int(code) if code.isdigit() else code
