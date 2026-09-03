from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from model_v3.models.lyme_precaution_proxy import (
    COMPACT_WEATHER_FEATURES,
    COMPACT_WEATHER_ID,
    NO_WEATHER_ID,
    load_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_proxy_contract_targets_current_week_without_runtime_cases() -> None:
    config = load_config(REPO_ROOT / "model_v3/config/lyme_precaution_proxy.json")
    manifest = json.loads(
        (REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/model_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    selection = json.loads(
        (REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/model_selection.json").read_text(
            encoding="utf-8"
        )
    )

    assert config["purpose"]["runtime_case_inputs_allowed"] is False
    assert config["purpose"]["training_target"] == (
        "reported_lyme_cases_in_current_signal_week_t"
    )
    assert config["evaluation"]["target_timing"] == "signal_week_t"
    assert config["evaluation"]["target_embargo_weeks"] == 0
    assert selection["selected_candidate_id"] == COMPACT_WEATHER_ID
    assert selection["evidence_selected_candidate_id"] == NO_WEATHER_ID
    assert selection["weather_candidate_passed_evidence_gate"] is False
    assert selection["weather_required_by_product"] is True
    assert selection["claim_that_weather_improved_validation_allowed"] is False
    assert selection["development_weather_improved_fold_count"] == 6
    assert manifest["runtime_contract"]["recent_cases_required"] is False
    assert manifest["runtime_contract"]["output_target_timing"] == (
        "current_signal_week"
    )
    assert manifest["status"] == (
        "sealed_for_current_week_no_runtime_case_inference"
    )
    assert manifest["runtime_contract"]["weather_used_by_ai_score"] is True
    assert manifest["runtime_contract"]["weather_displayed_as_separate_context"] is True
    assert manifest["runtime_contract"]["operational_weather_features"] == list(
        COMPACT_WEATHER_FEATURES
    )
    assert "swvl1_mean_m3_m3_previous_4w_mean" not in COMPACT_WEATHER_FEATURES

    scaler = json.loads(
        (REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/weather_scaler.json").read_text(
            encoding="utf-8"
        )
    )
    assert scaler["feature_order"] == list(COMPACT_WEATHER_FEATURES)
    assert set(scaler["training_support_minimums"]) == set(COMPACT_WEATHER_FEATURES)
    assert set(scaler["training_support_maximums"]) == set(COMPACT_WEATHER_FEATURES)
    assert set(scaler["training_issue_week_median_minimums"]) == set(
        COMPACT_WEATHER_FEATURES
    )
    assert set(scaler["training_issue_week_median_maximums"]) == set(
        COMPACT_WEATHER_FEATURES
    )
    assert set(scaler["operational_support_tolerances"]) == set(
        COMPACT_WEATHER_FEATURES
    )
    assert set(scaler["training_seasonal_median_outer_fences"]) == {
        str(week) for week in range(1, 54)
    }
    assert all(
        scaler["training_support_minimums"][feature]
        < scaler["training_support_maximums"][feature]
        for feature in COMPACT_WEATHER_FEATURES
    )
    assert all(
        scaler["training_issue_week_median_minimums"][feature]
        < scaler["training_issue_week_median_maximums"][feature]
        for feature in COMPACT_WEATHER_FEATURES
    )
    assert scaler["operational_support_tolerances"] == {
        "stl1_mean_c_previous_4w_mean": 0.05,
        "t2m_mean_c_previous_4w_mean": 0.05,
        "tp_sum_mm_previous_4w_sum": 33.6,
    }
    assert all(
        set(scaler["training_seasonal_median_outer_fences"][str(week)])
        == set(COMPACT_WEATHER_FEATURES)
        for week in range(1, 54)
    )


def test_weather_candidate_failed_the_retrospective_2025_audit() -> None:
    path = REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/aggregate_metrics.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_key = {(row["evaluation_scope"], row["candidate_id"]): row for row in rows}
    no_weather = by_key[("opened_2025_retrospective_audit", NO_WEATHER_ID)]
    weather = by_key[
        (
            "opened_2025_retrospective_audit",
            COMPACT_WEATHER_ID,
        )
    ]

    for metric in ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance"):
        assert float(weather[metric]) > float(no_weather[metric])


def test_fold_predictions_are_for_the_current_signal_week() -> None:
    path = REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/fold_predictions.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        assert tuple(rows.fieldnames or ())[:10] == (
            "evaluation_scope",
            "fold_id",
            "validation_year",
            "candidate_id",
            "municipality_code",
            "issue_week",
            "signal_week_start",
            "signal_week_end",
            "actual_reported_lyme_cases_current_week",
            "predicted_reported_lyme_cases_current_week",
        )
        for index, row in enumerate(rows):
            assert row["signal_week_start"] == row["issue_week"]
            assert date.fromisoformat(row["signal_week_end"]) == (
                date.fromisoformat(row["issue_week"]) + timedelta(days=6)
            )
            if index == 999:
                break


def test_relative_display_bands_are_monotonic_in_development_evidence() -> None:
    calibration = json.loads(
        (REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/display_calibration.json").read_text(
            encoding="utf-8"
        )
    )
    bands = calibration["lyme"]["development_band_summary"]
    actual_means = [row["mean_actual_incidence_per_100000"] for row in bands]

    assert calibration["interpretation"] == "relative_percentile_not_absolute_or_personal_risk"
    assert [row["label"] for row in bands] == ["Nizko", "Srednje", "Visoko"]
    assert actual_means == sorted(actual_means)
