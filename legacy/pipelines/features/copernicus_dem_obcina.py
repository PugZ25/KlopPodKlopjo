from __future__ import annotations

import json
import math
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_DEM_DIR = Path("data/raw/copernicus/copernicus_dem_slovenia")
DEFAULT_GEOJSON_PATH = Path("data/raw/gurs/obcine-gurs-rpe.geojson")
DEFAULT_TILE_COVERAGE_OUTPUT = Path(
    "data/interim/features/copernicus/copernicus_dem_slovenia/obcina_dem_tile_coverage.csv"
)
DEFAULT_SUMMARY_OUTPUT = Path("data/processed/training/obcina_dem_features.csv")
DEFAULT_MANIFEST_OUTPUT = Path("data/processed/training/obcina_dem_features_manifest.json")
OVERLAY_CRS = "EPSG:3794"
PIXEL_ASSIGNMENT_METHOD = "pixel_center_mask"
ROW_BLOCK_SIZE = 512


class ProcessingDependencyError(RuntimeError):
    """Raised when optional processing dependencies are missing."""


@dataclass(frozen=True)
class TileInfo:
    row: int
    col: int
    filename: str
    path: Path
    width_px: int
    height_px: int
    bbox_projected: tuple[float, float, float, float]
    x_resolution_m: float
    y_resolution_m: float
    pixel_area_m2: float
    nodata_value: float | None
    geometry_projected: Any


@dataclass
class MunicipalityAccumulator:
    obcina_sifra: str
    obcina_naziv: str
    eid_obcina: str
    ob_mid: str
    municipality_area_m2: float
    pixel_count: int = 0
    covered_area_m2: float = 0.0
    elevation_sum: float = 0.0
    elevation_sum_sq: float = 0.0
    elevation_min: float | None = None
    elevation_max: float | None = None
    used_tiles: set[str] = field(default_factory=set)

    def update(self, values: Any, *, pixel_area_m2: float, tile_filename: str) -> None:
        import numpy as np

        count = int(values.size)
        if count == 0:
            return

        values64 = values.astype(np.float64, copy=False)
        self.pixel_count += count
        self.covered_area_m2 += count * pixel_area_m2
        self.elevation_sum += float(values64.sum())
        self.elevation_sum_sq += float(np.square(values64).sum())

        block_min = float(values64.min())
        block_max = float(values64.max())
        self.elevation_min = block_min if self.elevation_min is None else min(self.elevation_min, block_min)
        self.elevation_max = block_max if self.elevation_max is None else max(self.elevation_max, block_max)
        self.used_tiles.add(tile_filename)

    def to_summary_row(
        self,
        *,
        dem_instance: str,
        heights: str,
        output_epsg: int,
        source_resolution_m: float,
    ) -> dict[str, Any]:
        if self.pixel_count <= 0 or self.elevation_min is None or self.elevation_max is None:
            raise ValueError(
                f"No DEM pixels were assigned to municipality {self.obcina_sifra} {self.obcina_naziv}."
            )

        mean_value = self.elevation_sum / self.pixel_count
        variance = max((self.elevation_sum_sq / self.pixel_count) - (mean_value * mean_value), 0.0)
        std_value = math.sqrt(variance)
        covered_area_pct = (
            (self.covered_area_m2 / self.municipality_area_m2) * 100.0
            if self.municipality_area_m2 > 0.0
            else 0.0
        )

        return {
            "obcina_sifra": self.obcina_sifra,
            "obcina_naziv": self.obcina_naziv,
            "eid_obcina": self.eid_obcina,
            "ob_mid": self.ob_mid,
            "municipality_area_m2": self.municipality_area_m2,
            "covered_area_m2": self.covered_area_m2,
            "covered_area_pct_estimate": covered_area_pct,
            "pixel_count": self.pixel_count,
            "tile_count": len(self.used_tiles),
            "assignment_method": PIXEL_ASSIGNMENT_METHOD,
            "dem_instance": dem_instance,
            "dem_heights": heights,
            "output_epsg": output_epsg,
            "source_resolution_m": source_resolution_m,
            "elevation_m_mean": mean_value,
            "elevation_m_std": std_value,
            "elevation_m_min": self.elevation_min,
            "elevation_m_max": self.elevation_max,
            "elevation_m_range": self.elevation_max - self.elevation_min,
        }


