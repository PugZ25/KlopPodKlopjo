from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15

    def validate(self) -> None:
        ratios = [self.train_ratio, self.validation_ratio, self.test_ratio]
        if any(ratio <= 0 for ratio in ratios):
            raise ValueError("All split ratios must be greater than zero.")
        if abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError("Split ratios must sum to 1.0.")


@dataclass(frozen=True)
class CatBoostConfig:
    iterations: int = 800
    learning_rate: float = 0.05
    depth: int = 8
    l2_leaf_reg: float = 3.0
    random_seed: int = 42
    early_stopping_rounds: int = 50
    verbose: int = 100
    loss_function: str | None = None
    eval_metric: str | None = None

    def resolved_loss_function(self, problem_type: str) -> str:
        if self.loss_function:
            return self.loss_function
        if problem_type == "regression":
            return "RMSE"
        return "Logloss"


@dataclass(frozen=True)
class TrainConfig:
    config_path: Path
    dataset_path: Path
    output_dir: Path
    target_column: str
    time_column: str
    problem_type: str = "regression"
    feature_columns: tuple[str, ...] = field(default_factory=tuple)
    categorical_columns: tuple[str, ...] = field(default_factory=tuple)
    id_columns: tuple[str, ...] = field(default_factory=tuple)
    ignore_columns: tuple[str, ...] = field(default_factory=tuple)
    split: SplitConfig = field(default_factory=SplitConfig)
    catboost: CatBoostConfig = field(default_factory=CatBoostConfig)

    def validate(self) -> None:
        if self.problem_type not in {"regression", "binary_classification"}:
            raise ValueError(
                "problem_type must be 'regression' or 'binary_classification'."
            )
        if not self.target_column:
            raise ValueError("target_column is required.")
        if not self.time_column:
            raise ValueError("time_column is required.")
        self.split.validate()


def load_config(path: str | Path) -> TrainConfig:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent

    split = SplitConfig(**raw.get("split", {}))
    catboost = CatBoostConfig(**raw.get("catboost", {}))

    config = TrainConfig(
        config_path=config_path,
        dataset_path=_resolve_input_path(
            raw["dataset_path"],
            base_dir=base_dir,
        ),
        output_dir=_resolve_output_path(
            raw.get("output_dir", "../../data/processed/training/catboost_run"),
            base_dir=base_dir,
        ),
        target_column=raw["target_column"],
        time_column=raw["time_column"],
        problem_type=raw.get("problem_type", "regression"),
        feature_columns=tuple(raw.get("feature_columns", [])),
        categorical_columns=tuple(raw.get("categorical_columns", [])),
        id_columns=tuple(raw.get("id_columns", [])),
        ignore_columns=tuple(raw.get("ignore_columns", [])),
        split=split,
        catboost=catboost,
    )
    config.validate()
    return config


def _resolve_input_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _resolve_output_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()
