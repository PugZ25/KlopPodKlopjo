from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from model_v3.predict.precaution_snapshot import (
    DisplayCalibration,
    load_config,
    percentile_score,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_snapshot_config_has_no_runtime_case_input() -> None:
    config = load_config(REPO_ROOT / "model_v3/config/precaution_snapshot.json")

    assert config["product_contract"]["runtime_case_inputs_allowed"] is False
    assert config["product_contract"]["weather_used_by_lyme_score"] is True
    assert config["product_contract"]["weather_used_by_kme_score"] is False
    assert config["product_contract"]["public_signal_window"] == (
        "issue_week_monday_through_sunday"
    )
    assert config["product_contract"]["lyme_model_target_matches_public_signal_window"] is True
    assert config["product_contract"]["lyme_training_target"] == (
        "reported_lyme_cases_in_current_signal_week"
    )
    assert config["weather"]["expected_refresh_cadence_hours"] == 24
    assert config["weather"]["maximum_display_age_hours"] == 36
    assert not [key for key in config["inputs"] if "case" in key.lower()]


def test_percentile_score_interpolates_and_clamps() -> None:
    calibration = DisplayCalibration(
        percentiles=(0.0, 50.0, 100.0),
        values=(2.0, 4.0, 8.0),
        low_upper=33.333333333333336,
        medium_upper=66.66666666666667,
    )

    assert percentile_score(1.0, calibration) == 0.0
    assert percentile_score(3.0, calibration) == 25.0
    assert percentile_score(6.0, calibration) == 75.0
    assert percentile_score(9.0, calibration) == 100.0


def test_frontend_snapshot_preserves_scope_and_weather_separation() -> None:
    path = REPO_ROOT / "frontend/src/data/precautionSnapshot.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schemaVersion"] == 3
    assert payload["runtimeCaseInputsUsed"] is False
    assert payload["weatherUsedInAiScores"] is True
    assert payload["weatherUsedByDisease"] == {"borelioza": True, "kme": False}
    assert payload["weatherContext"]["expectedRefreshCadenceHours"] == 24
    assert payload["weatherContext"]["maximumDisplayAgeHours"] == 36
    assert set(payload["models"]) == {"borelioza", "kme"}
    issue_week = date.fromisoformat(payload["issueWeek"])
    expected_end = (issue_week + timedelta(days=6)).isoformat()

    for key, model in payload["models"].items():
        assert model["signalWeekStart"] == payload["issueWeek"]
        assert model["signalWeekEnd"] == expected_end
        assert model["modelTarget"]
        assert model["inputWindow"]
        assert model["validationSummary"]
        assert model["limitations"]
        assert "predictionWindowStart" not in model
        assert "predictionWindowEnd" not in model
        assert model["weatherUsedInScore"] is (key == "borelioza")
        assert len(model["locations"]) == 212
        assert len({row["municipalityCode"] for row in model["locations"]}) == 212
        for row in model["locations"]:
            assert row["weekStart"] == payload["issueWeek"]
            assert row["weekEnd"] == expected_end
            assert 0 <= row["score"] <= 100
            assert row["level"] in {"Nizko", "Srednje", "Visoko"}
            context = row["weatherContext"]
            assert context["usedInLymeScore"] is True
            assert context["usedInKmeScore"] is False
            assert context["dataStatus"] == (
                "recent_operational_model_history_not_station_observations"
            )
            assert context["spatialMethod"] == (
                "frozen_grid_samples_weighted_by_municipality_polygon_intersections"
            )
            assert all(
                math.isfinite(context[key])
                for key in (
                    "airTemperatureC7dMean",
                    "precipitationMm7dTotal",
                    "soilTemperatureC7dMean",
                    "soilMoistureM3M3_7dMean",
                )
            )

    kme_by_region: defaultdict[str, set[tuple[int, str]]] = defaultdict(set)
    for row in payload["models"]["kme"]["locations"]:
        kme_by_region[row["regionCode"]].add((row["score"], row["level"]))
    assert len(kme_by_region) == 12
    assert all(len(values) == 1 for values in kme_by_region.values())
    assert payload["models"]["kme"]["spatialScope"] == "statistical_region"
    assert "ni potrjena" in payload["models"]["borelioza"]["validationSummary"]
    assert "vreme" in payload["models"]["borelioza"]["inputWindow"].lower()
