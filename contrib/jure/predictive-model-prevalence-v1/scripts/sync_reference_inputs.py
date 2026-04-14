from __future__ import annotations

import argparse
import sys

from pipeline_utils import (
    LOCKED_LOG_POPULATION_SOURCE,
    LOCKED_NIJZ_WEEKLY_SOURCE,
    LOCKED_POPULATION_SOURCE,
    REFERENCE_LOG_POPULATION,
    REFERENCE_NIJZ_WEEKLY,
    REFERENCE_POPULATION,
    copy_file,
    ensure_project_dirs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy locked explanatory reference inputs into the predictive workspace "
            "without modifying the frozen branch."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing copied files.",
    )
    return parser


def sync_one(source, destination, *, force: bool) -> str:
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    if destination.exists() and not force:
        return f"kept existing: {destination}"
    copy_file(source, destination)
    return f"copied: {destination}"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_project_dirs()

    try:
        results = [
            sync_one(LOCKED_NIJZ_WEEKLY_SOURCE, REFERENCE_NIJZ_WEEKLY, force=args.force),
            sync_one(LOCKED_POPULATION_SOURCE, REFERENCE_POPULATION, force=args.force),
            sync_one(LOCKED_LOG_POPULATION_SOURCE, REFERENCE_LOG_POPULATION, force=args.force),
        ]
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Predictive reference sync completed.")
    for line in results:
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
