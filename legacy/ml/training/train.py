from __future__ import annotations

import argparse
import json
from pathlib import Path

from .catboost_pipeline import train_catboost_model
from .config import load_config
from .dataset import PreparedDataset, prepare_dataset
from .splits import build_time_splits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a CatBoost risk model on municipality/time tabular data using "
            "time-ordered train/validation/test splits."
        )
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to a training JSON config file.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate config, schema and time splits without fitting a model.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Optional row limit for smoke tests or quick iteration.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    dataset = prepare_dataset(config, max_rows=args.max_rows)
    splits = build_time_splits(dataset.timestamps, config.split)

    if args.validate_only:
        print("Validation complete.")
        print(json.dumps(build_validation_summary(config, dataset, splits), indent=2))
        return 0

    artifacts = train_catboost_model(config, dataset, splits)
    print("Training complete.")
    print(f"Model: {artifacts.model_path}")
    print(f"Metadata: {artifacts.metadata_path}")
    print(f"Predictions: {artifacts.predictions_path}")
    print(json.dumps(artifacts.metrics, indent=2))
    return 0


def build_validation_summary(
    config,
    dataset: PreparedDataset,
    splits,
) -> dict[str, object]:
    sample_weight_summary = None
    if dataset.sample_weights:
        sample_weight_summary = {
            "column": config.sample_weight.column if config.sample_weight else None,
            "transform": config.sample_weight.transform if config.sample_weight else None,
            "normalize": config.sample_weight.normalize if config.sample_weight else None,
            "min": min(dataset.sample_weights),
            "mean": sum(dataset.sample_weights) / len(dataset.sample_weights),
            "max": max(dataset.sample_weights),
        }
    return {
        "config_path": str(config.config_path),
        "dataset_path": str(config.dataset_path),
        "problem_type": config.problem_type,
        "row_count": dataset.row_count,
        "feature_count": len(dataset.feature_columns),
        "feature_columns": dataset.feature_columns,
        "categorical_columns": dataset.categorical_columns,
        "sample_weight": sample_weight_summary,
        "split_summary": {
            split_name: {
                "row_count": split.row_count,
                "unique_time_count": split.unique_time_count,
                "start_time": split.start_time,
                "end_time": split.end_time,
            }
            for split_name, split in splits.items()
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
