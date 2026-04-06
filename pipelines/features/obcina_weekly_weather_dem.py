from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_WEATHER_INPUT = Path("data/processed/training/obcina_weekly_weather_features.csv")
DEFAULT_DEM_INPUT = Path("data/processed/training/obcina_dem_features.csv")
DEFAULT_OUTPUT = Path("data/processed/training/obcina_weekly_weather_dem_features.csv")
DEFAULT_MANIFEST_OUTPUT = Path(
    "data/processed/training/obcina_weekly_weather_dem_features_manifest.json"
)
DEM_FEATURE_COLUMNS = [
    "elevation_m_mean",
    "elevation_m_std",
    "elevation_m_range",
]


@dataclass(frozen=True)
class CombinedFeatureTables:
    combined: Any
    manifest: dict[str, Any]


def _ensure_columns(frame: Any, required_columns: list[str], *, label: str) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def build_weekly_weather_dem_features(
    *,
    weather_input: Path = DEFAULT_WEATHER_INPUT,
    dem_input: Path = DEFAULT_DEM_INPUT,
) -> CombinedFeatureTables:
    import pandas as pd

    if not weather_input.exists():
        raise FileNotFoundError(f"Weather feature CSV not found: {weather_input}")
    if not dem_input.exists():
        raise FileNotFoundError(f"DEM feature CSV not found: {dem_input}")

    weather = pd.read_csv(weather_input)
    dem = pd.read_csv(dem_input)

    _ensure_columns(
        weather,
        ["obcina_sifra", "obcina_naziv"],
        label="Weekly weather feature CSV",
    )

    # The combined file should add DEM columns only if they are not already present.
    overlapping_dem_columns = [column for column in DEM_FEATURE_COLUMNS if column in weather.columns]
    if overlapping_dem_columns:
        weather = weather.drop(columns=overlapping_dem_columns)

    _ensure_columns(
        dem,
        ["obcina_sifra", "obcina_naziv", *DEM_FEATURE_COLUMNS],
        label="DEM feature CSV",
    )

    dem_subset = dem[["obcina_sifra", "obcina_naziv", *DEM_FEATURE_COLUMNS]].copy()
    duplicated = dem_subset["obcina_sifra"].duplicated(keep=False)
    if duplicated.any():
        duplicate_codes = sorted(dem_subset.loc[duplicated, "obcina_sifra"].astype(str).unique().tolist())
        raise ValueError(
            "DEM feature CSV has duplicate municipality codes: " + ", ".join(duplicate_codes)
        )

    combined = weather.merge(
        dem_subset,
        on="obcina_sifra",
        how="left",
        validate="many_to_one",
        suffixes=("", "_dem"),
    )

    if "obcina_naziv_dem" in combined.columns:
        mismatch = combined[
            combined["obcina_naziv_dem"].notna()
            & (combined["obcina_naziv"].astype(str) != combined["obcina_naziv_dem"].astype(str))
        ]
        if not mismatch.empty:
            sample = mismatch.iloc[0]
            raise ValueError(
                "Municipality name mismatch for code "
                f"{sample['obcina_sifra']}: weather='{sample['obcina_naziv']}', "
                f"dem='{sample['obcina_naziv_dem']}'"
            )
        combined = combined.drop(columns=["obcina_naziv_dem"])

    missing_dem = combined[DEM_FEATURE_COLUMNS].isna().any(axis=1)
    if missing_dem.any():
        missing_codes = sorted(combined.loc[missing_dem, "obcina_sifra"].astype(str).unique().tolist())
        raise ValueError(
            "DEM features are missing for municipality codes: " + ", ".join(missing_codes)
        )

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "weather_input": str(weather_input.resolve()),
        "dem_input": str(dem_input.resolve()),
        "row_count": int(len(combined)),
        "municipality_count": int(combined["obcina_sifra"].astype(str).nunique()),
        "added_dem_columns": DEM_FEATURE_COLUMNS,
        "combined_columns": combined.columns.tolist(),
    }
    return CombinedFeatureTables(combined=combined, manifest=manifest)


def write_weekly_weather_dem_features(
    tables: CombinedFeatureTables,
    *,
    output_path: Path = DEFAULT_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.combined.to_csv(output_path, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")
