from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_RASTER_PATH = Path(
    "data/raw/copernicus/clms_land_cover_slovenia/"
    "u2018_clc2018_v2020_20u1_raster100m/DATA/U2018_CLC2018_V2020_20u1.tif"
)
DEFAULT_GEOJSON_PATH = Path("data/raw/gurs/obcine-gurs-rpe.geojson")
DEFAULT_COVERAGE_OUTPUT = Path(
    "data/interim/features/copernicus/clms_land_cover_slovenia/obcina_clc_sampling.csv"
)
DEFAULT_SUMMARY_OUTPUT = Path("data/processed/training/obcina_clc_features.csv")
DEFAULT_MANIFEST_OUTPUT = Path("data/processed/training/obcina_clc_features_manifest.json")
OVERLAY_CRS = "EPSG:3035"
PIXEL_ASSIGNMENT_METHOD = "pixel_center_mask"
ROW_BLOCK_SIZE = 512
CLASS_GROUPS = {
    "urban_cover_pct": {111, 112, 121, 122, 123, 124, 131, 132, 133, 141, 142},
    "agricultural_cover_pct": {211, 212, 213, 221, 222, 223, 231, 241, 242, 243, 244},
    "grassland_pasture_cover_pct": {231, 321},
    "forest_cover_pct": {311, 312, 313},
    "broad_leaved_forest_cover_pct": {311},
    "coniferous_forest_cover_pct": {312},
    "mixed_forest_cover_pct": {313},
    "shrub_transitional_cover_pct": {322, 323, 324},
    "open_bare_cover_pct": {331, 332, 333, 334, 335},
    "wetland_cover_pct": {411, 412, 421, 422, 423},
    "water_cover_pct": {511, 512, 521, 522, 523},
}


class ProcessingDependencyError(RuntimeError):
    """Raised when optional processing dependencies are missing."""


@dataclass(frozen=True)
class RasterInfo:
    path: Path
    width_px: int
    height_px: int
    origin_x: float
    origin_y: float
    pixel_width_m: float
    pixel_height_m: float
    pixel_area_m2: float
    nodata_value: int | None


@dataclass(frozen=True)
class RasterCrop:
    array: Any
    row_start: int
    row_end: int
    col_start: int
    col_end: int
    west: float
    south: float
    east: float
    north: float


@dataclass
class MunicipalityAccumulator:
    obcina_sifra: str
    obcina_naziv: str
    eid_obcina: str
    ob_mid: str
    municipality_area_m2: float
    pixel_count: int = 0
    covered_area_m2: float = 0.0
    code_counts: dict[int, int] = field(default_factory=dict)

    def update(self, counts_by_code: Mapping[int, int], *, pixel_area_m2: float) -> None:
        total_count = 0
        for code, count in counts_by_code.items():
            if count <= 0:
                continue
            self.code_counts[code] = self.code_counts.get(code, 0) + int(count)
            total_count += int(count)

        self.pixel_count += total_count
        self.covered_area_m2 += total_count * pixel_area_m2

    def to_summary_row(
        self,
        *,
        source_resolution_m: float,
        label_by_code: Mapping[int, str],
    ) -> dict[str, Any]:
        if self.pixel_count <= 0:
            raise ValueError(
                f"No CLC pixels were assigned to municipality {self.obcina_sifra} {self.obcina_naziv}."
            )

        covered_area_pct = (
            (self.covered_area_m2 / self.municipality_area_m2) * 100.0
            if self.municipality_area_m2 > 0.0
            else 0.0
        )
        dominant_code, dominant_count = max(
            sorted(self.code_counts.items()),
            key=lambda item: item[1],
        )
        dominant_pct = (dominant_count / self.pixel_count) * 100.0

        row = {
            "obcina_sifra": self.obcina_sifra,
            "obcina_naziv": self.obcina_naziv,
            "eid_obcina": self.eid_obcina,
            "ob_mid": self.ob_mid,
            "municipality_area_m2": self.municipality_area_m2,
            "covered_area_m2": self.covered_area_m2,
            "covered_area_pct_estimate": covered_area_pct,
            "pixel_count": self.pixel_count,
            "assignment_method": PIXEL_ASSIGNMENT_METHOD,
            "source_resolution_m": source_resolution_m,
            "dominant_clc_code": dominant_code,
            "dominant_clc_label": label_by_code.get(dominant_code, ""),
            "dominant_clc_cover_pct": dominant_pct,
        }
        for column_name, codes in CLASS_GROUPS.items():
            count = sum(self.code_counts.get(code, 0) for code in codes)
            row[column_name] = (count / self.pixel_count) * 100.0
        return row


