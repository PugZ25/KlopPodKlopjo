from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from model_v3.models.kme_precaution_proxy import BASELINE_ID, MODEL_ID, load_config


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "model_v3/outputs/precaution_proxy/kme_v1"


def test_kme_proxy_is_current_week_and_uses_no_runtime_cases() -> None:
    config = load_config(REPO_ROOT / "model_v3/config/kme_precaution_proxy.json")
    manifest = json.loads((OUTPUT / "model_manifest.json").read_text(encoding="utf-8"))
    assert config["purpose"]["training_target"] == (
        "reported_kme_cases_in_current_signal_week_t"
    )
    assert config["purpose"]["runtime_case_inputs_allowed"] is False
    assert manifest["selected_candidate_id"] == MODEL_ID
    assert manifest["runtime_contract"]["output_target_timing"] == "current_signal_week"
    assert manifest["runtime_contract"]["recent_cases_required"] is False
    assert manifest["runtime_contract"]["spatial_scope"] == "statistical_region"


def test_kme_current_week_model_beats_declared_baseline() -> None:
    with (OUTPUT / "aggregate_metrics.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    index = {(row["evaluation_scope"], row["candidate_id"]): row for row in rows}
    for scope in ("development_rolling_origin", "opened_2025_retrospective_audit"):
        baseline = index[(scope, BASELINE_ID)]
        model = index[(scope, MODEL_ID)]
        for metric in ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance"):
            assert float(model[metric]) < float(baseline[metric])


def test_kme_calibration_has_monotonic_observed_bands() -> None:
    payload = json.loads((OUTPUT / "display_calibration.json").read_text(encoding="utf-8"))
    source = payload["kme"]
    assert source["reference_n"] > 0
    assert source["spatial_scope"] == "statistical_region_not_municipality"
    observed = [
        row["mean_actual_incidence_per_100000"]
        for row in source["development_band_summary"]
    ]
    assert observed == sorted(observed)


def test_kme_fold_predictions_cover_the_current_monday_to_sunday() -> None:
    with (OUTPUT / "fold_predictions.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        issue_week = date.fromisoformat(row["issue_week"])
        assert row["signal_week_start"] == issue_week.isoformat()
        assert row["signal_week_end"] == (issue_week + timedelta(days=6)).isoformat()
