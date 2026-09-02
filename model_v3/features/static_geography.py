from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyproj
from pyproj import Geod


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "static_geography.json"

OUTPUT_COLUMNS = ("municipality_code", "municipality_area_km2")


class StaticGeographyError(ValueError):
    """Raised when a static geographic source or feature violates its contract."""


def resolve_repo_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise StaticGeographyError(
            f"Configured path must be a non-empty string: {raw_path!r}"
        )
    relative = Path(raw_path)
    if relative.is_absolute():
        raise StaticGeographyError(
            f"Configured path must be repository-relative: {raw_path}"
        )
    resolved = (REPO_ROOT / relative).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise StaticGeographyError(f"Configured path leaves repository root: {raw_path}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise StaticGeographyError(
            f"Static geography configuration must be inside the repository: {path}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise StaticGeographyError("Configuration schema_version must equal 1.")
    expected_geometry = {
        "path": "data/raw/gurs/obcine-gurs-rpe.geojson",
        "provider": "Geodetic Administration of the Republic of Slovenia (GURS)",
        "layer": "TEMELJNE_VSEBINE/GH_Prostorske_enote/MapServer/1530",
        "download_date": "2026-04-04",
        "format": "GeoJSON",
        "crs": "EPSG:4326",
        "municipality_code_property": "SIFRA",
    }
    expected_municipality = {
        "path": "model_v3/outputs/canonical/municipality.csv",
        "municipality_code_column": "municipality_code",
    }
    expected_feature = {
        "column": "municipality_area_km2",
        "unit": "square_kilometres",
        "transformation": (
            "absolute_wgs84_ellipsoidal_polygon_area_m2_divided_by_1000000"
        ),
        "ellipsoid": "WGS84",
        "polygon_hole_rule": "subtract_absolute_geodesic_hole_areas",
        "multipolygon_rule": "sum_polygon_areas",
        "missing_data_rule": (
            "fail_on_missing_invalid_or_nonpositive_geometry_area"
        ),
        "source_geom_area_property_used": False,
        "source_geom_area_property_exclusion_reason": (
            "unit_not_verified_in_active_source_documentation"
        ),
    }
    expected_outputs = {
        "directory": "model_v3/outputs/static_geography",
        "features": "municipality_static_geography.csv",
        "quality_summary": "static_geography_quality_summary.json",
    }
    expected_temporal_policy = {
        "fixed_analytical_zones_all_years": True,
        "zone_snapshot": "GURS_2026-04-04",
        "historical_boundary_reconstruction": False,
        "interpretation": (
            "the_same_documented_212_municipality_zones_are_used_for_every_model_year"
        ),
    }
    sources = config.get("sources")
    if not isinstance(sources, dict):
        raise StaticGeographyError("Configuration sources are required.")
    if sources.get("municipality_geometry") != expected_geometry:
        raise StaticGeographyError("GURS geometry source configuration is unsupported.")
    if sources.get("canonical_municipality") != expected_municipality:
        raise StaticGeographyError(
            "Canonical municipality source configuration is unsupported."
        )
    if config.get("feature") != expected_feature:
        raise StaticGeographyError("Static feature configuration is unsupported.")
    if config.get("temporal_policy") != expected_temporal_policy:
        raise StaticGeographyError("Static geography temporal policy is unsupported.")
    if config.get("outputs") != expected_outputs:
        raise StaticGeographyError("Static geography outputs are unsupported.")
    return config


def canonical_code(value: object) -> str:
    if isinstance(value, bool):
        raise StaticGeographyError(f"Municipality code cannot be boolean: {value!r}")
    if isinstance(value, int):
        numeric = value
    elif isinstance(value, str) and value.strip().isdigit():
        numeric = int(value.strip())
    else:
        raise StaticGeographyError(f"Municipality code is invalid: {value!r}")
    if numeric < 0 or numeric > 999:
        raise StaticGeographyError(f"Municipality code is outside three digits: {numeric}")
    return f"{numeric:03d}"


def _ring_area_m2(ring: object, *, geod: Geod, context: str) -> float:
    if not isinstance(ring, list) or len(ring) < 4:
        raise StaticGeographyError(f"{context} must contain at least four positions.")
    longitudes: list[float] = []
    latitudes: list[float] = []
    positions: list[tuple[float, float]] = []
    for position_index, position in enumerate(ring, start=1):
        if not isinstance(position, list) or len(position) < 2:
            raise StaticGeographyError(
                f"{context} position {position_index} is not a coordinate pair."
            )
        longitude, latitude = position[0], position[1]
        if (
            isinstance(longitude, bool)
            or isinstance(latitude, bool)
            or not isinstance(longitude, (int, float))
            or not isinstance(latitude, (int, float))
            or not math.isfinite(float(longitude))
            or not math.isfinite(float(latitude))
        ):
            raise StaticGeographyError(
                f"{context} position {position_index} has invalid coordinates."
            )
        longitude = float(longitude)
        latitude = float(latitude)
        if not -180.0 <= longitude <= 180.0 or not -90.0 <= latitude <= 90.0:
            raise StaticGeographyError(
                f"{context} position {position_index} is outside EPSG:4326 bounds."
            )
        positions.append((longitude, latitude))
        longitudes.append(longitude)
        latitudes.append(latitude)
    if positions[0] != positions[-1]:
        raise StaticGeographyError(f"{context} is not a closed linear ring.")
    signed_area, _ = geod.polygon_area_perimeter(longitudes, latitudes)
    area = abs(float(signed_area))
    if not math.isfinite(area) or area <= 0:
        raise StaticGeographyError(f"{context} has nonpositive geodesic area.")
    return area


def geodesic_geometry_area_m2(
    geometry: object, *, geod: Geod, context: str
) -> float:
    if not isinstance(geometry, dict):
        raise StaticGeographyError(f"{context} geometry must be present.")
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise StaticGeographyError(
            f"{context} geometry type must be Polygon or MultiPolygon: {geometry_type!r}"
        )
    if not isinstance(polygons, list) or not polygons:
        raise StaticGeographyError(f"{context} has no polygon coordinates.")

    total_area = 0.0
    for polygon_index, polygon in enumerate(polygons, start=1):
        if not isinstance(polygon, list) or not polygon:
            raise StaticGeographyError(
                f"{context} polygon {polygon_index} has no exterior ring."
            )
        exterior = _ring_area_m2(
            polygon[0],
            geod=geod,
            context=f"{context} polygon {polygon_index} exterior",
        )
        holes = sum(
            _ring_area_m2(
                ring,
                geod=geod,
                context=f"{context} polygon {polygon_index} hole {hole_index}",
            )
            for hole_index, ring in enumerate(polygon[1:], start=1)
        )
        polygon_area = exterior - holes
        if polygon_area <= 0:
            raise StaticGeographyError(
                f"{context} polygon {polygon_index} has nonpositive area after holes."
            )
        total_area += polygon_area
    if not math.isfinite(total_area) or total_area <= 0:
        raise StaticGeographyError(f"{context} has invalid total geodesic area.")
    return total_area


def read_canonical_codes(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "municipality_code" not in set(reader.fieldnames or []):
            raise StaticGeographyError(
                "Canonical municipality input lacks municipality_code."
            )
        codes = [canonical_code(row["municipality_code"]) for row in reader]
    if not codes:
        raise StaticGeographyError("Canonical municipality input is empty.")
    if len(codes) != len(set(codes)):
        raise StaticGeographyError("Canonical municipality codes are duplicated.")
    return set(codes)


def build_feature_rows(
    payload: Mapping[str, object],
    *,
    canonical_codes: set[str],
    code_property: str,
    ellipsoid: str,
) -> tuple[list[dict[str, object]], list[int]]:
    if payload.get("type") != "FeatureCollection":
        raise StaticGeographyError("GURS source must be a GeoJSON FeatureCollection.")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise StaticGeographyError("GURS source has no features.")
    geod = Geod(ellps=ellipsoid)
    rows: list[dict[str, object]] = []
    system_timestamps: list[int] = []
    for feature_index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise StaticGeographyError(f"GURS feature {feature_index} is not an object.")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise StaticGeographyError(
                f"GURS feature {feature_index} has no properties object."
            )
        code = canonical_code(properties.get(code_property))
        area_m2 = geodesic_geometry_area_m2(
            feature.get("geometry"),
            geod=geod,
            context=f"GURS municipality {code}",
        )
        rows.append(
            {
                "municipality_code": code,
                "municipality_area_km2": area_m2 / 1_000_000.0,
            }
        )
        raw_timestamp = properties.get("DATUM_SYS")
        if isinstance(raw_timestamp, int) and not isinstance(raw_timestamp, bool):
            system_timestamps.append(raw_timestamp)
    codes = [str(row["municipality_code"]) for row in rows]
    if len(codes) != len(set(codes)):
        raise StaticGeographyError("GURS source has duplicate municipality codes.")
    observed_codes = set(codes)
    if observed_codes != canonical_codes:
        raise StaticGeographyError(
            "GURS and canonical municipality code sets differ: "
            f"GURS-only={sorted(observed_codes - canonical_codes)}, "
            f"canonical-only={sorted(canonical_codes - observed_codes)}"
        )
    rows.sort(key=lambda row: str(row["municipality_code"]))
    return rows, system_timestamps


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(OUTPUT_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "municipality_code": row["municipality_code"],
                    "municipality_area_km2": f"{float(row['municipality_area_km2']):.15g}",
                }
            )


def timestamp_iso_utc(milliseconds: int) -> str:
    return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc).isoformat()


