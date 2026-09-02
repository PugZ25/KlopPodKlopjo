from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
EXPLANATORY_ROOT = WORKSPACE_ROOT / "environmental_explanation_project"
GITLOOKUP_ROOT = WORKSPACE_ROOT / "GITlookup" / "KlopPodKlopjo-main"

RAW_DIR = PROJECT_ROOT / "raw"
DOCS_DIR = PROJECT_ROOT / "docs"
REPORTS_DIR = PROJECT_ROOT / "reports"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
INTERIM_DIR = PROJECT_ROOT / "interim"
PROCESSED_DIR = PROJECT_ROOT / "processed"
REFERENCE_DIR = PROJECT_ROOT / "reference data"
REFERENCE_LOCKED_DIR = REFERENCE_DIR / "locked_explanatory"

COPERNICUS_RAW_DIR = RAW_DIR / "copernicus"
GURS_RAW_DIR = RAW_DIR / "gurs"

ERA5LAND_RAW_DIR = COPERNICUS_RAW_DIR / "era5land_slovenia"
DEM_RAW_DIR = COPERNICUS_RAW_DIR / "copernicus_dem_slovenia"
CLC_RAW_DIR = COPERNICUS_RAW_DIR / "clms_land_cover_slovenia"
FORECAST_RAW_DIR = COPERNICUS_RAW_DIR / "forecast"
CLIMATE_ATLAS_RAW_DIR = COPERNICUS_RAW_DIR / "climate_atlas"

ERA5LAND_FEATURE_DIR = INTERIM_DIR / "features" / "copernicus" / "era5land_slovenia"
ERA5LAND_FEATURE_HOURLY_DIR = ERA5LAND_FEATURE_DIR / "hourly"
WEATHER_OVERLAY_OUTPUT = ERA5LAND_FEATURE_DIR / "obcina_grid_overlay.csv"
WEATHER_DAILY_OUTPUT = ERA5LAND_FEATURE_DIR / "obcina_daily_weather.csv"
WEATHER_WEEKLY_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_weekly_weather_features.csv"
WEATHER_WEEKLY_MANIFEST = PROCESSED_DIR / "municipality" / "obcina_weekly_weather_features_manifest.json"

DEM_INTERIM_DIR = INTERIM_DIR / "features" / "copernicus" / "copernicus_dem_slovenia"
DEM_TILE_COVERAGE_OUTPUT = DEM_INTERIM_DIR / "obcina_dem_tile_coverage.csv"
DEM_SUMMARY_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_dem_features.csv"
DEM_MANIFEST_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_dem_features_manifest.json"

CLC_INTERIM_DIR = INTERIM_DIR / "features" / "copernicus" / "clms_land_cover_slovenia"
CLC_SAMPLING_OUTPUT = CLC_INTERIM_DIR / "obcina_clc_sampling.csv"
CLC_SUMMARY_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_clc_features.csv"
CLC_MANIFEST_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_clc_features_manifest.json"

MUNICIPALITY_WEEKLY_PANEL_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_weekly_predictive_panel.csv"
MUNICIPALITY_MONTHLY_PANEL_OUTPUT = PROCESSED_DIR / "municipality" / "obcina_monthly_predictive_panel.csv"
SLOVENIA_MONTHLY_PANEL_OUTPUT = PROCESSED_DIR / "slovenia" / "slovenia_monthly_predictive_panel.csv"
SLOVENIA_YEARLY_PANEL_OUTPUT = PROCESSED_DIR / "slovenia" / "slovenia_yearly_predictive_panel.csv"
PANEL_MANIFEST_OUTPUT = PROCESSED_DIR / "predictive_panel_manifest.json"

LOCKED_NIJZ_WEEKLY_SOURCE = (
    EXPLANATORY_ROOT / "input data" / "NIJZ" / "obcina_weekly_epidemiology_KME_Boreliosis.csv"
)
LOCKED_POPULATION_SOURCE = (
    EXPLANATORY_ROOT / "input data" / "Copernicus" / "obcina_surs_population_density_yearly_features.csv"
)
LOCKED_LOG_POPULATION_SOURCE = (
    EXPLANATORY_ROOT / "input data" / "Copernicus" / "obcina_surs_log_population_yearly_features.csv"
)

