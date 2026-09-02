#!/usr/bin/env python3
"""Shared utilities for okoljski_raziskovalni_model."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

RANDOM_SEED = 42
CATBOOST_PARAMS = {
    "loss_function": "RMSE",
    "eval_metric": "RMSE",
    "iterations": 250,
    "learning_rate": 0.06,
    "depth": 6,
    "l2_leaf_reg": 5.0,
    "random_seed": RANDOM_SEED,
    "verbose": False,
    "allow_writing_files": False,
}


def rmse(actual: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - actual) ** 2)))


def mae(actual: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.mean(np.abs(prediction - actual)))


def spearman_corr(actual: pd.Series, prediction: pd.Series) -> float:
    correlation = actual.corr(prediction, method="spearman")
    if pd.isna(correlation):
        return math.nan
    return float(correlation)


def format_pct(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100.0, 4)
