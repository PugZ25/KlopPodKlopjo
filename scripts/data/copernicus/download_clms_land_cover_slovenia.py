#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from urllib import error, parse, request


TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_API_URL = "https://sh.dataspace.copernicus.eu/process/v1"
DEFAULT_BBOX = [46.9, 13.3, 45.3, 16.6]  # north, west, south, east
DEFAULT_OUTPUT_EPSG = 3794  # D96 / TM
DEFAULT_RESOLUTION_M = 100.0
DEFAULT_MAX_TILE_SIZE = 2400
DEFAULT_YEAR = 2019
SUPPORTED_YEARS = tuple(range(2015, 2020))
COLLECTION_ID = "35fecfec-8a73-4723-bb08-b775f283a535"
DATA_TYPE = f"byoc-{COLLECTION_ID}"
RESAMPLING_METHODS = ("NEAREST", "BILINEAR", "BICUBIC")
DEFAULT_OUTPUT_DIR = Path("data/raw/copernicus/clms_land_cover_slovenia")
DEFAULT_TILE_DIRNAME = "tiles"

# Fractional-cover bands keep the raw percentages, while the class bands preserve
# the original product coding for later municipality-level aggregation.
BAND_SPECS: list[tuple[str, str, str]] = [
    ("Tree_Cover_Fraction", "tree_cover_fraction_pct", "Tree cover fraction"),
    ("Grass_Cover_Fraction", "grass_cover_fraction_pct", "Grass cover fraction"),
    ("Shrub_Cover_Fraction", "shrub_cover_fraction_pct", "Shrub cover fraction"),
    ("Crops_Cover_Fraction", "crops_cover_fraction_pct", "Crops cover fraction"),
    ("Forest_Type", "forest_type", "Forest type class"),
    ("Discrete_Classification", "discrete_classification", "Discrete land-cover class"),
]

EVALSCRIPT = f"""
//VERSION=3
function setup() {{
  return {{
    input: [{", ".join(json.dumps(spec[0]) for spec in BAND_SPECS)}],
    output: {{
      id: "default",
      bands: {len(BAND_SPECS)},
      sampleType: SampleType.UINT8,
    }},
  }};
}}

function evaluatePixel(sample) {{
  return [{", ".join(f"sample.{spec[0]}" for spec in BAND_SPECS)}];
}}
""".strip()


@dataclass(frozen=True)
class TilePlan:
    row: int
    col: int
    width_px: int
    height_px: int
    bbox_projected: list[float]
    bbox_wgs84: list[float]
    filename: str

    def to_manifest_dict(self) -> dict[str, object]:
        return {
            "row": self.row,
            "col": self.col,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "bbox_projected": self.bbox_projected,
            "bbox_wgs84": self.bbox_wgs84,
            "filename": self.filename,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download raw CLMS global land-cover fractional cover GeoTIFF tiles "
            "for Slovenia through the Copernicus Data Space Sentinel Hub Process API."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
        help=(
            "Product year to request. Officially supported in this product: "
            f"{SUPPORTED_YEARS[0]}-{SUPPORTED_YEARS[-1]}. Default: {DEFAULT_YEAR}."
        ),
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        metavar=("NORTH", "WEST", "SOUTH", "EAST"),
        type=float,
        default=DEFAULT_BBOX,
        help="Bounding box in WGS84 with ERA5/CDS ordering: north west south east.",
    )
    parser.add_argument(
        "--output-epsg",
        type=int,
        default=DEFAULT_OUTPUT_EPSG,
        help=f"Projected CRS used for the output GeoTIFFs. Default: EPSG:{DEFAULT_OUTPUT_EPSG}.",
    )
    parser.add_argument(
        "--resolution-m",
        type=float,
        default=DEFAULT_RESOLUTION_M,
        help=f"Requested output resolution in metres. Default: {DEFAULT_RESOLUTION_M:g}.",
    )
    parser.add_argument(
        "--max-tile-size",
        type=int,
        default=DEFAULT_MAX_TILE_SIZE,
        help=(
            "Maximum output width/height per request in pixels. The synchronous "
            f"Process API limit is 2500; default keeps a margin at {DEFAULT_MAX_TILE_SIZE}."
        ),
    )
    parser.add_argument(
        "--upsampling",
        choices=RESAMPLING_METHODS,
        default="NEAREST",
        help="Upsampling mode sent to Process API. Default: NEAREST.",
    )
    parser.add_argument(
        "--downsampling",
        choices=RESAMPLING_METHODS,
        default="NEAREST",
        help="Downsampling mode sent to Process API. Default: NEAREST.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Destination directory for GeoTIFF tiles and manifest.",
    )
    parser.add_argument(
        "--build-vrt",
        action="store_true",
        help="Build a VRT mosaic with gdalbuildvrt if the command is available.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download tile files even when they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned tile layout without requesting data.",
    )
    return parser


