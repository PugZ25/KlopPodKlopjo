#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


DATASET_NAME = "reanalysis-era5-land"
DEFAULT_AREA = [46.9, 13.3, 45.3, 16.6]  # north, west, south, east
DEFAULT_AVAILABILITY_LAG_DAYS = 5
DEFAULT_YEARS_BACK = 10
REQUEST_VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "total_precipitation",
    "soil_temperature_level_1",
    "soil_temperature_level_2",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
]
HOURS = [f"{hour:02d}:00" for hour in range(24)]


@dataclass(frozen=True)
class MonthWindow:
    year: int
    month: int
    start_date: date
    end_date: date

    @property
    def raw_filename(self) -> str:
        return f"era5land_slovenia_{self.year}_{self.month:02d}.nc"

    @property
    def feature_filename(self) -> str:
        return f"era5land_slovenia_features_{self.year}_{self.month:02d}.nc"

    def to_dict(self) -> dict[str, str | int]:
        return {
            "year": self.year,
            "month": self.month,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "raw_filename": self.raw_filename,
            "feature_filename": self.feature_filename,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download ERA5-Land hourly data for Slovenia, then derive project-ready "
            "meteorological features."
        )
    )
    parser.add_argument(
        "--start-date",
        help="Start date in ISO format (YYYY-MM-DD). If omitted, computed from --years-back.",
    )
    parser.add_argument(
        "--end-date",
        help=(
            "End date in ISO format (YYYY-MM-DD). If omitted, uses today's date minus "
            "--availability-lag-days."
        ),
    )
    parser.add_argument(
        "--years-back",
        type=int,
        default=DEFAULT_YEARS_BACK,
        help=f"How many years back to fetch. Default: {DEFAULT_YEARS_BACK}.",
    )
    parser.add_argument(
        "--availability-lag-days",
        type=int,
        default=DEFAULT_AVAILABILITY_LAG_DAYS,
        help=(
            "Default end-date lag behind today to avoid requesting data not yet published. "
            f"Default: {DEFAULT_AVAILABILITY_LAG_DAYS}."
        ),
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        metavar=("NORTH", "WEST", "SOUTH", "EAST"),
        type=float,
        default=DEFAULT_AREA,
        help="Bounding box for Slovenia in CDS area order: north west south east.",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw/copernicus/era5land_slovenia",
        help="Directory for raw monthly NetCDF files.",
    )
    parser.add_argument(
        "--feature-dir",
        default="data/interim/features/copernicus/era5land_slovenia",
        help="Directory for derived monthly feature NetCDF files.",
    )
    parser.add_argument(
        "--max-months",
        type=int,
        help="Optional limit used for smoke tests or partial backfills.",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download raw NetCDF files only.",
    )
    parser.add_argument(
        "--transform-only",
        action="store_true",
        help="Build feature NetCDF files from existing raw files only.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download raw monthly files even if they already exist.",
    )
    parser.add_argument(
        "--force-transform",
        action="store_true",
        help="Rebuild feature monthly files even if they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned monthly requests without downloading anything.",
    )
    return parser


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - years)


def build_date_range(args: argparse.Namespace) -> tuple[date, date]:
    end_date = (
        parse_iso_date(args.end_date)
        if args.end_date
        else date.today() - timedelta(days=args.availability_lag_days)
    )
    start_date = (
        parse_iso_date(args.start_date)
        if args.start_date
        else subtract_years(end_date, args.years_back)
    )

    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date.")

    return start_date, end_date


def iter_month_windows(start_date: date, end_date: date) -> list[MonthWindow]:
    windows: list[MonthWindow] = []
    cursor = date(start_date.year, start_date.month, 1)

    while cursor <= end_date:
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        month_start = max(start_date, cursor)
        month_end = min(end_date, date(cursor.year, cursor.month, last_day))
        windows.append(
            MonthWindow(
                year=cursor.year,
                month=cursor.month,
                start_date=month_start,
                end_date=month_end,
            )
        )
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    return windows