@dataclass(frozen=True)
class ClcFeatureTables:
    sampling: Any
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


def _parse_nodata_value(raw_value: object) -> int | None:
    if raw_value in (None, ""):
        return None
    raw_text = str(raw_value).strip().strip("\x00")
    if not raw_text:
        return None
    try:
        return int(float(raw_text)) % 256
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


def _parse_world_file(world_file_path: Path) -> tuple[float, float, float, float]:
    if not world_file_path.exists():
        raise FileNotFoundError(f"World file not found: {world_file_path}")

    values = [float(line.strip()) for line in world_file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(values) != 6:
        raise ValueError(f"World file must contain 6 values: {world_file_path}")

    pixel_width, rotation_x, rotation_y, pixel_height_signed, center_x, center_y = values
    if not math.isclose(rotation_x, 0.0, abs_tol=1e-9) or not math.isclose(rotation_y, 0.0, abs_tol=1e-9):
        raise ValueError(f"Rotated world files are not supported: {world_file_path}")

    pixel_height = abs(pixel_height_signed)
    origin_x = center_x - (pixel_width / 2.0)
    origin_y = center_y + (pixel_height / 2.0)
    return origin_x, origin_y, pixel_width, pixel_height


def _load_raster_info(raster_path: Path) -> RasterInfo:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None

    world_file_path = raster_path.with_suffix(".tfw")
    with Image.open(raster_path) as image:
        width_px, height_px = image.size
        scale = image.tag_v2.get(33550)
        tiepoint = image.tag_v2.get(33922)
        nodata_value = _parse_nodata_value(image.tag_v2.get(42113))

    if scale and tiepoint:
        pixel_width = float(scale[0])
        pixel_height = float(scale[1])
        raster_i = float(tiepoint[0])
        raster_j = float(tiepoint[1])
        model_x = float(tiepoint[3])
        model_y = float(tiepoint[4])
        origin_x = model_x - (raster_i * pixel_width)
        origin_y = model_y + (raster_j * pixel_height)
    else:
        origin_x, origin_y, pixel_width, pixel_height = _parse_world_file(world_file_path)

    return RasterInfo(
        path=raster_path,
        width_px=width_px,
        height_px=height_px,
        origin_x=origin_x,
        origin_y=origin_y,
        pixel_width_m=pixel_width,
        pixel_height_m=pixel_height,
        pixel_area_m2=pixel_width * pixel_height,
        nodata_value=nodata_value,
    )


def _parse_dbf_records(dbf_path: Path) -> list[dict[str, str]]:
    payload = dbf_path.read_bytes()
    _, _, _, _, record_count, header_length, record_length = struct.unpack("<BBBBIHH20x", payload[:32])

    fields: list[tuple[str, str, int]] = []
    offset = 32
    while payload[offset] != 0x0D:
        name = payload[offset : offset + 11].split(b"\x00", 1)[0].decode("ascii")
        field_type = chr(payload[offset + 11])
        field_length = payload[offset + 16]
        fields.append((name, field_type, field_length))
        offset += 32

    records: list[dict[str, str]] = []
    for index in range(record_count):
        start = header_length + (index * record_length)
        end = start + record_length
        record = payload[start:end]
        if not record or record[:1] == b"*":
            continue

        values: dict[str, str] = {}
        position = 1
        for name, _, field_length in fields:
            raw_value = record[position : position + field_length]
            values[name] = raw_value.decode("cp1252", errors="ignore").strip()
            position += field_length
        records.append(values)

    return records


def _load_vat_mapping(raster_path: Path) -> tuple[list[int], dict[int, str]]:
    vat_path = raster_path.with_name(raster_path.name + ".vat.dbf")
    if not vat_path.exists():
        raise FileNotFoundError(f"CLC VAT DBF not found: {vat_path}")

    value_to_code = [0] * 256
    label_by_code: dict[int, str] = {}
    for record in _parse_dbf_records(vat_path):
        value_text = record.get("Value", "")
        code_text = record.get("CODE_18", "")
        label_text = record.get("LABEL3", "")
        if not value_text or not code_text:
            continue

        value = int(float(value_text)) % 256
        code = int(code_text)
        value_to_code[value] = code
        label_by_code[code] = label_text

    if not any(value_to_code):
        raise ValueError(f"CLC VAT DBF contained no code mapping: {vat_path}")

    return value_to_code, label_by_code


def _compute_raster_window(
    raster_info: RasterInfo,
    geometry_bounds: tuple[float, float, float, float],
) -> tuple[int, int, int, int] | None:
    geom_west, geom_south, geom_east, geom_north = geometry_bounds
    raster_west = raster_info.origin_x
    raster_east = raster_info.origin_x + (raster_info.width_px * raster_info.pixel_width_m)
    raster_north = raster_info.origin_y
    raster_south = raster_info.origin_y - (raster_info.height_px * raster_info.pixel_height_m)

    clipped_west = max(raster_west, geom_west)
    clipped_south = max(raster_south, geom_south)
    clipped_east = min(raster_east, geom_east)
    clipped_north = min(raster_north, geom_north)
    if clipped_west >= clipped_east or clipped_south >= clipped_north:
        return None

    col_start = max(0, int(math.floor((clipped_west - raster_info.origin_x) / raster_info.pixel_width_m)))
    col_end = min(
        raster_info.width_px,
        int(math.ceil((clipped_east - raster_info.origin_x) / raster_info.pixel_width_m)),
    )
    row_start = max(0, int(math.floor((raster_info.origin_y - clipped_north) / raster_info.pixel_height_m)))
    row_end = min(
        raster_info.height_px,
        int(math.ceil((raster_info.origin_y - clipped_south) / raster_info.pixel_height_m)),
    )
    if col_start >= col_end or row_start >= row_end:
        return None

    return row_start, row_end, col_start, col_end


def _load_raster_crop(raster_info: RasterInfo, municipalities: list[dict[str, Any]]) -> RasterCrop:
    import numpy as np
    from PIL import Image

    overall_bounds = (
        min(item["geometry_bounds"][0] for item in municipalities),
        min(item["geometry_bounds"][1] for item in municipalities),
        max(item["geometry_bounds"][2] for item in municipalities),
        max(item["geometry_bounds"][3] for item in municipalities),
    )
    window = _compute_raster_window(raster_info, overall_bounds)
    if window is None:
        raise ValueError("Municipality bounds do not intersect the CLC raster.")

    row_start, row_end, col_start, col_end = window
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(raster_info.path) as image:
        array = np.array(image.crop((col_start, row_start, col_end, row_end)), dtype=np.uint8)

    west = raster_info.origin_x + (col_start * raster_info.pixel_width_m)
    east = raster_info.origin_x + (col_end * raster_info.pixel_width_m)
    north = raster_info.origin_y - (row_start * raster_info.pixel_height_m)
    south = raster_info.origin_y - (row_end * raster_info.pixel_height_m)

    return RasterCrop(
        array=array,
        row_start=row_start,
        row_end=row_end,
        col_start=col_start,
        col_end=col_end,
        west=west,
        south=south,
        east=east,
        north=north,
    )


def _sample_crop_window(
    raster_crop: RasterCrop,
    raster_info: RasterInfo,
    geometry_projected: Any,
    window: tuple[int, int, int, int],
    value_to_code: list[int],
) -> tuple[dict[int, int], int]:
    import numpy as np
    from shapely import contains_xy

    row_start, row_end, col_start, col_end = window
    x_coords = raster_crop.west + (
        np.arange(col_start, col_end, dtype=np.float64) + 0.5
    ) * raster_info.pixel_width_m

    code_counts: dict[int, int] = {}
    valid_count = 0
    for block_row_start in range(row_start, row_end, ROW_BLOCK_SIZE):
        block_row_end = min(row_end, block_row_start + ROW_BLOCK_SIZE)
        block = raster_crop.array[block_row_start:block_row_end, col_start:col_end]
        if block.size == 0:
            continue

        y_coords = raster_crop.north - (
            np.arange(block_row_start, block_row_end, dtype=np.float64) + 0.5
        ) * raster_info.pixel_height_m
        x_grid, y_grid = np.meshgrid(x_coords, y_coords)
        mask = contains_xy(geometry_projected, x_grid, y_grid)
        if raster_info.nodata_value is not None:
            mask &= block != raster_info.nodata_value
        if not mask.any():
            continue

        values = block[mask]
        if values.size == 0:
            continue

        bincount = np.bincount(values, minlength=256)
        for value, count in enumerate(bincount.tolist()):
            if count <= 0:
                continue
            code = value_to_code[value]
            if code <= 0:
                continue
            code_counts[code] = code_counts.get(code, 0) + int(count)
            valid_count += int(count)

    return code_counts, valid_count


def build_obcina_clc_feature_tables(
    *,
    raster_path: Path = DEFAULT_RASTER_PATH,
    geojson_path: Path = DEFAULT_GEOJSON_PATH,
    limit_obcine: int | None = None,
    obcina_sifre: Iterable[str] | None = None,
) -> ClcFeatureTables:
    import pandas as pd

    ensure_processing_dependencies()

    municipalities = _load_municipalities(
        geojson_path,
        limit_obcine=limit_obcine,
        obcina_sifre=obcina_sifre,
    )
    raster_info = _load_raster_info(raster_path)
    value_to_code, label_by_code = _load_vat_mapping(raster_path)
    raster_crop = _load_raster_crop(raster_info, municipalities)

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

    sampling_rows: list[dict[str, Any]] = []
    for municipality in municipalities:
        geometry_projected = municipality["geometry_projected"]
        geometry_bounds = municipality["geometry_bounds"]

        crop_window = _compute_raster_window(
            RasterInfo(
                path=raster_info.path,
                width_px=raster_crop.array.shape[1],
                height_px=raster_crop.array.shape[0],
                origin_x=raster_crop.west,
                origin_y=raster_crop.north,
                pixel_width_m=raster_info.pixel_width_m,
                pixel_height_m=raster_info.pixel_height_m,
                pixel_area_m2=raster_info.pixel_area_m2,
                nodata_value=raster_info.nodata_value,
            ),
            geometry_bounds,
        )
        if crop_window is None:
            continue

        code_counts, valid_count = _sample_crop_window(
            raster_crop,
            raster_info,
            geometry_projected,
            crop_window,
            value_to_code,
        )
        if valid_count <= 0:
            continue

        row_start, row_end, col_start, col_end = crop_window
        window_west = raster_crop.west + (col_start * raster_info.pixel_width_m)
        window_east = raster_crop.west + (col_end * raster_info.pixel_width_m)
        window_north = raster_crop.north - (row_start * raster_info.pixel_height_m)
        window_south = raster_crop.north - (row_end * raster_info.pixel_height_m)
        sampled_area_m2 = valid_count * raster_info.pixel_area_m2
        dominant_code, dominant_count = max(
            sorted(code_counts.items()),
            key=lambda item: item[1],
        )
        sampling_rows.append(
            {
                "obcina_sifra": municipality["obcina_sifra"],
                "obcina_naziv": municipality["obcina_naziv"],
                "window_row_start": row_start,
                "window_row_end": row_end,
                "window_col_start": col_start,
                "window_col_end": col_end,
                "window_bbox_projected_west": window_west,
                "window_bbox_projected_south": window_south,
                "window_bbox_projected_east": window_east,
                "window_bbox_projected_north": window_north,
                "pixel_count": valid_count,
                "sampled_area_m2": sampled_area_m2,
                "sampled_area_pct_of_municipality": (
                    sampled_area_m2 / municipality["municipality_area_m2"] * 100.0
                    if municipality["municipality_area_m2"] > 0.0
                    else 0.0
                ),
                "pixel_area_m2": raster_info.pixel_area_m2,
                "assignment_method": PIXEL_ASSIGNMENT_METHOD,
                "dominant_clc_code": dominant_code,
                "dominant_clc_label": label_by_code.get(dominant_code, ""),
                "dominant_clc_cover_pct": (dominant_count / valid_count) * 100.0,
            }
        )
        accumulators[municipality["obcina_sifra"]].update(
            code_counts,
            pixel_area_m2=raster_info.pixel_area_m2,
        )

    municipality_rows = [
        accumulator.to_summary_row(
            source_resolution_m=raster_info.pixel_width_m,
            label_by_code=label_by_code,
        )
        for _, accumulator in sorted(accumulators.items())
        if accumulator.pixel_count > 0
    ]
    if not municipality_rows:
        raise ValueError("No municipality CLC rows were produced.")

    sampling = pd.DataFrame(sampling_rows).sort_values(by=["obcina_sifra"]).reset_index(drop=True)
    municipality_features = pd.DataFrame(municipality_rows).sort_values(
        by=["obcina_sifra"]
    ).reset_index(drop=True)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raster_path": str(raster_path.resolve()),
        "vat_path": str(raster_path.with_name(raster_path.name + ".vat.dbf").resolve()),
        "geojson_path": str(geojson_path.resolve()),
        "output_epsg": 3035,
        "source_resolution_m": raster_info.pixel_width_m,
        "raster_width_px": raster_info.width_px,
        "raster_height_px": raster_info.height_px,
        "crop_row_start": raster_crop.row_start,
        "crop_row_end": raster_crop.row_end,
        "crop_col_start": raster_crop.col_start,
        "crop_col_end": raster_crop.col_end,
        "crop_width_px": int(raster_crop.array.shape[1]),
        "crop_height_px": int(raster_crop.array.shape[0]),
        "nodata_value": raster_info.nodata_value,
        "municipality_count": int(len(municipality_features)),
        "limit_obcine": limit_obcine,
        "selected_obcina_sifre": sorted({value.strip() for value in obcina_sifre or [] if value.strip()}),
        "assignment_method": PIXEL_ASSIGNMENT_METHOD,
        "sampling_row_count": int(len(sampling)),
        "municipality_feature_row_count": int(len(municipality_features)),
        "coverage_pct_estimate_min": float(municipality_features["covered_area_pct_estimate"].min()),
        "coverage_pct_estimate_max": float(municipality_features["covered_area_pct_estimate"].max()),
        "feature_columns": [column for column in municipality_features.columns],
        "class_group_columns": sorted(CLASS_GROUPS),
    }

    return ClcFeatureTables(
        sampling=sampling,
        municipality_features=municipality_features,
        manifest=manifest,
    )


def write_clc_feature_tables(
    tables: ClcFeatureTables,
    *,
    sampling_output: Path = DEFAULT_COVERAGE_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> None:
    sampling_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    tables.sampling.to_csv(sampling_output, index=False)
    tables.municipality_features.to_csv(summary_output, index=False)
    manifest_output.write_text(json.dumps(tables.manifest, indent=2, ensure_ascii=True) + "\n")
