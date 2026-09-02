from __future__ import annotations

import csv
import json
from pathlib import Path

from model_v3.models.lyme_precaution_proxy import NO_WEATHER_ID, load_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_proxy_contract_and_selection_do_not_require_current_cases_or_weather() -> None:
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
    assert selection["selected_candidate_id"] == NO_WEATHER_ID
    assert selection["weather_candidate_selected"] is False
    assert selection["development_weather_improved_fold_count"] == 5
    assert manifest["runtime_contract"]["recent_cases_required"] is False
    assert manifest["runtime_contract"]["weather_used_by_ai_score"] is False
    assert manifest["runtime_contract"]["weather_displayed_as_separate_context"] is True


def test_weather_candidate_failed_the_opened_2025_audit() -> None:
    path = REPO_ROOT / "model_v3/outputs/precaution_proxy/lyme_v1/aggregate_metrics.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_key = {(row["evaluation_scope"], row["candidate_id"]): row for row in rows}
    no_weather = by_key[("opened_2025_retrospective_audit", NO_WEATHER_ID)]
    weather = by_key[
        (
            "opened_2025_retrospective_audit",
            "catboost_no_case_compact_weather_offset",
        )
    ]

    for metric in ("pooled_mae", "pooled_rmse", "pooled_mean_poisson_deviance"):
        assert float(weather[metric]) > float(no_weather[metric])


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
