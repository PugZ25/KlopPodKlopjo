#!/usr/bin/env python3
"""Normalize Slovenia local datasets into merge-friendly CSV staging tables."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
LOCAL_DIR = RAW_DIR / "Slovenia_local_data"
NIJZ_PATH = RAW_DIR / "NIJZ" / "obcina_weekly_epidemiology_KME_Boreliosis.csv"
OUTPUT_DIR = INTERIM_DIR / "Slovenia_local_data_normalized"


ARSO_PARAMETER_MAP = {
    "koli\u010dina padavin": {
        "parameter_key": "arso_precipitation_sum_mm",
        "parameter_label_en": "Monthly precipitation sum",
    },
    "povp. rel. vla.": {
        "parameter_key": "arso_relative_humidity_mean_pct",
        "parameter_label_en": "Monthly mean relative humidity",
    },
    "povp. T": {
        "parameter_key": "arso_air_temperature_mean_c",
        "parameter_label_en": "Monthly mean air temperature",
    },
}


GOZDIS_DATA_TYPE_MAP = {
    "koli\u010dina padavin (sum)": {
        "metrics": [
            ("weekly_mean_sum", "gozdis_precipitation_sum_mm"),
        ],
        "label_en": "Weekly precipitation sum",
    },
    "relativna zra\u010dna vlaga (mean, min, max)": {
        "metrics": [
            ("weekly_mean_sum", "gozdis_relative_humidity_mean_pct"),
            ("weekly_min", "gozdis_relative_humidity_min_pct"),
            ("weekly_max", "gozdis_relative_humidity_max_pct"),
        ],
        "label_en": "Weekly relative humidity",
    },
    "temperatura zraka (mean, min, max)": {
        "metrics": [
            ("weekly_mean_sum", "gozdis_air_temperature_mean_c"),
            ("weekly_min", "gozdis_air_temperature_min_c"),
            ("weekly_max", "gozdis_air_temperature_max_c"),
        ],
        "label_en": "Weekly air temperature",
    },
}


OBROD_YEAR_COLUMNS = [f"obrod_{year}" for year in range(2012, 2024)]


@dataclass(frozen=True)
class WeekRecord:
    week_start: str
    week_end: str
    iso_year: int
    iso_week: int
    week_mid_date: str
    week_mid_month_key: str
    week_mid_calendar_year: int


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def parse_int(value: str | None) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(round(number))


def canonical_name_map() -> tuple[dict[str, str], list[WeekRecord]]:
    municipality_names: dict[str, Counter[str]] = defaultdict(Counter)
    seen_weeks: dict[str, WeekRecord] = {}

    with NIJZ_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            obcina_sifra = (row.get("obcina_sifra") or "").strip()
            obcina_naziv = (row.get("obcina_naziv") or "").strip()
            if obcina_sifra and obcina_naziv:
                municipality_names[obcina_sifra][obcina_naziv] += 1

            week_start = (row.get("week_start") or "").strip()
            week_end = (row.get("week_end") or "").strip()
            iso_year = parse_int(row.get("iso_year"))
            iso_week = parse_int(row.get("iso_week"))
            if not week_start or not week_end or iso_year is None or iso_week is None:
                continue

            if week_start not in seen_weeks:
                start_dt = date.fromisoformat(week_start)
                mid_dt = start_dt + timedelta(days=3)
                seen_weeks[week_start] = WeekRecord(
                    week_start=week_start,
                    week_end=week_end,
                    iso_year=iso_year,
                    iso_week=iso_week,
                    week_mid_date=mid_dt.isoformat(),
                    week_mid_month_key=mid_dt.strftime("%Y-%m"),
                    week_mid_calendar_year=mid_dt.year,
                )

    canonical_names = {
        obcina_sifra: counter.most_common(1)[0][0]
        for obcina_sifra, counter in municipality_names.items()
    }
    week_records = [seen_weeks[key] for key in sorted(seen_weeks)]
    return canonical_names, week_records


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
            count += 1
    return count


def weighted_average(values: list[tuple[float, float]]) -> float | None:
    usable = [(value, weight) for value, weight in values if value is not None]
    if not usable:
        return None
    weight_sum = sum(weight for _, weight in usable)
    if weight_sum <= 0:
        return mean(value for value, _ in usable)
    return sum(value * weight for value, weight in usable) / weight_sum


def preferred_name(raw_names: list[str], canonical_name: str | None) -> str:
    if canonical_name:
        return canonical_name
    counter = Counter(name for name in raw_names if name)
    if counter:
        return counter.most_common(1)[0][0]
    return ""


def normalize_species_key(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "unknown"
    return re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_") or "unknown"


def arso_outputs(canonical_names: dict[str, str], week_records: list[WeekRecord]) -> dict[str, dict[str, int]]:
    input_path = LOCAL_DIR / "Arso-final export_data_station_municipality_municipality.csv"
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            obcina_sifra = (row.get("municipality_id") or "").strip()
            month_key = (row.get("time_month") or "").strip()
            parameter_name = (row.get("parameter_short_name") or "").strip()
            if not obcina_sifra or not month_key or not parameter_name:
                continue

            parameter_meta = ARSO_PARAMETER_MAP.get(parameter_name)
            parameter_key = (
                parameter_meta["parameter_key"]
                if parameter_meta
                else f"arso_unmapped_{re.sub(r'[^0-9A-Za-z]+', '_', parameter_name).strip('_').lower()}"
            )
            group_key = (obcina_sifra, month_key, parameter_key)
            record = grouped.setdefault(
                group_key,
                {
                    "obcina_sifra": obcina_sifra,
                    "obcina_naziv": canonical_names.get(obcina_sifra, ""),
                    "source_municipality_names": [],
                    "month_key": month_key,
                    "month_start": ((row.get("time_date") or "").strip() or f"{month_key}-01"),
                    "calendar_year": month_key.split("-")[0],
                    "calendar_month": month_key.split("-")[1] if "-" in month_key else "",
                    "parameter_key": parameter_key,
                    "parameter_short_name": parameter_name,
                    "parameter_label": (row.get("parameter_label") or "").strip(),
                    "parameter_label_en": parameter_meta["parameter_label_en"] if parameter_meta else "",
                    "unit": (row.get("unit") or "").strip(),
                    "weighted_values": [],
                    "row_count": 0,
                    "station_count_sum": 0,
                    "station_type_values": set(),
                    "file_secondary_id_values": set(),
                },
            )

            value = parse_float(row.get("value"))
            station_count = parse_float(row.get("Station_count")) or 1.0
            if value is not None:
                record["weighted_values"].append((value, station_count))
            record["row_count"] += 1
            record["station_count_sum"] += int(round(station_count))
            station_type = (row.get("station_type") or "").strip()
            if station_type:
                record["station_type_values"].add(station_type)
            file_secondary_id = (row.get("file_secondary_id") or "").strip()
            if file_secondary_id:
                record["file_secondary_id_values"].add(file_secondary_id)
            source_name = (row.get("municipality_name") or "").strip()
            if source_name:
                record["source_municipality_names"].append(source_name)

    long_rows = []
    wide_rows_map: dict[tuple[str, str], dict[str, object]] = {}
    for key in sorted(grouped, key=lambda item: (int(item[0]), item[1], item[2])):
        record = grouped[key]
        canonical_name = canonical_names.get(record["obcina_sifra"], "")
        source_names = record.pop("source_municipality_names")
        weighted_values = record.pop("weighted_values")
        station_type_values = record.pop("station_type_values")
        file_secondary_ids = record.pop("file_secondary_id_values")
        value = weighted_average(weighted_values)

        long_row = {
            **record,
            "obcina_naziv": preferred_name(source_names, canonical_name),
            "source_municipality_name": Counter(source_names).most_common(1)[0][0] if source_names else "",
            "value": "" if value is None else round(value, 6),
            "component_row_count": record["row_count"],
            "station_count_weight_sum": record["station_count_sum"],
            "station_type_values": "|".join(sorted(station_type_values)),
            "file_secondary_id_values": "|".join(sorted(file_secondary_ids)),
        }
        long_rows.append(long_row)

        wide_key = (long_row["obcina_sifra"], long_row["month_key"])
        wide_row = wide_rows_map.setdefault(
            wide_key,
            {
                "month_start": long_row["month_start"],
                "month_key": long_row["month_key"],
                "calendar_year": long_row["calendar_year"],
                "calendar_month": long_row["calendar_month"],
                "obcina_sifra": long_row["obcina_sifra"],
                "obcina_naziv": long_row["obcina_naziv"],
                "arso_air_temperature_mean_c": "",
                "arso_relative_humidity_mean_pct": "",
                "arso_precipitation_sum_mm": "",
            },
        )
        wide_row[long_row["parameter_key"]] = long_row["value"]

    long_fieldnames = [
        "month_start",
        "month_key",
        "calendar_year",
        "calendar_month",
        "obcina_sifra",
        "obcina_naziv",
        "source_municipality_name",
        "parameter_key",
        "parameter_short_name",
        "parameter_label",
        "parameter_label_en",
        "unit",
        "value",
        "component_row_count",
        "station_count_weight_sum",
        "station_type_values",
        "file_secondary_id_values",
    ]
    wide_fieldnames = [
        "month_start",
        "month_key",
        "calendar_year",
        "calendar_month",
        "obcina_sifra",
        "obcina_naziv",
        "arso_air_temperature_mean_c",
        "arso_relative_humidity_mean_pct",
        "arso_precipitation_sum_mm",
    ]

    long_path = OUTPUT_DIR / "arso_monthly_weather_long_normalized.csv"
    wide_path = OUTPUT_DIR / "arso_monthly_weather_wide.csv"
    long_count = write_csv(long_path, long_fieldnames, long_rows)
    wide_rows = [wide_rows_map[key] for key in sorted(wide_rows_map, key=lambda item: (int(item[0]), item[1]))]
    wide_count = write_csv(wide_path, wide_fieldnames, wide_rows)

    wide_lookup = {(row["obcina_sifra"], row["month_key"]): row for row in wide_rows}
    weekly_rows = []
    for week in week_records:
        month_key = week.week_mid_month_key
        for obcina_sifra, _ in sorted(
            [item for item in wide_lookup if item[1] == month_key],
            key=lambda item: int(item[0]),
        ):
            source_row = wide_lookup[(obcina_sifra, month_key)]
            weekly_rows.append(
                {
                    "week_start": week.week_start,
                    "week_end": week.week_end,
                    "iso_year": week.iso_year,
                    "iso_week": week.iso_week,
                    "week_mid_date": week.week_mid_date,
                    "source_month_key": month_key,
                    "obcina_sifra": source_row["obcina_sifra"],
                    "obcina_naziv": source_row["obcina_naziv"],
                    "arso_air_temperature_mean_c": source_row["arso_air_temperature_mean_c"],
                    "arso_relative_humidity_mean_pct": source_row["arso_relative_humidity_mean_pct"],
                    "arso_precipitation_sum_mm": source_row["arso_precipitation_sum_mm"],
                }
            )

    weekly_fieldnames = [
        "week_start",
        "week_end",
        "iso_year",
        "iso_week",
        "week_mid_date",
        "source_month_key",
        "obcina_sifra",
        "obcina_naziv",
        "arso_air_temperature_mean_c",
        "arso_relative_humidity_mean_pct",
        "arso_precipitation_sum_mm",
    ]
    weekly_path = OUTPUT_DIR / "arso_weekly_weather_from_monthly.csv"
    weekly_count = write_csv(weekly_path, weekly_fieldnames, weekly_rows)

    return {
        long_path.name: {"rows": long_count, "columns": len(long_fieldnames)},
        wide_path.name: {"rows": wide_count, "columns": len(wide_fieldnames)},
        weekly_path.name: {"rows": weekly_count, "columns": len(weekly_fieldnames)},
    }


def week_dates_from_iso(year_value: int, week_value: int) -> tuple[str, str] | None:
    try:
        start_dt = date.fromisocalendar(year_value, week_value, 1)
    except ValueError:
        return None
    end_dt = start_dt + timedelta(days=6)
    return start_dt.isoformat(), end_dt.isoformat()


def gozdis_outputs(canonical_names: dict[str, str]) -> dict[str, dict[str, int]]:
    input_path = LOCAL_DIR / "GOZDIS-vremenski-podatki-urejeni-z-obcinami-final_municipality.csv"
    grouped: dict[tuple[str, int, int], dict[str, object]] = {}

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            obcina_sifra = (row.get("municipality_id") or "").strip()
            iso_year = parse_int(row.get("time_iso_year"))
            iso_week = parse_int(row.get("time_iso_week"))
            data_type = (row.get("data_type") or "").strip()
            if not obcina_sifra or iso_year is None or iso_week is None or not data_type:
                continue

            week_dates = week_dates_from_iso(iso_year, iso_week)
            if week_dates is None:
                continue
            week_start, week_end = week_dates
            meta = GOZDIS_DATA_TYPE_MAP.get(data_type)
            if meta is None:
                continue

            key = (obcina_sifra, iso_year, iso_week)
            record = grouped.setdefault(
                key,
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "iso_year": iso_year,
                    "iso_week": iso_week,
                    "obcina_sifra": obcina_sifra,
                    "obcina_naziv": canonical_names.get(obcina_sifra, (row.get("municipality_name") or "").strip()),
                    "source_municipality_name": (row.get("municipality_name") or "").strip(),
                    "gozdis_precipitation_sum_mm": "",
                    "gozdis_relative_humidity_mean_pct": "",
                    "gozdis_relative_humidity_min_pct": "",
                    "gozdis_relative_humidity_max_pct": "",
                    "gozdis_air_temperature_mean_c": "",
                    "gozdis_air_temperature_min_c": "",
                    "gozdis_air_temperature_max_c": "",
                },
            )

            for source_column, output_column in meta["metrics"]:
                value = parse_float(row.get(source_column))
                record[output_column] = "" if value is None else round(value, 6)

    fieldnames = [
        "week_start",
        "week_end",
        "iso_year",
        "iso_week",
        "obcina_sifra",
        "obcina_naziv",
        "source_municipality_name",
        "gozdis_precipitation_sum_mm",
        "gozdis_relative_humidity_mean_pct",
        "gozdis_relative_humidity_min_pct",
        "gozdis_relative_humidity_max_pct",
        "gozdis_air_temperature_mean_c",
        "gozdis_air_temperature_min_c",
        "gozdis_air_temperature_max_c",
    ]
    rows = [grouped[key] for key in sorted(grouped, key=lambda item: (int(item[0]), item[1], item[2]))]
    output_path = OUTPUT_DIR / "gozdis_weekly_weather_wide.csv"
    row_count = write_csv(output_path, fieldnames, rows)

    return {
        output_path.name: {"rows": row_count, "columns": len(fieldnames)},
    }


def obrod_outputs(canonical_names: dict[str, str], week_records: list[WeekRecord]) -> dict[str, dict[str, int]]:
    input_path = LOCAL_DIR / "OBROD-urejeni podatki_municipality.csv"
    grouped: dict[tuple[str, str, int], dict[str, object]] = {}

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            obcina_sifra = (row.get("municipality_id") or "").strip()
            if not obcina_sifra:
                continue

            species_number = (row.get("species_number") or "").strip()
            species_key = normalize_species_key(species_number)
            station_count = parse_float(row.get("Station_count")) or 1.0
            source_name = (row.get("municipality_name") or "").strip()

            for year_column in OBROD_YEAR_COLUMNS:
                year_value = int(year_column.split("_")[1])
                obrod_value = parse_float(row.get(year_column))
                if obrod_value is None:
                    continue
                key = (obcina_sifra, species_key, year_value)
                record = grouped.setdefault(
                    key,
                    {
                        "year": year_value,
                        "obcina_sifra": obcina_sifra,
                        "obcina_naziv": canonical_names.get(obcina_sifra, source_name),
                        "source_municipality_names": [],
                        "species_number": species_number,
                        "species_key": species_key,
                        "weighted_values": [],
                        "row_count": 0,
                        "station_count_sum": 0,
                    },
                )
                record["weighted_values"].append((obrod_value, station_count))
                record["row_count"] += 1
                record["station_count_sum"] += int(round(station_count))
                if source_name:
                    record["source_municipality_names"].append(source_name)

    long_rows = []
    species_keys = sorted({key[1] for key in grouped}, key=lambda item: (item == "unknown", item))
    yearly_species_map: dict[tuple[str, int], dict[str, object]] = {}
    yearly_summary_map: dict[tuple[str, int], dict[str, object]] = {}

    for key in sorted(grouped, key=lambda item: (int(item[0]), item[2], item[1])):
        record = grouped[key]
        source_names = record.pop("source_municipality_names")
        weighted_values = record.pop("weighted_values")
        value = weighted_average(weighted_values)
        long_row = {
            **record,
            "source_municipality_name": Counter(source_names).most_common(1)[0][0] if source_names else "",
            "obrod_value": "" if value is None else round(value, 6),
            "component_row_count": record["row_count"],
            "station_count_weight_sum": record["station_count_sum"],
        }
        long_rows.append(long_row)

        map_key = (long_row["obcina_sifra"], long_row["year"])
        species_row = yearly_species_map.setdefault(
            map_key,
            {
                "year": long_row["year"],
                "obcina_sifra": long_row["obcina_sifra"],
                "obcina_naziv": long_row["obcina_naziv"],
            },
        )
        species_row[f"obrod_species_{long_row['species_key']}"] = long_row["obrod_value"]

        summary_row = yearly_summary_map.setdefault(
            map_key,
            {
                "year": long_row["year"],
                "obcina_sifra": long_row["obcina_sifra"],
                "obcina_naziv": long_row["obcina_naziv"],
                "values": [],
            },
        )
        if value is not None:
            summary_row["values"].append(value)

    long_fieldnames = [
        "year",
        "obcina_sifra",
        "obcina_naziv",
        "source_municipality_name",
        "species_number",
        "species_key",
        "obrod_value",
        "component_row_count",
        "station_count_weight_sum",
    ]
    long_path = OUTPUT_DIR / "obrod_yearly_long.csv"
    long_count = write_csv(long_path, long_fieldnames, long_rows)

    species_fieldnames = ["year", "obcina_sifra", "obcina_naziv"] + [
        f"obrod_species_{species_key}" for species_key in species_keys
    ]
    species_rows = [
        yearly_species_map[key]
        for key in sorted(yearly_species_map, key=lambda item: (int(item[0]), item[1]))
    ]
    species_path = OUTPUT_DIR / "obrod_yearly_species_wide.csv"
    species_count = write_csv(species_path, species_fieldnames, species_rows)

    summary_rows = []
    for key in sorted(yearly_summary_map, key=lambda item: (int(item[0]), item[1])):
        row = yearly_summary_map[key]
        values = row.pop("values")
        summary_rows.append(
            {
                **row,
                "obrod_species_nonmissing_count": len(values),
                "obrod_value_mean": "" if not values else round(mean(values), 6),
                "obrod_value_min": "" if not values else round(min(values), 6),
                "obrod_value_max": "" if not values else round(max(values), 6),
                "obrod_value_sum": "" if not values else round(sum(values), 6),
            }
        )

    summary_fieldnames = [
        "year",
        "obcina_sifra",
        "obcina_naziv",
        "obrod_species_nonmissing_count",
        "obrod_value_mean",
        "obrod_value_min",
        "obrod_value_max",
        "obrod_value_sum",
    ]
    summary_path = OUTPUT_DIR / "obrod_yearly_summary_features.csv"
    summary_count = write_csv(summary_path, summary_fieldnames, summary_rows)

    species_lookup = {(row["obcina_sifra"], row["year"]): row for row in species_rows}
    summary_lookup = {(row["obcina_sifra"], row["year"]): row for row in summary_rows}
    weekly_rows = []
    weekly_fieldnames = [
        "week_start",
        "week_end",
        "iso_year",
        "iso_week",
        "week_mid_date",
        "calendar_year",
        "obcina_sifra",
        "obcina_naziv",
        "obrod_species_nonmissing_count",
        "obrod_value_mean",
        "obrod_value_min",
        "obrod_value_max",
        "obrod_value_sum",
    ] + [f"obrod_species_{species_key}" for species_key in species_keys]

    for week in week_records:
        calendar_year = week.week_mid_calendar_year
        for obcina_sifra, year in sorted(
            [item for item in summary_lookup if item[1] == calendar_year],
            key=lambda item: int(item[0]),
        ):
            summary_row = summary_lookup[(obcina_sifra, year)]
            species_row = species_lookup.get((obcina_sifra, year), {})
            weekly_row = {
                "week_start": week.week_start,
                "week_end": week.week_end,
                "iso_year": week.iso_year,
                "iso_week": week.iso_week,
                "week_mid_date": week.week_mid_date,
                "calendar_year": calendar_year,
                "obcina_sifra": obcina_sifra,
                "obcina_naziv": summary_row["obcina_naziv"],
                "obrod_species_nonmissing_count": summary_row["obrod_species_nonmissing_count"],
                "obrod_value_mean": summary_row["obrod_value_mean"],
                "obrod_value_min": summary_row["obrod_value_min"],
                "obrod_value_max": summary_row["obrod_value_max"],
                "obrod_value_sum": summary_row["obrod_value_sum"],
            }
            for species_key in species_keys:
                column_name = f"obrod_species_{species_key}"
                weekly_row[column_name] = species_row.get(column_name, "")
            weekly_rows.append(weekly_row)

    weekly_path = OUTPUT_DIR / "obrod_weekly_features_from_yearly.csv"
    weekly_count = write_csv(weekly_path, weekly_fieldnames, weekly_rows)

    return {
        long_path.name: {"rows": long_count, "columns": len(long_fieldnames)},
        species_path.name: {"rows": species_count, "columns": len(species_fieldnames)},
        summary_path.name: {"rows": summary_count, "columns": len(summary_fieldnames)},
        weekly_path.name: {"rows": weekly_count, "columns": len(weekly_fieldnames)},
    }


def write_summary(
    output_files: dict[str, dict[str, int]],
    canonical_names: dict[str, str],
    week_records: list[WeekRecord],
) -> None:
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": str(Path(__file__).resolve()),
        "output_dir": str(OUTPUT_DIR.resolve()),
        "canonical_municipality_count": len(canonical_names),
        "nijz_week_count": len(week_records),
        "assumptions": [
            "Raw source files are not modified; all outputs are written to a separate normalized folder.",
            "ARSO duplicate municipality-month-parameter rows are collapsed with a Station_count-weighted average.",
            "ARSO monthly features are mapped to NIJZ weeks using the month of week_mid_date.",
            "GOZDIS ISO year/week rows are converted to week_start and week_end using ISO Monday-to-Sunday dates.",
            "OBROD wide yearly columns are unpivoted to long yearly rows.",
            "OBROD duplicate municipality-species-year values are collapsed with a Station_count-weighted average.",
            "OBROD yearly features are mapped to NIJZ weeks using the calendar year of week_mid_date.",
            "NIJZ municipality names are used as canonical standardized names when available.",
        ],
        "output_files": output_files,
    }
    output_path = OUTPUT_DIR / "normalization_run_summary.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def main() -> None:
    ensure_output_dir()
    canonical_names, week_records = canonical_name_map()

    output_files: dict[str, dict[str, int]] = {}
    output_files.update(arso_outputs(canonical_names, week_records))
    output_files.update(gozdis_outputs(canonical_names))
    output_files.update(obrod_outputs(canonical_names, week_records))
    write_summary(output_files, canonical_names, week_records)

    print("Normalized local datasets written to:")
    print(OUTPUT_DIR)
    for name in sorted(output_files):
        stats = output_files[name]
        print(f"- {name}: {stats['rows']} rows, {stats['columns']} columns")
    print("- normalization_run_summary.json")


if __name__ == "__main__":
    main()