@dataclass(frozen=True)
class DemFeatureTables:
    tile_coverage: Any
    municipality_features: Any
    manifest: dict[str, Any]


def ensure_processing_dependencies() -> None:
    missing: list[str] = []
    for module_name in ("numpy", "pandas", "pyproj", "shapely", "PIL"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)

    if missing:
        raise ProcessingDependencyError(
            "Missing dependencies: "
            + ", ".join(sorted(missing))
            + ". Install with: python3 -m pip install -r scripts/data/copernicus/requirements.txt"
        )


def normalize_obcina_properties(properties: Mapping[str, object]) -> dict[str, str]:
    sifra = properties.get("SIFRA")
    naziv = properties.get("NAZIV")
    if sifra in (None, ""):
        raise ValueError("GeoJSON feature is missing SIFRA.")
    if naziv in (None, ""):
        raise ValueError("GeoJSON feature is missing NAZIV.")

    return {
        "obcina_sifra": str(sifra).strip(),
        "obcina_naziv": str(naziv).strip(),
        "eid_obcina": str(properties.get("EID_OBCINA", "")).strip(),
        "ob_mid": str(properties.get("OB_MID", "")).strip(),
    }


def _parse_nodata_value(raw_value: object) -> float | None:
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, bytes):
        raw_text = raw_value.decode("utf-8", errors="ignore")
    else:
        raw_text = str(raw_value)
    raw_text = raw_text.strip().strip("\x00")
    if not raw_text:
        return None
    try:
        return float(raw_text)
    except ValueError:
        return None