REFERENCE_NIJZ_WEEKLY = REFERENCE_LOCKED_DIR / "obcina_weekly_epidemiology_KME_Boreliosis.csv"
REFERENCE_POPULATION = REFERENCE_LOCKED_DIR / "obcina_surs_population_density_yearly_features.csv"
REFERENCE_LOG_POPULATION = REFERENCE_LOCKED_DIR / "obcina_surs_log_population_yearly_features.csv"

GITLOOKUP_ERA5_SCRIPT = GITLOOKUP_ROOT / "scripts" / "data" / "copernicus" / "download_era5land_slovenia.py"
GITLOOKUP_BUILD_WEATHER_SCRIPT = GITLOOKUP_ROOT / "scripts" / "data" / "copernicus" / "build_obcina_weekly_features.py"
GITLOOKUP_BUILD_DEM_SCRIPT = GITLOOKUP_ROOT / "scripts" / "data" / "copernicus" / "build_obcina_dem_features.py"
GITLOOKUP_BUILD_CLC_SCRIPT = GITLOOKUP_ROOT / "scripts" / "data" / "copernicus" / "build_obcina_clc_features.py"

FORECAST_DATASET_DIRNAME_MAP = {
    "monthly_stats": "seasonal-monthly-single-levels",
    "monthly_anomalies": "seasonal-postprocessed-single-levels",
    "daily_original": "seasonal-original-single-levels",
}

LOCKED_COPERNICUS_FORECAST_FAMILIES = [
    "copernicus_temperature",
    "copernicus_humidity",
    "copernicus_precipitation",
    "copernicus_soil",
]

FAMILY_OUTPUT_DIRS = {
    family: FORECAST_RAW_DIR / family for family in LOCKED_COPERNICUS_FORECAST_FAMILIES
}

SLOVENIA_BBOX_NWSE = [46.9, 13.3, 45.3, 16.6]


def forecast_output_dir(variable_family: str, dataset_kind: str) -> Path:
    return FAMILY_OUTPUT_DIRS[variable_family] / FORECAST_DATASET_DIRNAME_MAP[dataset_kind]


def ensure_project_dirs() -> None:
    for path in [
        RAW_DIR,
        DOCS_DIR,
        REPORTS_DIR,
        SCRIPTS_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        REFERENCE_DIR,
        REFERENCE_LOCKED_DIR,
        COPERNICUS_RAW_DIR,
        GURS_RAW_DIR,
        FORECAST_RAW_DIR,
        CLIMATE_ATLAS_RAW_DIR,
        ERA5LAND_FEATURE_DIR,
        ERA5LAND_FEATURE_HOURLY_DIR,
        DEM_INTERIM_DIR,
        CLC_INTERIM_DIR,
        WEATHER_WEEKLY_OUTPUT.parent,
        SLOVENIA_MONTHLY_PANEL_OUTPUT.parent,
        *FAMILY_OUTPUT_DIRS.values(),
    ]:
        path.mkdir(parents=True, exist_ok=True)


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def run_subprocess(command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def module_available(module_name: str) -> bool:
    return find_spec(module_name) is not None


def env_var_present(name: str) -> bool:
    return bool(os.getenv(name))


def home_file_exists(name: str) -> bool:
    return (Path.home() / name).exists()


def count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob(pattern))


def summarize_raw_state() -> dict[str, object]:
    return {
        "era5land_hourly_nc_count": count_files(ERA5LAND_RAW_DIR / "hourly", "*.nc"),
        "copernicus_dem_tile_count": count_files(DEM_RAW_DIR / "tiles", "*.tif"),
        "clms_land_cover_tif_count": count_files(CLC_RAW_DIR, "*.tif"),
        "gurs_geojson_exists": (GURS_RAW_DIR / "obcine-gurs-rpe.geojson").exists(),
        "climate_atlas_zip_count": count_files(CLIMATE_ATLAS_RAW_DIR, "*.zip"),
        "forecast_family_dirs": {
            family: str(path) for family, path in FAMILY_OUTPUT_DIRS.items()
        },
    }
