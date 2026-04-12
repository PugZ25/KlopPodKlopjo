from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "data" / "raw" / "gurs" / "obcine-gurs-rpe.geojson"
DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "public" / "municipality-boundaries.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a simplified municipality boundary asset for browser-side "
            "geolocation lookup in the hackathon frontend."
        )
    )
    parser.add_argument(
        "--source-path",
        default=str(DEFAULT_SOURCE),
        help="Input GURS municipality GeoJSON path.",
    )
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path for the frontend boundary asset.",
    )
    parser.add_argument(
        "--simplify-tolerance",
        type=float,
        default=0.0004,
        help="Geometry simplify tolerance in WGS84 degrees.",
    )
    parser.add_argument(
        "--round-decimals",
        type=int,
        default=5,
        help="Coordinate rounding precision.",
    )
    return parser


def build_boundary_asset(
    *,
    source_path: Path,
    simplify_tolerance: float,
    round_decimals: int,
) -> list[dict[str, Any]]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    if not features:
        raise ValueError(f"No GeoJSON features found in {source_path}.")

    boundaries: list[dict[str, Any]] = []
    for feature in features:
        properties = feature.get("properties", {})
        municipality_code = str(properties.get("SIFRA", "")).strip()
        municipality_name = str(properties.get("NAZIV", "")).strip()
        if not municipality_code or not municipality_name:
            raise ValueError("Boundary feature is missing SIFRA or NAZIV.")

        geometry = shape(feature["geometry"]).simplify(
            simplify_tolerance,
            preserve_topology=True,
        )
        ring = [
            [round(float(longitude), round_decimals), round(float(latitude), round_decimals)]
            for longitude, latitude in geometry.exterior.coords
        ]
        longitudes = [point[0] for point in ring]
        latitudes = [point[1] for point in ring]
        boundaries.append(
            {
                "code": municipality_code,
                "name": municipality_name,
                "bbox": [
                    min(longitudes),
                    min(latitudes),
                    max(longitudes),
                    max(latitudes),
                ],
                "ring": ring,
            }
        )

    boundaries.sort(key=lambda boundary: (int(boundary["code"]), boundary["name"]))
    return boundaries


def write_boundary_asset(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    source_path = Path(args.source_path)
    output_path = Path(args.output_path)

    payload = build_boundary_asset(
        source_path=source_path,
        simplify_tolerance=args.simplify_tolerance,
        round_decimals=args.round_decimals,
    )
    write_boundary_asset(output_path, payload)
    print(f"Municipality boundary asset written to {output_path.resolve()}")
    print(f"- municipalities: {len(payload)}")
    print(f"- simplify_tolerance: {args.simplify_tolerance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