def build_static_geography(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, object]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    geometry_config = config["sources"]["municipality_geometry"]
    municipality_config = config["sources"]["canonical_municipality"]
    geometry_path = resolve_repo_path(geometry_config["path"])
    municipality_path = resolve_repo_path(municipality_config["path"])
    if not geometry_path.is_file() or not municipality_path.is_file():
        raise StaticGeographyError("One or more static geography inputs are missing.")
    canonical_codes = read_canonical_codes(municipality_path)
    payload = json.loads(geometry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise StaticGeographyError("GURS GeoJSON root must be an object.")
    rows, system_timestamps = build_feature_rows(
        payload,
        canonical_codes=canonical_codes,
        code_property=geometry_config["municipality_code_property"],
        ellipsoid=config["feature"]["ellipsoid"],
    )

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    feature_path = output_directory / config["outputs"]["features"]
    quality_path = output_directory / config["outputs"]["quality_summary"]
    if feature_path.parent != output_directory or quality_path.parent != output_directory:
        raise StaticGeographyError("Output filenames must not contain subdirectories.")
    write_csv(feature_path, rows)
    areas = [float(row["municipality_area_km2"]) for row in rows]
    quality: dict[str, object] = {
        "schema_version": 1,
        "pipeline": "model_v3.features.static_geography",
        "status": "pass",
        "sources": {
            "municipality_geometry": {
                **file_record(geometry_path),
                **{
                    key: geometry_config[key]
                    for key in (
                        "provider",
                        "layer",
                        "download_date",
                        "format",
                        "crs",
                    )
                },
            },
            "canonical_municipality": file_record(municipality_path),
            "config": file_record(config_path),
            "builder": file_record(Path(__file__).resolve()),
        },
        "feature_dictionary": {
            "municipality_area_km2": config["feature"],
        },
        "dataset": {
            **file_record(feature_path),
            "columns": list(OUTPUT_COLUMNS),
            "primary_key": ["municipality_code"],
            "row_count": len(rows),
            "missing_value_count": 0,
            "minimum_area_km2": min(areas),
            "maximum_area_km2": max(areas),
            "total_area_km2": sum(areas),
        },
        "source_geometry_system_time": {
            "meaning": "GURS DATUM_SYS; semantic interpretation not asserted",
            "minimum_utc": (
                timestamp_iso_utc(min(system_timestamps))
                if system_timestamps
                else None
            ),
            "maximum_utc": (
                timestamp_iso_utc(max(system_timestamps))
                if system_timestamps
                else None
            ),
            "missing_count": len(rows) - len(system_timestamps),
        },
        "checks": {
            "municipality_codes_match_canonical_exactly": True,
            "municipality_codes_unique": True,
            "all_geometries_present_and_valid_for_area": True,
            "all_areas_positive_and_finite": all(
                math.isfinite(value) and value > 0 for value in areas
            ),
            "lockbox_outcome_data_accessed": False,
            "weather_features_created": False,
            "land_cover_features_created": False,
            "elevation_features_created": False,
        },
        "temporal_scope": {
            **config["temporal_policy"],
            "source_snapshot_interpretation": (
                "static descriptor of the documented GURS snapshot"
            ),
            "used_as_time_varying_feature": False,
        },
        "library_versions": {"pyproj": pyproj.__version__},
    }
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build verified model_v3 static municipality geography."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    quality = build_static_geography(config_path)
    dataset = quality["dataset"]
    print("Static municipality geography built.")
    print(f"- rows: {dataset['row_count']}")
    print(
        "- area range km2: "
        f"{dataset['minimum_area_km2']:.6f}..{dataset['maximum_area_km2']:.6f}"
    )
    print(f"- output: {dataset['path']}")
    print("No weather, lockbox outcome, model, or prediction was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