def ensure_pyproj() -> None:
    try:
        from pyproj import Transformer  # noqa: F401
    except ImportError as exc:
        module_name = exc.name or "pyproj"
        print(
            "Missing dependency: "
            f"{module_name}. Install with:\n"
            "python3 -m pip install -r scripts/data/copernicus/requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def resolve_access_token() -> str:
    access_token = os.getenv("CDSE_ACCESS_TOKEN")
    if access_token:
        return access_token

    client_id = os.getenv("CDSE_CLIENT_ID")
    client_secret = os.getenv("CDSE_CLIENT_SECRET")
    if client_id and client_secret:
        try:
            return fetch_access_token(client_id, client_secret)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

    print(
        "Missing Copernicus Data Space credentials.\n"
        "Before running this script, export either:\n"
        "  export CDSE_ACCESS_TOKEN='<your bearer token>'\n"
        "or:\n"
        "  export CDSE_CLIENT_ID='<your client id>'\n"
        "  export CDSE_CLIENT_SECRET='<your client secret>'",
        file=sys.stderr,
    )
    raise SystemExit(1)


def validate_year(year: int) -> int:
    if year not in SUPPORTED_YEARS:
        supported = ", ".join(str(value) for value in SUPPORTED_YEARS)
        raise ValueError(
            f"Unsupported year {year}. This CLMS land-cover product supports: {supported}."
        )
    return year


def bbox_to_wgs84_xy(bbox: list[float]) -> tuple[float, float, float, float]:
    north, west, south, east = bbox
    if south >= north:
        raise ValueError("Invalid bbox: SOUTH must be smaller than NORTH.")
    if west >= east:
        raise ValueError("Invalid bbox: WEST must be smaller than EAST.")
    return west, south, east, north


def build_transformers(output_epsg: int):
    from pyproj import Transformer

    forward = Transformer.from_crs("EPSG:4326", f"EPSG:{output_epsg}", always_xy=True)
    inverse = Transformer.from_crs(f"EPSG:{output_epsg}", "EPSG:4326", always_xy=True)
    return forward, inverse


def project_bbox(wgs84_bbox: tuple[float, float, float, float], output_epsg: int) -> list[float]:
    forward, _ = build_transformers(output_epsg)
    west, south, east, north = wgs84_bbox
    corners = [
        (west, south),
        (west, north),
        (east, south),
        (east, north),
    ]
    projected = [forward.transform(lon, lat) for lon, lat in corners]
    xs = [point[0] for point in projected]
    ys = [point[1] for point in projected]
    return [min(xs), min(ys), max(xs), max(ys)]


def back_project_bbox(projected_bbox: list[float], output_epsg: int) -> list[float]:
    _, inverse = build_transformers(output_epsg)
    west, south, east, north = projected_bbox
    corners = [
        (west, south),
        (west, north),
        (east, south),
        (east, north),
    ]
    transformed = [inverse.transform(x, y) for x, y in corners]
    xs = [point[0] for point in transformed]
    ys = [point[1] for point in transformed]
    return [min(xs), min(ys), max(xs), max(ys)]


def build_base_name(year: int, resolution_m: float) -> str:
    resolution_label = f"{int(resolution_m)}m" if resolution_m.is_integer() else f"{resolution_m:g}m"
    return f"clms_land_cover_slovenia_v3_{year}_{resolution_label}"


def build_tile_plan(
    projected_bbox: list[float],
    output_epsg: int,
    resolution_m: float,
    max_tile_size: int,
    base_name: str,
) -> list[TilePlan]:
    west, south, east, north = projected_bbox
    total_width_px = ceil((east - west) / resolution_m)
    total_height_px = ceil((north - south) / resolution_m)

    tiles: list[TilePlan] = []
    rows = ceil(total_height_px / max_tile_size)
    cols = ceil(total_width_px / max_tile_size)

    for row in range(rows):
        y_start_px = row * max_tile_size
        y_end_px = min(total_height_px, (row + 1) * max_tile_size)
        tile_north = north - (y_start_px * resolution_m)
        tile_south = max(south, north - (y_end_px * resolution_m))
        tile_height_px = y_end_px - y_start_px

        for col in range(cols):
            x_start_px = col * max_tile_size
            x_end_px = min(total_width_px, (col + 1) * max_tile_size)
            tile_west = west + (x_start_px * resolution_m)
            tile_east = min(east, west + (x_end_px * resolution_m))
            tile_width_px = x_end_px - x_start_px

            projected_tile_bbox = [tile_west, tile_south, tile_east, tile_north]
            wgs84_tile_bbox = back_project_bbox(projected_tile_bbox, output_epsg)
            filename = f"{base_name}_r{row + 1:02d}_c{col + 1:02d}.tif"
            tiles.append(
                TilePlan(
                    row=row + 1,
                    col=col + 1,
                    width_px=tile_width_px,
                    height_px=tile_height_px,
                    bbox_projected=projected_tile_bbox,
                    bbox_wgs84=wgs84_tile_bbox,
                    filename=filename,
                )
            )

    return tiles


def fetch_access_token(client_id: str, client_secret: str) -> str:
    payload = parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    request_obj = request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(request_obj) as response:
            data = json.load(response)
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token request failed with HTTP {exc.code}: {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Token request failed: {exc}") from exc

    token = data.get("access_token")
    if not token:
        raise RuntimeError("Token endpoint response did not include an access_token.")
    return token


def build_process_request(
    tile: TilePlan,
    *,
    year: int,
    output_epsg: int,
    upsampling: str,
    downsampling: str,
) -> dict[str, object]:
    return {
        "input": {
            "bounds": {
                "bbox": tile.bbox_projected,
                "properties": {
                    "crs": f"http://www.opengis.net/def/crs/EPSG/0/{output_epsg}"
                },
            },
            "data": [
                {
                    "type": DATA_TYPE,
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{year}-01-01T00:00:00Z",
                            "to": f"{year}-12-31T23:59:59Z",
                        }
                    },
                    "processing": {
                        "upsampling": upsampling,
                        "downsampling": downsampling,
                    },
                }
            ],
        },
        "output": {
            "width": tile.width_px,
            "height": tile.height_px,
            "responses": [
                {
                    "identifier": "default",
                    "format": {"type": "image/tiff"},
                }
            ],
        },
        "evalscript": EVALSCRIPT,
    }