def _load_municipalities(
    geojson_path: Path,
    *,
    limit_obcine: int | None = None,
    obcina_sifre: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform

    selected_sifre = {value.strip() for value in obcina_sifre or [] if value.strip()}

    with geojson_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    transformer = Transformer.from_crs("EPSG:4326", OVERLAY_CRS, always_xy=True)
    project = transformer.transform

    municipalities: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        properties = normalize_obcina_properties(feature.get("properties", {}))
        if selected_sifre and properties["obcina_sifra"] not in selected_sifre:
            continue

        geometry_wgs84 = shape(feature["geometry"])
        geometry_projected = transform(project, geometry_wgs84)
        municipalities.append(
            {
                **properties,
                "geometry_projected": geometry_projected,
                "geometry_bounds": tuple(float(value) for value in geometry_projected.bounds),
                "municipality_area_m2": float(geometry_projected.area),
            }
        )

    municipalities.sort(key=lambda item: item["obcina_sifra"])
    if limit_obcine is not None:
        municipalities = municipalities[:limit_obcine]

    if not municipalities:
        raise ValueError(f"No municipality features found in {geojson_path}.")

    return municipalities


def _load_tile_array(tile: TileInfo) -> Any:
    import numpy as np
    from PIL import Image

    with Image.open(tile.path) as image:
        compression = int(image.tag_v2.get(259, 1))
        strip_offsets = image.tag_v2.get(273)
        strip_byte_counts = image.tag_v2.get(279)

    if strip_offsets is None or strip_byte_counts is None:
        raise ValueError(f"Tile {tile.filename} is missing TIFF strip metadata.")

    if isinstance(strip_offsets, int):
        strip_offsets = (strip_offsets,)
    if isinstance(strip_byte_counts, int):
        strip_byte_counts = (strip_byte_counts,)
    if len(strip_offsets) != len(strip_byte_counts):
        raise ValueError(f"Tile {tile.filename} has inconsistent TIFF strip metadata.")

    raw_bytes = bytearray()
    with tile.path.open("rb") as handle:
        for offset, byte_count in zip(strip_offsets, strip_byte_counts, strict=True):
            handle.seek(int(offset))
            compressed = handle.read(int(byte_count))
            if compression in (8, 32946):
                raw_bytes.extend(zlib.decompress(compressed))
            elif compression == 1:
                raw_bytes.extend(compressed)
            else:
                raise ValueError(
                    f"Unsupported TIFF compression {compression} in tile {tile.filename}."
                )

    expected_byte_count = tile.width_px * tile.height_px * 4
    if len(raw_bytes) != expected_byte_count:
        raise ValueError(
            f"Tile {tile.filename} expanded to {len(raw_bytes)} bytes, "
            f"expected {expected_byte_count}."
        )

    with tile.path.open("rb") as handle:
        byte_order_marker = handle.read(2)
    if byte_order_marker == b"MM":
        dtype = ">f4"
    elif byte_order_marker == b"II":
        dtype = "<f4"
    else:
        raise ValueError(f"Unsupported TIFF byte order in tile {tile.filename}.")

    tile_array = np.frombuffer(raw_bytes, dtype=dtype, count=tile.width_px * tile.height_px)
    tile_array = tile_array.reshape(tile.height_px, tile.width_px).astype(np.float32, copy=False)

    expected_shape = (tile.height_px, tile.width_px)
    if tile_array.shape != expected_shape:
        raise ValueError(
            f"Tile {tile.filename} has shape {tile_array.shape}, expected {expected_shape} from manifest."
        )
    return tile_array


def _build_tile_info(dem_dir: Path, tile_payload: Mapping[str, object]) -> TileInfo:
    from PIL import Image
    from shapely.geometry import box

    filename = str(tile_payload["filename"])
    path = dem_dir / "tiles" / filename
    if not path.exists():
        raise FileNotFoundError(f"DEM tile listed in manifest is missing: {path}")

    bbox_projected = tuple(float(value) for value in tile_payload["bbox_projected"])
    west, south, east, north = bbox_projected
    width_px = int(tile_payload["width_px"])
    height_px = int(tile_payload["height_px"])
    x_resolution_m = (east - west) / width_px
    y_resolution_m = (north - south) / height_px
    pixel_area_m2 = x_resolution_m * y_resolution_m

    with Image.open(path) as image:
        nodata_value = _parse_nodata_value(image.tag_v2.get(42113))

    return TileInfo(
        row=int(tile_payload["row"]),
        col=int(tile_payload["col"]),
        filename=filename,
        path=path,
        width_px=width_px,
        height_px=height_px,
        bbox_projected=bbox_projected,
        x_resolution_m=x_resolution_m,
        y_resolution_m=y_resolution_m,
        pixel_area_m2=pixel_area_m2,
        nodata_value=nodata_value,
        geometry_projected=box(west, south, east, north),
    )


def _load_dem_metadata(dem_dir: Path) -> tuple[dict[str, Any], list[TileInfo]]:
    manifest_path = dem_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"DEM manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiles_payload = payload.get("tiles", [])
    if not tiles_payload:
        raise ValueError(f"DEM manifest contains no tiles: {manifest_path}")

    tiles = [_build_tile_info(dem_dir, item) for item in tiles_payload]
    tiles.sort(key=lambda item: (item.row, item.col))
    return payload, tiles


def _compute_window(tile: TileInfo, geometry_bounds: tuple[float, float, float, float]) -> tuple[int, int, int, int] | None:
    west, south, east, north = tile.bbox_projected
    geom_west, geom_south, geom_east, geom_north = geometry_bounds

    clipped_west = max(west, geom_west)
    clipped_south = max(south, geom_south)
    clipped_east = min(east, geom_east)
    clipped_north = min(north, geom_north)
    if clipped_west >= clipped_east or clipped_south >= clipped_north:
        return None

    col_start = max(0, int(math.floor((clipped_west - west) / tile.x_resolution_m)))
    col_end = min(tile.width_px, int(math.ceil((clipped_east - west) / tile.x_resolution_m)))
    row_start = max(0, int(math.floor((north - clipped_north) / tile.y_resolution_m)))
    row_end = min(tile.height_px, int(math.ceil((north - clipped_south) / tile.y_resolution_m)))
    if col_start >= col_end or row_start >= row_end:
        return None

    return row_start, row_end, col_start, col_end


def _sample_tile_window(tile: TileInfo, tile_array: Any, geometry_projected: Any, window: tuple[int, int, int, int]) -> tuple[int, float, float, float | None, float | None]:
    import numpy as np
    from shapely import contains_xy

    row_start, row_end, col_start, col_end = window
    x_coords = tile.bbox_projected[0] + (np.arange(col_start, col_end, dtype=np.float64) + 0.5) * tile.x_resolution_m

    pixel_count = 0
    value_sum = 0.0
    value_sum_sq = 0.0
    value_min: float | None = None
    value_max: float | None = None

    for block_row_start in range(row_start, row_end, ROW_BLOCK_SIZE):
        block_row_end = min(row_end, block_row_start + ROW_BLOCK_SIZE)
        block = tile_array[block_row_start:block_row_end, col_start:col_end]
        if block.size == 0:
            continue

        y_coords = tile.bbox_projected[3] - (
            np.arange(block_row_start, block_row_end, dtype=np.float64) + 0.5
        ) * tile.y_resolution_m
        x_grid, y_grid = np.meshgrid(x_coords, y_coords)
        mask = contains_xy(geometry_projected, x_grid, y_grid)
        mask &= np.isfinite(block)
        if tile.nodata_value is not None:
            mask &= block != tile.nodata_value
        if not mask.any():
            continue

        values = block[mask].astype(np.float64, copy=False)
        pixel_count += int(values.size)
        value_sum += float(values.sum())
        value_sum_sq += float(np.square(values).sum())

        block_min = float(values.min())
        block_max = float(values.max())
        value_min = block_min if value_min is None else min(value_min, block_min)
        value_max = block_max if value_max is None else max(value_max, block_max)

    return pixel_count, value_sum, value_sum_sq, value_min, value_max


def build_obcina_dem_feature_tables(
    *,
    dem_dir: Path = DEFAULT_DEM_DIR,
    geojson_path: Path = DEFAULT_GEOJSON_PATH,
    limit_obcine: int | None = None,
    obcina_sifre: Iterable[str] | None = None,
) -> DemFeatureTables:
    import pandas as pd

    ensure_processing_dependencies()

    municipalities = _load_municipalities(
        geojson_path,
        limit_obcine=limit_obcine,
        obcina_sifre=obcina_sifre,
    )
    dem_manifest, tiles = _load_dem_metadata(dem_dir)

    accumulators = {
        municipality["obcina_sifra"]: MunicipalityAccumulator(
            obcina_sifra=municipality["obcina_sifra"],
            obcina_naziv=municipality["obcina_naziv"],
            eid_obcina=municipality["eid_obcina"],
            ob_mid=municipality["ob_mid"],
            municipality_area_m2=municipality["municipality_area_m2"],
        )
        for municipality in municipalities
    }

    tile_coverage_rows: list[dict[str, Any]] = []
    for tile in tiles:
        tile_array = _load_tile_array(tile)
        for municipality in municipalities:
            geometry_projected = municipality["geometry_projected"]
            if not geometry_projected.intersects(tile.geometry_projected):
                continue

            window = _compute_window(tile, municipality["geometry_bounds"])
            if window is None:
                continue

            pixel_count, value_sum, value_sum_sq, value_min, value_max = _sample_tile_window(
                tile,
                tile_array,
                geometry_projected,
                window,
            )
            if pixel_count <= 0 or value_min is None or value_max is None:
                continue

            row_start, row_end, col_start, col_end = window
            west, south, east, north = tile.bbox_projected
            window_bbox = (
                west + (col_start * tile.x_resolution_m),
                north - (row_end * tile.y_resolution_m),
                west + (col_end * tile.x_resolution_m),
                north - (row_start * tile.y_resolution_m),
            )
            sampled_area_m2 = pixel_count * tile.pixel_area_m2
            tile_coverage_rows.append(
                {
                    "obcina_sifra": municipality["obcina_sifra"],
                    "obcina_naziv": municipality["obcina_naziv"],
                    "tile_filename": tile.filename,
                    "tile_row": tile.row,
                    "tile_col": tile.col,
                    "window_row_start": row_start,
                    "window_row_end": row_end,
                    "window_col_start": col_start,
                    "window_col_end": col_end,
                    "window_bbox_projected_west": window_bbox[0],
                    "window_bbox_projected_south": window_bbox[1],
                    "window_bbox_projected_east": window_bbox[2],
                    "window_bbox_projected_north": window_bbox[3],
                    "tile_pixel_count": pixel_count,
                    "tile_sampled_area_m2": sampled_area_m2,
                    "tile_sampled_area_pct_of_municipality": (
                        sampled_area_m2 / municipality["municipality_area_m2"] * 100.0
                        if municipality["municipality_area_m2"] > 0.0
                        else 0.0
                    ),
                    "tile_pixel_area_m2": tile.pixel_area_m2,
                    "assignment_method": PIXEL_ASSIGNMENT_METHOD,
                }
            )

            accumulator = accumulators[municipality["obcina_sifra"]]
            accumulator.pixel_count += pixel_count
            accumulator.covered_area_m2 += sampled_area_m2
            accumulator.elevation_sum += value_sum
            accumulator.elevation_sum_sq += value_sum_sq
            accumulator.elevation_min = (
                value_min if accumulator.elevation_min is None else min(accumulator.elevation_min, value_min)
            )
            accumulator.elevation_max = (
                value_max if accumulator.elevation_max is None else max(accumulator.elevation_max, value_max)
            )
            accumulator.used_tiles.add(tile.filename)

    municipality_rows = [
        accumulator.to_summary_row(
            dem_instance=str(dem_manifest.get("dem_instance", "")),
            heights=str(dem_manifest.get("heights", "")),
            output_epsg=int(dem_manifest.get("output_epsg", 0)),
            source_resolution_m=float(dem_manifest.get("resolution_m", 0.0)),
        )
        for _, accumulator in sorted(accumulators.items())
    ]

    tile_coverage = pd.DataFrame(tile_coverage_rows).sort_values(
        by=["obcina_sifra", "tile_row", "tile_col"]
    ).reset_index(drop=True)
    municipality_features = pd.DataFrame(municipality_rows).sort_values(
        by=["obcina_sifra"]
    ).reset_index(drop=True)

    if municipality_features.empty:
        raise ValueError("No municipality DEM rows were produced.")

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dem_dir": str(dem_dir.resolve()),
        "geojson_path": str(geojson_path.resolve()),
        "source_manifest_path": str((dem_dir / "manifest.json").resolve()),
        "dem_instance": dem_manifest.get("dem_instance"),
        "dem_heights": dem_manifest.get("heights"),
        "output_epsg": dem_manifest.get("output_epsg"),
        "source_resolution_m": dem_manifest.get("resolution_m"),
        "tile_count": len(tiles),
        "municipality_count": int(len(municipality_features)),
        "limit_obcine": limit_obcine,
        "selected_obcina_sifre": sorted({value.strip() for value in obcina_sifre or [] if value.strip()}),
        "assignment_method": PIXEL_ASSIGNMENT_METHOD,
        "tile_coverage_row_count": int(len(tile_coverage)),
        "municipality_feature_row_count": int(len(municipality_features)),
        "coverage_pct_estimate_min": float(municipality_features["covered_area_pct_estimate"].min()),
        "coverage_pct_estimate_max": float(municipality_features["covered_area_pct_estimate"].max()),
        "feature_columns": [column for column in municipality_features.columns],
    }

    return DemFeatureTables(
        tile_coverage=tile_coverage,
        municipality_features=municipality_features,
        manifest=manifest,
    )


def write_dem_feature_tables(
    tables: DemFeatureTables,
    *,
    tile_coverage_output: Path = DEFAULT_TILE_COVERAGE_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    tile_coverage_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.tile_coverage.to_csv(tile_coverage_output, index=False)
    tables.municipality_features.to_csv(summary_output, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")
