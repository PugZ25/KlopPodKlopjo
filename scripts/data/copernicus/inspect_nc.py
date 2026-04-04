import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect a NetCDF (.nc) file and print dataset metadata."
    )
    parser.add_argument("path", help="Path to the .nc file")
    parser.add_argument(
        "--variable",
        help="Optional variable name to inspect in more detail",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print basic min/max/mean statistics for the selected variable",
    )
    return parser


def format_attrs(attrs: dict) -> str:
    if not attrs:
        return "  (none)"
    return "\n".join(f"  - {key}: {value}" for key, value in attrs.items())


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        import xarray as xr
    except ImportError:
        print(
            "Missing dependency: xarray.\n"
            "Install with: pip install xarray netCDF4",
            file=sys.stderr,
        )
        return 1

    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    try:
        with xr.open_dataset(path) as ds:
            print(f"File: {path}")
            print()

            print("Dimensions")
            for name, size in ds.sizes.items():
                print(f"  - {name}: {size}")
            if not ds.sizes:
                print("  (none)")
            print()

            print("Coordinates")
            if ds.coords:
                for name, coord in ds.coords.items():
                    print(
                        f"  - {name}: dims={coord.dims}, shape={coord.shape}, dtype={coord.dtype}"
                    )
            else:
                print("  (none)")
            print()

            print("Variables")
            if ds.data_vars:
                for name, variable in ds.data_vars.items():
                    units = variable.attrs.get("units")
                    label = (
                        f"  - {name}: dims={variable.dims}, shape={variable.shape}, "
                        f"dtype={variable.dtype}"
                    )
                    if units:
                        label += f", units={units}"
                    print(label)
            else:
                print("  (none)")
            print()

            print("Global Attributes")
            print(format_attrs(ds.attrs))
            print()

            if args.variable:
                if args.variable not in ds:
                    print(
                        f"Variable '{args.variable}' not found. "
                        f"Available variables: {', '.join(ds.data_vars)}",
                        file=sys.stderr,
                    )
                    return 1

                variable = ds[args.variable]
                print(f"Variable Detail: {args.variable}")
                print(variable)
                print()

                print("Variable Attributes")
                print(format_attrs(variable.attrs))
                print()

                if args.stats:
                    try:
                        minimum = variable.min(skipna=True).item()
                        maximum = variable.max(skipna=True).item()
                        mean = variable.mean(skipna=True).item()
                    except Exception as exc:
                        print(f"Could not compute stats: {exc}", file=sys.stderr)
                        return 1

                    print("Variable Stats")
                    print(f"  - min: {minimum}")
                    print(f"  - max: {maximum}")
                    print(f"  - mean: {mean}")

    except Exception as exc:
        print(f"Could not open NetCDF file: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