def download_tile(token: str, payload: dict[str, object], destination: Path) -> None:
    request_obj = request.Request(
        PROCESS_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(request_obj) as response:
            content = response.read()
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Land-cover download failed for {destination.name} with HTTP {exc.code}: {message}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Land-cover download failed for {destination.name}: {exc}") from exc

    destination.write_bytes(content)


def maybe_build_vrt(tiles_dir: Path, vrt_path: Path) -> tuple[bool, str | None]:
    gdalbuildvrt = shutil.which("gdalbuildvrt")
    if gdalbuildvrt is None:
        return False, "gdalbuildvrt command is not available"

    tile_paths = sorted(str(path) for path in tiles_dir.glob("*.tif"))
    if not tile_paths:
        return False, "no tile GeoTIFF files available"

    result = subprocess.run(
        [gdalbuildvrt, str(vrt_path), *tile_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return False, stderr
    return True, None


def write_manifest(
    manifest_path: Path,
    *,
    year: int,
    output_epsg: int,
    resolution_m: float,
    max_tile_size: int,
    bbox_input: list[float],
    bbox_projected: list[float],
    bbox_projected_wgs84: list[float],
    output_dir: Path,
    tiles_dir: Path,
    base_name: str,
    upsampling: str,
    downsampling: str,
    downloaded_tiles: list[TilePlan],
    skipped_tiles: list[TilePlan],
    vrt_filename: str | None,
    vrt_status: str | None,
) -> None:
    manifest = {
        "dataset": "CLMS global land cover 100 m yearly v3",
        "dataset_access": "Copernicus Data Space Sentinel Hub Process API",
        "source_urls": {
            "collection_docs": (
                "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/"
                "clms/land-cover-and-land-use-mapping/global-dynamic-land-cover/"
                "lc_global_100m_yearly_v3.html"
            ),
            "browser": "https://browser.dataspace.copernicus.eu/",
            "auth_docs": (
                "https://documentation.dataspace.copernicus.eu/APIs/"
                "SentinelHub/Overview/Authentication.html"
            ),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "collection_id": COLLECTION_ID,
        "data_type": DATA_TYPE,
        "year": year,
        "resolution_m": resolution_m,
        "output_epsg": output_epsg,
        "max_tile_size_px": max_tile_size,
        "bbox_input_nwse": bbox_input,
        "bbox_projected": bbox_projected,
        "bbox_projected_wgs84": bbox_projected_wgs84,
        "output_dir": str(output_dir),
        "tiles_dir": str(tiles_dir),
        "base_name": base_name,
        "upsampling": upsampling,
        "downsampling": downsampling,
        "bands": [
            {"source_band": source_band, "output_band": output_band, "description": description}
            for source_band, output_band, description in BAND_SPECS
        ],
        "downloaded_tile_count": len(downloaded_tiles),
        "skipped_tile_count": len(skipped_tiles),
        "tiles": [tile.to_manifest_dict() for tile in downloaded_tiles + skipped_tiles],
        "vrt_filename": vrt_filename,
        "vrt_status": vrt_status,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def print_plan(*, year: int, resolution_m: float, output_epsg: int, base_name: str, tiles: list[TilePlan]) -> None:
    print(f"Dataset year: {year}")
    print(f"Resolution: {resolution_m:g} m")
    print(f"Output CRS: EPSG:{output_epsg}")
    print(f"Collection ID: {COLLECTION_ID}")
    print(f"Base name: {base_name}")
    print(f"Output bands: {', '.join(spec[1] for spec in BAND_SPECS)}")
    print(f"Planned tiles: {len(tiles)}")
    for tile in tiles:
        west, south, east, north = tile.bbox_projected
        print(
            f"- r{tile.row:02d} c{tile.col:02d}: "
            f"{tile.width_px}x{tile.height_px}px, "
            f"projected bbox=({west:.2f}, {south:.2f}, {east:.2f}, {north:.2f}), "
            f"file={tile.filename}"
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ensure_pyproj()

    try:
        year = validate_year(args.year)
        bbox_wgs84 = bbox_to_wgs84_xy(args.bbox)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.resolution_m <= 0:
        print("resolution-m must be greater than zero.", file=sys.stderr)
        return 2
    if args.max_tile_size <= 0 or args.max_tile_size > 2500:
        print("max-tile-size must be in the range 1..2500.", file=sys.stderr)
        return 2

    projected_bbox = project_bbox(bbox_wgs84, args.output_epsg)
    projected_bbox_wgs84 = back_project_bbox(projected_bbox, args.output_epsg)
    base_name = build_base_name(year, float(args.resolution_m))
    tiles = build_tile_plan(
        projected_bbox=projected_bbox,
        output_epsg=args.output_epsg,
        resolution_m=float(args.resolution_m),
        max_tile_size=args.max_tile_size,
        base_name=base_name,
    )

    print_plan(
        year=year,
        resolution_m=float(args.resolution_m),
        output_epsg=args.output_epsg,
        base_name=base_name,
        tiles=tiles,
    )
    if args.dry_run:
        return 0

    token = resolve_access_token()
    output_dir = Path(args.output_dir)
    tiles_dir = output_dir / DEFAULT_TILE_DIRNAME
    manifest_path = output_dir / "manifest.json"
    vrt_path = output_dir / f"{base_name}.vrt"

    output_dir.mkdir(parents=True, exist_ok=True)
    tiles_dir.mkdir(parents=True, exist_ok=True)

    downloaded_tiles: list[TilePlan] = []
    skipped_tiles: list[TilePlan] = []

    for tile in tiles:
        destination = tiles_dir / tile.filename
        if destination.exists() and not args.force:
            print(f"Skipping existing tile: {destination.name}")
            skipped_tiles.append(tile)
            continue

        print(f"Downloading tile r{tile.row:02d} c{tile.col:02d} -> {destination.name}")
        payload = build_process_request(
            tile,
            year=year,
            output_epsg=args.output_epsg,
            upsampling=args.upsampling,
            downsampling=args.downsampling,
        )
        try:
            download_tile(token, payload, destination)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        downloaded_tiles.append(tile)

    vrt_filename: str | None = None
    vrt_status: str | None = None
    if args.build_vrt:
        success, message = maybe_build_vrt(tiles_dir, vrt_path)
        vrt_filename = vrt_path.name if success else None
        vrt_status = "built" if success else message

    write_manifest(
        manifest_path,
        year=year,
        output_epsg=args.output_epsg,
        resolution_m=float(args.resolution_m),
        max_tile_size=args.max_tile_size,
        bbox_input=args.bbox,
        bbox_projected=projected_bbox,
        bbox_projected_wgs84=projected_bbox_wgs84,
        output_dir=output_dir,
        tiles_dir=tiles_dir,
        base_name=base_name,
        upsampling=args.upsampling,
        downsampling=args.downsampling,
        downloaded_tiles=downloaded_tiles,
        skipped_tiles=skipped_tiles,
        vrt_filename=vrt_filename,
        vrt_status=vrt_status,
    )

    print("CLMS land-cover download completed.")
    print(f"- downloaded tiles: {len(downloaded_tiles)}")
    print(f"- skipped tiles: {len(skipped_tiles)}")
    print(f"- manifest: {manifest_path.resolve()}")
    if args.build_vrt:
        print(f"- vrt status: {vrt_status or 'built'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