def build_cds_request(window: MonthWindow, bbox: list[float]) -> dict[str, object]:
    return {
        "variable": REQUEST_VARIABLES,
        "year": [f"{window.year:04d}"],
        "month": [f"{window.month:02d}"],
        "day": [f"{day:02d}" for day in range(window.start_date.day, window.end_date.day + 1)],
        "time": HOURS,
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": bbox,
    }


def ensure_download_dependencies() -> None:
    try:
        import cdsapi  # noqa: F401
    except ImportError as exc:
        module_name = exc.name or "a required dependency"
        print(
            "Missing dependency: "
            f"{module_name}. Install with:\n"
            "python3 -m pip install -r scripts/data/copernicus/requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def ensure_transform_dependencies() -> None:
    try:
        import netCDF4  # noqa: F401
        import numpy as np  # noqa: F401
        import pandas as pd  # noqa: F401
        import xarray as xr  # noqa: F401
    except ImportError as exc:
        module_name = exc.name or "a required dependency"
        print(
            "Missing dependency: "
            f"{module_name}. Install with:\n"
            "python3 -m pip install -r scripts/data/copernicus/requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def collapse_expver(ds):
    import xarray as xr

    if "expver" not in ds.dims:
        return ds

    merged_vars = {}
    for name, variable in ds.data_vars.items():
        if "expver" not in variable.dims:
            merged_vars[name] = variable
            continue

        merged = variable.isel(expver=0)
        for index in range(1, variable.sizes["expver"]):
            merged = merged.combine_first(variable.isel(expver=index))
        merged_vars[name] = merged

    coords = {name: coord for name, coord in ds.coords.items() if name != "expver"}
    collapsed = xr.Dataset(merged_vars, coords=coords, attrs=ds.attrs)
    return collapsed


def normalize_dataset(ds):
    rename_map = {}

    if "valid_time" in ds.dims and "time" not in ds.dims:
        rename_map["valid_time"] = "time"
    elif "valid_time" in ds.coords and "time" not in ds.coords:
        rename_map["valid_time"] = "time"

    if "lat" in ds.dims or "lat" in ds.coords:
        rename_map["lat"] = "latitude"
    if "lon" in ds.dims or "lon" in ds.coords:
        rename_map["lon"] = "longitude"

    if rename_map:
        ds = ds.rename(rename_map)

    ds = collapse_expver(ds)

    if "time" not in ds.coords:
        raise ValueError("Expected a time coordinate after normalization.")

    return ds.sortby("time")


def get_variable(ds, *aliases):
    for alias in aliases:
        if alias in ds.data_vars:
            return ds[alias]
    raise KeyError(f"Could not find any of the expected variables: {aliases}")


def compute_relative_humidity(temp_c, dewpoint_c):
    import numpy as np

    alpha_temp = (17.625 * temp_c) / (243.04 + temp_c)
    alpha_dew = (17.625 * dewpoint_c) / (243.04 + dewpoint_c)
    rh = 100.0 * np.exp(alpha_dew - alpha_temp)
    return rh.clip(min=0.0, max=100.0)


def project_variable(values, source, long_name: str, units: str, **extra_attrs):
    projected = values.astype("float32")
    projected.attrs = {
        "long_name": long_name,
        "units": units,
        "source_variable": source.name or "unknown",
        "source_units": source.attrs.get("units", "unknown"),
    }
    projected.attrs.update(extra_attrs)
    return projected


def deaccumulate_era5land_precipitation(tp_m):
    import numpy as np
    import pandas as pd
    import xarray as xr

    tp_mm = (tp_m * 1000.0).transpose("time", ...)
    timestamps = pd.to_datetime(tp_mm["time"].values)
    grouped_indices: dict[pd.Timestamp, list[tuple[int, int]]] = {}
    hourly_slices = [None] * tp_mm.sizes["time"]

    for index, timestamp in enumerate(timestamps):
        accumulation_day = (
            (timestamp - pd.Timedelta(days=1)).normalize()
            if timestamp.hour == 0
            else timestamp.normalize()
        )
        step_hour = 24 if timestamp.hour == 0 else timestamp.hour
        grouped_indices.setdefault(accumulation_day, []).append((step_hour, index))

    zero_template = np.zeros_like(tp_mm.isel(time=0).values, dtype=np.float64)

    for step_indices in grouped_indices.values():
        step_indices.sort(key=lambda item: item[0])
        previous_cumulative = zero_template.copy()

        for _step_hour, index in step_indices:
            current_cumulative = tp_mm.isel(time=index).values.astype(np.float64)
            hourly_increment = current_cumulative - previous_cumulative
            hourly_increment = np.where(hourly_increment < 0.0, 0.0, hourly_increment)
            hourly_slices[index] = hourly_increment.astype(np.float32)
            previous_cumulative = current_cumulative

    hourly_values = np.stack(hourly_slices, axis=0)
    return xr.DataArray(
        hourly_values,
        coords=tp_mm.coords,
        dims=tp_mm.dims,
        attrs={
            "long_name": "Hourly precipitation derived from ERA5-Land total precipitation",
            "units": "mm",
            "source_variable": tp_m.name or "total_precipitation",
            "note": (
                "ERA5-Land total precipitation is stored as an accumulated field. "
                "This variable contains hourly de-accumulated precipitation."
            ),
        },
    )


def build_feature_dataset(ds, source_file: str):
    ds = normalize_dataset(ds)

    t2m = get_variable(ds, "t2m", "2m_temperature")
    d2m = get_variable(ds, "d2m", "2m_dewpoint_temperature")
    tp = get_variable(ds, "tp", "total_precipitation")
    stl1 = get_variable(ds, "stl1", "soil_temperature_level_1")
    stl2 = get_variable(ds, "stl2", "soil_temperature_level_2")
    swvl1 = get_variable(ds, "swvl1", "volumetric_soil_water_layer_1")
    swvl2 = get_variable(ds, "swvl2", "volumetric_soil_water_layer_2")

    air_temperature_c = project_variable(
        t2m - 273.15,
        t2m,
        "Air temperature at 2 m",
        "degC",
    )
    dewpoint_temperature_c = project_variable(
        d2m - 273.15,
        d2m,
        "Dewpoint temperature at 2 m",
        "degC",
    )
    relative_humidity_pct = project_variable(
        compute_relative_humidity(air_temperature_c, dewpoint_temperature_c),
        d2m,
        "Relative humidity at 2 m",
        "%",
        formula=(
            "100 * exp((17.625 * Td) / (243.04 + Td) - "
            "(17.625 * T) / (243.04 + T))"
        ),
        formula_temperature_unit="degC",
    )
    precipitation_hourly_mm = deaccumulate_era5land_precipitation(tp).astype("float32")
    soil_temperature_level_1_c = project_variable(
        stl1 - 273.15,
        stl1,
        "Soil temperature level 1 (0-7 cm)",
        "degC",
    )
    soil_temperature_level_2_c = project_variable(
        stl2 - 273.15,
        stl2,
        "Soil temperature level 2 (7-28 cm)",
        "degC",
    )
    soil_water_layer_1 = project_variable(
        swvl1,
        swvl1,
        "Volumetric soil water layer 1 (0-7 cm)",
        "m3 m-3",
    )
    soil_water_layer_2 = project_variable(
        swvl2,
        swvl2,
        "Volumetric soil water layer 2 (7-28 cm)",
        "m3 m-3",
    )

    feature_ds = air_temperature_c.to_dataset(name="air_temperature_c")
    feature_ds["dewpoint_temperature_c"] = dewpoint_temperature_c
    feature_ds["relative_humidity_pct"] = relative_humidity_pct
    feature_ds["precipitation_hourly_mm"] = precipitation_hourly_mm
    feature_ds["soil_temperature_level_1_c"] = soil_temperature_level_1_c
    feature_ds["soil_temperature_level_2_c"] = soil_temperature_level_2_c
    feature_ds["soil_water_layer_1_m3_m3"] = soil_water_layer_1
    feature_ds["soil_water_layer_2_m3_m3"] = soil_water_layer_2

    drop_coords = [name for name in ("expver", "number") if name in feature_ds.coords]
    if drop_coords:
        feature_ds = feature_ds.reset_coords(drop_coords, drop=True)

    feature_ds.attrs.update(
        {
            "title": "ERA5-Land Slovenia project features",
            "source_dataset": DATASET_NAME,
            "source_file": source_file,
            "region_name": "Slovenia",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    return feature_ds


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def download_month(client, window: MonthWindow, bbox: list[float], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = build_cds_request(window, bbox)
    client.retrieve(DATASET_NAME, request, str(target))


def transform_month(raw_path: Path, feature_path: Path) -> None:
    import xarray as xr

    feature_path.parent.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(raw_path) as ds:
        feature_ds = build_feature_dataset(ds, raw_path.name)
        feature_ds.to_netcdf(feature_path)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.download_only and args.transform_only:
        parser.error("Use either --download-only or --transform-only, not both.")

    try:
        start_date, end_date = build_date_range(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    raw_dir = Path(args.raw_dir)
    raw_hourly_dir = raw_dir / "hourly"
    feature_dir = Path(args.feature_dir)
    feature_hourly_dir = feature_dir / "hourly"

    windows = iter_month_windows(start_date, end_date)
    if args.max_months is not None:
        windows = windows[: args.max_months]

    if not windows:
        print("No monthly windows to process.", file=sys.stderr)
        return 1

    manifest = {
        "dataset": DATASET_NAME,
        "region_name": "Slovenia",
        "area_bbox": list(args.bbox),
        "requested_variables": REQUEST_VARIABLES,
        "time_window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "availability_lag_days": args.availability_lag_days,
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_dir": str(raw_dir.resolve()),
        "feature_dir": str(feature_dir.resolve()),
        "monthly_files": [],
    }

    print(
        f"Planned ERA5-Land download for Slovenia: {start_date.isoformat()} -> "
        f"{end_date.isoformat()} ({len(windows)} monthly files)"
    )

    if args.dry_run:
        for window in windows:
            print(
                f"- {window.year}-{window.month:02d}: "
                f"{window.start_date.isoformat()} -> {window.end_date.isoformat()}"
            )
        return 0

    client = None
    if not args.transform_only:
        ensure_download_dependencies()
        import cdsapi

        client = cdsapi.Client()

    if not args.download_only:
        ensure_transform_dependencies()

    for index, window in enumerate(windows, start=1):
        raw_path = raw_hourly_dir / window.raw_filename
        feature_path = feature_hourly_dir / window.feature_filename
        downloaded = False
        transformed = False

        print(
            f"[{index}/{len(windows)}] {window.year}-{window.month:02d} "
            f"({window.start_date.isoformat()} -> {window.end_date.isoformat()})"
        )

        if not args.transform_only:
            if raw_path.exists() and not args.force_download:
                print(f"  raw exists, skipping download: {raw_path}")
            else:
                print(f"  downloading raw NetCDF -> {raw_path}")
                download_month(client, window, list(args.bbox), raw_path)
                downloaded = True

        if not args.download_only:
            if not raw_path.exists():
                raise FileNotFoundError(
                    f"Raw file not found for transform step: {raw_path}"
                )
            if feature_path.exists() and not args.force_transform:
                print(f"  features exist, skipping transform: {feature_path}")
            else:
                print(f"  building feature NetCDF -> {feature_path}")
                transform_month(raw_path, feature_path)
                transformed = True

        manifest["monthly_files"].append(
            {
                **window.to_dict(),
                "raw_path": str(raw_path.resolve()),
                "feature_path": str(feature_path.resolve()),
                "downloaded_now": downloaded,
                "transformed_now": transformed,
                "raw_exists": raw_path.exists(),
                "feature_exists": feature_path.exists(),
            }
        )

        write_json(raw_dir / "manifest.json", manifest)
        write_json(feature_dir / "manifest.json", manifest)

    print("ERA5-Land Slovenia workflow completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
