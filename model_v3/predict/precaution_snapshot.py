from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from catboost import CatBoostRegressor

from model_v3.features.open_meteo_activity_weather import read_municipality_weather
from model_v3.models.kme_region_model import (
    annual_harmonic,
    read_mapping,
    read_population as read_kme_population,
    read_regions,
    selected_region_population,
)
from model_v3.models.lyme_precaution_proxy import (
    COMPACT_WEATHER_FEATURES,
    COMPACT_WEATHER_ID,
    NO_WEATHER_ID,
    ProxyRow,
    predict_model,
)
from model_v3.models.non_ml_baselines import file_record, parse_monday, resolve_repo_path
from model_v3.models.seasonal_count_models import (
    build_population_history,
    seasonal_terms,
    select_population_exposure,
)
from model_v3.models.weather_ablation import WeatherScaler, issue_weather_features
from model_v3.predict.lyme_operational import (
    _read_municipalities,
    _read_population,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "model_v3" / "config" / "precaution_snapshot.json"


class PrecautionSnapshotError(ValueError):
    """Raised when the public precaution snapshot violates its declared contract."""


@dataclass(frozen=True)
class DisplayCalibration:
    percentiles: tuple[float, ...]
    values: tuple[float, ...]
    low_upper: float
    medium_upper: float


@dataclass(frozen=True)
class OperationalWeatherScaler:
    scaler: WeatherScaler
    training_support_minimums: Mapping[str, float]
    training_support_maximums: Mapping[str, float]
    training_issue_week_median_minimums: Mapping[str, float]
    training_issue_week_median_maximums: Mapping[str, float]
    training_seasonal_median_outer_fences: Mapping[
        int, Mapping[str, tuple[float, float]]
    ]
    operational_support_tolerances: Mapping[str, float]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise PrecautionSnapshotError("Snapshot configuration must remain in the repository")
    config = json.loads(resolved.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise PrecautionSnapshotError("Snapshot schema_version must equal 1")
    contract = config.get("product_contract", {})
    required_false = (
        "runtime_case_inputs_allowed",
        "personal_risk_output_allowed",
        "direct_tick_measurement_claim_allowed",
        "low_means_safe",
    )
    if any(contract.get(key) is not False for key in required_false):
        raise PrecautionSnapshotError("The precaution-only safety contract changed")
    if contract.get("weather_displayed_as_separate_context") is not True:
        raise PrecautionSnapshotError("Weather must remain explicitly separate context")
    if (
        contract.get("weather_used_by_lyme_score") is not True
        or contract.get("weather_used_by_kme_score") is not False
    ):
        raise PrecautionSnapshotError("Declared disease-specific weather use changed")
    if (
        contract.get("public_signal_window")
        != "issue_week_monday_through_sunday"
        or contract.get("lyme_model_target_matches_public_signal_window") is not True
        or contract.get("lyme_training_target")
        != "reported_lyme_cases_in_current_signal_week"
    ):
        raise PrecautionSnapshotError("Public signal must cover only the issue week")
    weather = config.get("weather", {})
    if weather.get("required_complete_weeks") != 5 or weather.get("lyme_feature_weeks") != 4:
        raise PrecautionSnapshotError(
            "Weather input must support current and previous four-week Lyme features"
        )
    if weather.get("source_model") != "icon_seamless":
        raise PrecautionSnapshotError("Fresh-weather source model changed")
    if (
        weather.get("expected_refresh_cadence_hours") != 24
        or weather.get("maximum_display_age_hours") != 36
    ):
        raise PrecautionSnapshotError("Public weather freshness policy changed")
    if "threshold" not in weather.get("interpretation", ""):
        raise PrecautionSnapshotError("Weather context must reject activity thresholds")
    case_inputs = [key for key in config.get("inputs", {}) if "case" in key.lower()]
    if case_inputs:
        raise PrecautionSnapshotError(f"Runtime case inputs are forbidden: {case_inputs}")
    return config


def _load_weather_scaler(path: Path, expected_sha256: str) -> OperationalWeatherScaler:
    if _sha256(path) != expected_sha256:
        raise PrecautionSnapshotError("Lyme weather scaler hash differs from model seal")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("feature_order") != list(COMPACT_WEATHER_FEATURES):
        raise PrecautionSnapshotError("Lyme compact weather scaler order changed")
    means = payload.get("means", {})
    standard_deviations = payload.get("standard_deviations", {})
    minimums = payload.get("training_support_minimums", {})
    maximums = payload.get("training_support_maximums", {})
    median_minimums = payload.get("training_issue_week_median_minimums", {})
    median_maximums = payload.get("training_issue_week_median_maximums", {})
    tolerances = payload.get("operational_support_tolerances", {})
    raw_seasonal_fences = payload.get("training_seasonal_median_outer_fences", {})
    expected_features = set(COMPACT_WEATHER_FEATURES)
    if any(
        set(values) != expected_features
        for values in (
            means,
            standard_deviations,
            minimums,
            maximums,
            median_minimums,
            median_maximums,
            tolerances,
        )
    ):
        raise PrecautionSnapshotError("Lyme compact weather scaler schema changed")
    if not all(
        math.isfinite(float(means[name]))
        and math.isfinite(float(standard_deviations[name]))
        and float(standard_deviations[name]) > 0
        and math.isfinite(float(minimums[name]))
        and math.isfinite(float(maximums[name]))
        and float(minimums[name]) < float(maximums[name])
        and math.isfinite(float(median_minimums[name]))
        and math.isfinite(float(median_maximums[name]))
        and float(median_minimums[name]) < float(median_maximums[name])
        and math.isfinite(float(tolerances[name]))
        and float(tolerances[name]) > 0
        for name in COMPACT_WEATHER_FEATURES
    ):
        raise PrecautionSnapshotError("Lyme compact weather scaler values are invalid")
    if set(raw_seasonal_fences) != {str(week) for week in range(1, 54)}:
        raise PrecautionSnapshotError("Lyme seasonal weather support is incomplete")
    seasonal_fences: dict[int, dict[str, tuple[float, float]]] = {}
    for week in range(1, 54):
        source = raw_seasonal_fences[str(week)]
        if not isinstance(source, dict) or set(source) != expected_features:
            raise PrecautionSnapshotError("Lyme seasonal weather support schema changed")
        seasonal_fences[week] = {}
        for name in COMPACT_WEATHER_FEATURES:
            row = source[name]
            lower = float(row["lower"])
            upper = float(row["upper"])
            if (
                not math.isfinite(lower)
                or not math.isfinite(upper)
                or lower >= upper
                or int(row["support_issue_weeks"]) < 20
            ):
                raise PrecautionSnapshotError("Lyme seasonal weather support is invalid")
            seasonal_fences[week][name] = (lower, upper)
    return OperationalWeatherScaler(
        scaler=WeatherScaler(
            means={name: float(means[name]) for name in COMPACT_WEATHER_FEATURES},
            standard_deviations={
                name: float(standard_deviations[name])
                for name in COMPACT_WEATHER_FEATURES
            },
        ),
        training_support_minimums={
            name: float(minimums[name]) for name in COMPACT_WEATHER_FEATURES
        },
        training_support_maximums={
            name: float(maximums[name]) for name in COMPACT_WEATHER_FEATURES
        },
        training_issue_week_median_minimums={
            name: float(median_minimums[name]) for name in COMPACT_WEATHER_FEATURES
        },
        training_issue_week_median_maximums={
            name: float(median_maximums[name]) for name in COMPACT_WEATHER_FEATURES
        },
        training_seasonal_median_outer_fences=seasonal_fences,
        operational_support_tolerances={
            name: float(tolerances[name]) for name in COMPACT_WEATHER_FEATURES
        },
    )


def _read_boundaries(path: Path, municipalities: Mapping[str, str]) -> dict[str, tuple[float, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise PrecautionSnapshotError("Municipality boundary asset must be a list")
    coordinates: dict[str, tuple[float, float]] = {}
    names: dict[str, str] = {}
    for source in payload:
        try:
            code = f"{int(source['code']):03d}"
            minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude = (
                float(value) for value in source["bbox"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PrecautionSnapshotError("Municipality boundary schema is invalid") from exc
        if code in coordinates:
            raise PrecautionSnapshotError(f"Duplicate municipality boundary: {code}")
        if not (
            minimum_longitude < maximum_longitude
            and minimum_latitude < maximum_latitude
            and all(
                math.isfinite(value)
                for value in (
                    minimum_longitude,
                    minimum_latitude,
                    maximum_longitude,
                    maximum_latitude,
                )
            )
        ):
            raise PrecautionSnapshotError(f"Invalid municipality bbox: {code}")
        coordinates[code] = (
            (minimum_latitude + maximum_latitude) / 2.0,
            (minimum_longitude + maximum_longitude) / 2.0,
        )
        names[code] = str(source.get("name", "")).strip()
    if set(coordinates) != set(municipalities):
        raise PrecautionSnapshotError("Boundary and canonical municipality codes differ")
    name_differences = {
        code: (municipalities[code], names[code])
        for code in municipalities
        if municipalities[code] != names[code]
    }
    if name_differences:
        raise PrecautionSnapshotError(
            f"Boundary and canonical municipality names differ: {name_differences}"
        )
    return coordinates


def _load_display_calibration(path: Path, disease: str) -> DisplayCalibration:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("interpretation") != "relative_percentile_not_absolute_or_personal_risk":
        raise PrecautionSnapshotError("Display calibration interpretation changed")
    source = payload.get(disease, {})
    quantiles = source.get("quantiles")
    if not isinstance(quantiles, list) or len(quantiles) < 2:
        raise PrecautionSnapshotError(f"{disease} calibration grid is invalid")
    percentiles = tuple(float(row["percentile"]) for row in quantiles)
    values = tuple(float(row["value"]) for row in quantiles)
    if (
        percentiles != tuple(sorted(percentiles))
        or values != tuple(sorted(values))
        or not all(math.isfinite(value) for value in (*percentiles, *values))
    ):
        raise PrecautionSnapshotError(f"{disease} calibration is not monotonic and finite")
    return DisplayCalibration(
        percentiles=percentiles,
        values=values,
        low_upper=float(source["low_upper_percentile"]),
        medium_upper=float(source["medium_upper_percentile"]),
    )


def percentile_score(value: float, calibration: DisplayCalibration) -> float:
    """Interpolate a value on the frozen quantile grid without absolute-risk semantics."""
    if not math.isfinite(value):
        raise PrecautionSnapshotError("Display score input is not finite")
    if value <= calibration.values[0]:
        return calibration.percentiles[0]
    if value >= calibration.values[-1]:
        return calibration.percentiles[-1]
    upper = bisect.bisect_right(calibration.values, value)
    lower = upper - 1
    while upper < len(calibration.values) and calibration.values[upper] == calibration.values[lower]:
        upper += 1
    if upper == len(calibration.values):
        return calibration.percentiles[lower]
    lower_value = calibration.values[lower]
    upper_value = calibration.values[upper]
    if upper_value == lower_value:
        return calibration.percentiles[upper]
    weight = (value - lower_value) / (upper_value - lower_value)
    return calibration.percentiles[lower] + weight * (
        calibration.percentiles[upper] - calibration.percentiles[lower]
    )


def _display_level(score: float, calibration: DisplayCalibration) -> str:
    if score <= calibration.low_upper:
        return "Nizko"
    if score <= calibration.medium_upper:
        return "Srednje"
    return "Visoko"


def _trend_label(delta: int) -> str:
    if delta > 0:
        return f"+{delta} točk glede na prejšnji teden"
    if delta < 0:
        return f"{delta} točk glede na prejšnji teden"
    return "brez spremembe glede na prejšnji teden"


def _read_coefficients(path: Path, seal_manifest_path: Path) -> dict[str, float]:
    seal = json.loads(seal_manifest_path.read_text(encoding="utf-8"))
    expected_hash = seal.get("model_artifact", {}).get("coefficient_sha256")
    if expected_hash != _sha256(path):
        raise PrecautionSnapshotError("KME coefficient hash differs from its seal")
    coefficients: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("feature", "coefficient", "standard_error"):
            raise PrecautionSnapshotError("KME coefficient schema changed")
        for source in reader:
            feature = source["feature"]
            if feature in coefficients:
                raise PrecautionSnapshotError(f"Duplicate KME coefficient: {feature}")
            value = float(source["coefficient"])
            if not math.isfinite(value):
                raise PrecautionSnapshotError("KME coefficient is not finite")
            coefficients[feature] = value
    required = {"intercept", "seasonal_sin_annual", "seasonal_cos_annual"}
    required.update(f"region[{code:02d}]" for code in range(2, 13))
    if set(coefficients) != required:
        raise PrecautionSnapshotError("KME coefficient feature set changed")
    return coefficients


def _region_display_name(name: str) -> str:
    suffix = " STATISTIČNA REGIJA"
    base = name[:-len(suffix)] if name.endswith(suffix) else name
    return base.title()


def _model_location(
    *,
    disease_key: str,
    code: str,
    name: str,
    issue_week: date,
    score: int,
    previous_score: int,
    calibration: DisplayCalibration,
    coordinates: tuple[float, float],
    region_code: str,
    region_name: str,
    weather: Mapping[str, Any],
) -> dict[str, Any]:
    delta = score - previous_score
    return {
        "id": f"{disease_key}-{int(code)}",
        "municipalityCode": str(int(code)),
        "municipalityName": name,
        "regionCode": region_code,
        "regionName": region_name,
        "score": score,
        "level": _display_level(score, calibration),
        "trendDeltaScore": delta,
        "trendLabel": _trend_label(delta),
        "weekStart": issue_week.isoformat(),
        "weekEnd": (issue_week + timedelta(days=6)).isoformat(),
        "coordinates": [round(coordinates[0], 6), round(coordinates[1], 6)],
        "weatherContext": dict(weather),
    }


def _featured_locations(
    locations: Sequence[Mapping[str, Any]], codes: Sequence[str]
) -> list[dict[str, Any]]:
    index = {f"{int(row['municipalityCode']):03d}": row for row in locations}
    if any(code not in index for code in codes):
        raise PrecautionSnapshotError("Configured featured municipality is missing")
    return [
        {
            "municipalityName": index[code]["municipalityName"],
            "municipalityCode": index[code]["municipalityCode"],
            "level": index[code]["level"],
            "score": index[code]["score"],
            "id": index[code]["id"],
        }
        for code in codes
    ]


def build_precaution_snapshot(
    *,
    issue_week: date,
    recent_weather_path: Path,
    weather_quality_path: Path,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    if issue_week.weekday() != 0:
        raise PrecautionSnapshotError("issue_week must be a Monday")
    config_path = config_path.resolve()
    config = load_config(config_path)
    inputs = {key: resolve_repo_path(value) for key, value in config["inputs"].items()}
    missing = [
        str(path)
        for path in (*inputs.values(), recent_weather_path, weather_quality_path)
        if not path.is_file()
    ]
    if missing:
        raise PrecautionSnapshotError(f"Required snapshot inputs are missing: {missing}")

    municipalities = _read_municipalities(inputs["municipality"], expected_count=212)
    municipality_codes = set(municipalities)
    coordinates = _read_boundaries(inputs["municipality_boundaries"], municipalities)
    weekly_weather, weather_quality = read_municipality_weather(
        recent_weather_path,
        weather_quality_path,
        issue_week=issue_week,
        municipality_codes=municipality_codes,
    )
    weather_source = weather_quality.get("source", {})
    if (
        weather_source.get("model") != config["weather"]["source_model"]
        or weather_source.get("data_status") != config["weather"]["data_status"]
        or weather_quality.get("spatial", {}).get("method")
        != "query_operational_model_at_frozen_grid_sample_points_then_apply_normalized_municipality_polygon_intersection_weights"
    ):
        raise PrecautionSnapshotError("Fresh-weather source or spatial contract changed")

    weather_by_municipality: dict[str, dict[str, Any]] = {}
    latest_weather_week = issue_week - timedelta(weeks=1)
    for code in sorted(municipalities):
        context = weekly_weather[(code, latest_weather_week)]
        if context.values is None:
            raise PrecautionSnapshotError("Latest Open-Meteo week is unexpectedly empty")
        weather_by_municipality[code] = {
            "periodStart": context.week_start.isoformat(),
            "periodEnd": context.week_end.isoformat(),
            "airTemperatureC7dMean": round(context.values["t2m_mean_c"], 1),
            "precipitationMm7dTotal": round(context.values["tp_sum_mm"], 1),
            "soilTemperatureC7dMean": round(
                context.values["stl1_mean_c"], 1
            ),
            "soilMoistureM3M3_7dMean": round(
                context.values["swvl1_mean_m3_m3"], 3
            ),
            "source": config["weather"]["source_label"],
            "dataStatus": config["weather"]["data_status"],
            "spatialMethod": config["weather"]["spatial_method"],
            "usedInLymeScore": True,
            "usedInKmeScore": False,
        }

    regions = read_regions(inputs["statistical_region"])
    mapping = read_mapping(inputs["municipality_statistical_region"], regions)
    if set(mapping) != municipality_codes:
        raise PrecautionSnapshotError("Region mapping and municipality support differ")

    lyme_manifest = json.loads(inputs["lyme_model_manifest"].read_text(encoding="utf-8"))
    if (
        lyme_manifest.get("status")
        != "sealed_for_current_week_no_runtime_case_inference"
        or lyme_manifest.get("selected_candidate_id") != COMPACT_WEATHER_ID
        or lyme_manifest.get("runtime_contract", {}).get("output_target_timing")
        != "current_signal_week"
        or lyme_manifest.get("runtime_contract", {}).get("recent_cases_required") is not False
        or lyme_manifest.get("runtime_contract", {}).get("weather_used_by_ai_score") is not True
        or lyme_manifest.get("model_sha256") != _sha256(inputs["lyme_model"])
    ):
        raise PrecautionSnapshotError("Lyme precaution model seal is invalid")
    lyme_selection = json.loads(
        inputs["lyme_model_selection"].read_text(encoding="utf-8")
    )
    if (
        lyme_selection.get("selected_candidate_id") != COMPACT_WEATHER_ID
        or lyme_selection.get("evidence_selected_candidate_id") == COMPACT_WEATHER_ID
        or lyme_selection.get("weather_candidate_passed_evidence_gate") is not False
        or lyme_selection.get("claim_that_weather_improved_validation_allowed") is not False
    ):
        raise PrecautionSnapshotError("Lyme weather evidence status changed")
    with inputs["lyme_aggregate_metrics"].open(encoding="utf-8", newline="") as handle:
        metric_rows = list(csv.DictReader(handle))
    metric_index = {
        (row["evaluation_scope"], row["candidate_id"]): row for row in metric_rows
    }
    required_metric_keys = {
        (scope, candidate)
        for scope in (
            "development_rolling_origin",
            "opened_2025_retrospective_audit",
        )
        for candidate in (NO_WEATHER_ID, COMPACT_WEATHER_ID)
    }
    if set(metric_index) != required_metric_keys:
        raise PrecautionSnapshotError("Lyme aggregate metric support changed")
    lyme_development_weather_mae = float(
        metric_index[("development_rolling_origin", COMPACT_WEATHER_ID)]["pooled_mae"]
    )
    lyme_development_seasonal_mae = float(
        metric_index[("development_rolling_origin", NO_WEATHER_ID)]["pooled_mae"]
    )
    lyme_audit_weather_mae = float(
        metric_index[("opened_2025_retrospective_audit", COMPACT_WEATHER_ID)][
            "pooled_mae"
        ]
    )
    lyme_audit_seasonal_mae = float(
        metric_index[("opened_2025_retrospective_audit", NO_WEATHER_ID)][
            "pooled_mae"
        ]
    )
    if not all(
        math.isfinite(value) and value >= 0
        for value in (
            lyme_development_weather_mae,
            lyme_development_seasonal_mae,
            lyme_audit_weather_mae,
            lyme_audit_seasonal_mae,
        )
    ):
        raise PrecautionSnapshotError("Lyme validation metrics are invalid")
    lyme_calibration = _load_display_calibration(inputs["display_calibration"], "lyme")
    kme_calibration = _load_display_calibration(inputs["display_calibration"], "kme")
    lyme_weather_scaler = _load_weather_scaler(
        inputs["lyme_weather_scaler"], lyme_manifest["weather_scaler_sha256"]
    )

    population = _read_population(inputs["population"])
    population_history = build_population_history(population)
    lyme_model = CatBoostRegressor()
    lyme_model.load_model(str(inputs["lyme_model"]))

    def lyme_predictions(prediction_issue: date) -> dict[str, float]:
        rows: list[ProxyRow] = []
        for code in sorted(municipalities):
            exposure = select_population_exposure(
                population_history,
                municipality_code=code,
                issue_week=prediction_issue,
            )
            annual_sin, annual_cos = seasonal_terms(prediction_issue)
            weather = issue_weather_features(
                weekly_weather,
                municipality_code=code,
                issue_week=prediction_issue,
            )
            if weather is None:
                raise PrecautionSnapshotError(
                    f"Open-Meteo weather features are unavailable for {code} at {prediction_issue}"
                )
            rows.append(
                ProxyRow(
                    municipality_code=code,
                    issue_week=prediction_issue,
                    target_window_start=prediction_issue,
                    target_window_end=prediction_issue,
                    target_value=0,
                    population=exposure.population,
                    population_year=exposure.year,
                    seasonal_sin=annual_sin,
                    seasonal_cos=annual_cos,
                    weather=weather,
                )
            )
        operational_medians = {
            name: statistics.median(
                row.weather.values[name] for row in rows if row.weather is not None
            )
            for name in COMPACT_WEATHER_FEATURES
        }
        outside_support = {
            name: value
            for name, value in operational_medians.items()
            if not (
                lyme_weather_scaler.training_seasonal_median_outer_fences[
                    prediction_issue.isocalendar().week
                ][name][0]
                - lyme_weather_scaler.operational_support_tolerances[name]
                <= value
                <= lyme_weather_scaler.training_seasonal_median_outer_fences[
                    prediction_issue.isocalendar().week
                ][name][1]
                + lyme_weather_scaler.operational_support_tolerances[name]
            )
        }
        if outside_support:
            raise PrecautionSnapshotError(
                "Open-Meteo cross-municipality weather median is outside the "
                f"season-matched ERA5-Land outer fence at {prediction_issue}: "
                f"{outside_support}"
            )
        predicted_cases = predict_model(
            lyme_model,
            rows,
            COMPACT_WEATHER_ID,
            lyme_weather_scaler.scaler,
        )
        return {
            row.municipality_code: float(value) / row.population * 100000.0
            for row, value in zip(rows, predicted_cases, strict=True)
        }

    lyme_current = lyme_predictions(issue_week)
    lyme_previous = lyme_predictions(issue_week - timedelta(weeks=1))

    kme_coefficients = _read_coefficients(
        inputs["kme_coefficients"], inputs["kme_seal_manifest"]
    )
    kme_population = read_kme_population(inputs["population"])

    def kme_predictions(prediction_issue: date) -> dict[str, float]:
        annual_sin, annual_cos = annual_harmonic(prediction_issue)
        result: dict[str, float] = {}
        for region_code in sorted(regions):
            selected_region_population(
                region_code, prediction_issue, mapping, kme_population
            )
            linear_predictor = (
                kme_coefficients["intercept"]
                + kme_coefficients["seasonal_sin_annual"] * annual_sin
                + kme_coefficients["seasonal_cos_annual"] * annual_cos
                + kme_coefficients.get(f"region[{region_code}]", 0.0)
            )
            result[region_code] = math.exp(linear_predictor)
        return result

    kme_current = kme_predictions(issue_week)
    kme_previous = kme_predictions(issue_week - timedelta(weeks=1))

    region_display_names = {
        code: _region_display_name(name) for code, name in regions.items()
    }
    lyme_locations: list[dict[str, Any]] = []
    kme_locations: list[dict[str, Any]] = []
    for code in sorted(municipalities):
        region_code = mapping[code]
        lyme_score = int(round(percentile_score(lyme_current[code], lyme_calibration)))
        previous_lyme_score = int(
            round(percentile_score(lyme_previous[code], lyme_calibration))
        )
        kme_score = int(round(percentile_score(kme_current[region_code], kme_calibration)))
        previous_kme_score = int(
            round(percentile_score(kme_previous[region_code], kme_calibration))
        )
        common = {
            "code": code,
            "name": municipalities[code],
            "issue_week": issue_week,
            "coordinates": coordinates[code],
            "region_code": region_code,
            "region_name": region_display_names[region_code],
            "weather": weather_by_municipality[code],
        }
        lyme_locations.append(
            _model_location(
                disease_key="borelioza",
                score=lyme_score,
                previous_score=previous_lyme_score,
                calibration=lyme_calibration,
                **common,
            )
        )
        kme_locations.append(
            _model_location(
                disease_key="kme",
                score=kme_score,
                previous_score=previous_kme_score,
                calibration=kme_calibration,
                **common,
            )
        )

    featured_codes = config["display"]["featured_municipality_codes"]
    weather_period_start = latest_weather_week.isoformat()
    weather_period_end = (latest_weather_week + timedelta(days=6)).isoformat()
    weather_source_label = config["weather"]["source_label"]
    generated_at = weather_quality["retrieved_at_utc"]
    common_model = {
        "asOfDate": issue_week.isoformat(),
        "generatedAt": generated_at,
        "referenceWeekStart": weather_period_start,
        "referenceWeekEnd": weather_period_end,
        "weatherSource": weather_source_label,
        "weatherModel": weather_source["model"],
        "thresholds": {
            "lowUpper": lyme_calibration.low_upper,
            "mediumUpper": lyme_calibration.medium_upper,
        },
    }
    models = {
        "borelioza": {
            "key": "borelioza",
            "diseaseLabel": "Borelioza",
            "modelId": COMPACT_WEATHER_ID,
            "snapshotLabel": "vremensko posodobljen preventivni signal za tekoči teden",
            "spatialScope": "municipality",
            "scopeLabel": "relativna primerjava občin",
            "dataStatus": "Deluje brez novejših prijav borelioze; zgodovinski podatki so uporabljeni samo pri učenju in preverjanju modela.",
            "methodologyNote": "Signal za tekoči teden združuje sezono, občinski zgodovinski vzorec ter temperaturo zraka in tal in padavine Open-Meteo iz štirih predhodnih zaključenih tednov; novejše prijave primerov niso vhod v oceno.",
            "purpose": "Podpora odločitvi za previdnost pred odhodom v naravo.",
            "disclaimer": "To ni epidemiološki podatek, meritev klopov, diagnoza ali osebna verjetnost okužbe. Nizko ne pomeni varno.",
            "scoreExplanation": "Ocena 0–100 je relativni percentil modelsko pričakovanega bremena prijavljenih primerov borelioze v tekočem tednu glede na časovno ločene napovedi 2017–2024. Ni dejansko število primerov ali osebno tveganje.",
            "modelTarget": "Prijavljeni primeri borelioze v občini v tekočem tednu.",
            "inputWindow": "Sezona, občina, predhodno razpoložljivo prebivalstvo ter vreme — temperatura zraka in plitvih tal in padavine — v štirih zaključenih tednih t−4 do t−1.",
            "validationSummary": (
                "Časovno ločena validacija 2017–2024: vremenski model MAE "
                f"{lyme_development_weather_mae:.3f}, sezonski model "
                f"{lyme_development_seasonal_mae:.3f}; vreme je izboljšalo MAE v "
                f"{lyme_selection['development_weather_improved_fold_count']}/"
                f"{lyme_selection['development_fold_count']} letih. Retrospektivni "
                f"audit 2025: vremenski {lyme_audit_weather_mae:.3f}, sezonski "
                f"{lyme_audit_seasonal_mae:.3f}; vremenska prednost zato ni potrjena."
            ),
            "limitations": [
                "Vremenska različica ni prestala celotnega dokaznega praga in je uporabljena zaradi zahtevane vremenske občutljivosti.",
                "Model je učen z ERA5-Land, v živo pa uporablja preslikane podatke DWD ICON brez zaključene medvirske kalibracije pristranskosti.",
                "Ni neposredna meritev klopov, trenutne pojavnosti ali osebne verjetnosti okužbe.",
            ],
            "topDrivers": [
                "letni sezonski vzorec",
                "občinski zgodovinski vzorec",
                "temperatura zraka in tal v prejšnjih štirih tednih",
                "padavine v prejšnjih štirih tednih",
                "prebivalstvo kot epidemiološki imenovalec",
            ],
            "signalWeekStart": issue_week.isoformat(),
            "signalWeekEnd": (issue_week + timedelta(days=6)).isoformat(),
            "locations": lyme_locations,
            "featuredLocations": _featured_locations(lyme_locations, featured_codes),
            "weatherUsedInScore": True,
            **common_model,
        },
        "kme": {
            "key": "kme",
            "diseaseLabel": "KME",
            "modelId": "glm_seasonal_region_offset",
            "snapshotLabel": "regionalni preventivni signal za tekoči teden",
            "spatialScope": "statistical_region",
            "scopeLabel": "regionalni signal, prikazan na občinah iste regije",
            "dataStatus": "Deluje brez novejših prijav KME; vse občine v isti statistični regiji imajo isti modelni signal.",
            "methodologyNote": "KME signal za tekoči teden temelji na sezoni in statistični regiji; sveže prijave primerov in vreme niso vhod v oceno.",
            "purpose": "Podpora previdnosti in razmisleku o cepljenju proti KME.",
            "disclaimer": "To ni občinska epidemiološka stopnja, meritev klopov, diagnoza ali osebna verjetnost okužbe. Nizko ne pomeni varno.",
            "scoreExplanation": "Ocena 0–100 je regionalni preventivni signal za tekoči teden. Temelji na modelsko pričakovanem regionalnem bremenu v naslednjih osmih tednih in ni ocena primerov v tekočem tednu ali osebnega tveganja.",
            "modelTarget": "Prijavljeni primeri KME v statistični regiji v naslednjih osmih tednih; rezultat je uporabljen kot preventivni signal tekočega tedna.",
            "inputWindow": "Letna sezona, statistična regija in predhodno razpoložljivo prebivalstvo; vreme in novejše prijave primerov niso vhod.",
            "validationSummary": "Časovno ločena regionalna validacija 2018–2025. KME je zaradi redkosti modeliran ločeno od borelioze in samo na ravni statistične regije.",
            "limitations": [
                "Signal ni model trenutne tedenske pojavnosti KME.",
                "Vse občine iste statistične regije imajo enak signal.",
                "Vreme ni vhod v model KME.",
            ],
            "topDrivers": [
                "letni sezonski vzorec",
                "statistična regija",
                "prebivalstvo kot epidemiološki imenovalec",
            ],
            "signalWeekStart": issue_week.isoformat(),
            "signalWeekEnd": (issue_week + timedelta(days=6)).isoformat(),
            "locations": kme_locations,
            "featuredLocations": _featured_locations(kme_locations, featured_codes),
            **{
                **common_model,
                "weatherUsedInScore": False,
                "thresholds": {
                    "lowUpper": kme_calibration.low_upper,
                    "mediumUpper": kme_calibration.medium_upper,
                },
            },
        },
    }
    snapshot = {
        "schemaVersion": 3,
        "generatedAt": generated_at,
        "issueWeek": issue_week.isoformat(),
        "runtimeCaseInputsUsed": False,
        "weatherUsedInAiScores": True,
        "weatherUsedByDisease": {"borelioza": True, "kme": False},
        "weatherContext": {
            "source": weather_source_label,
            "sourceModel": weather_source["model"],
            "dataStatus": weather_source["data_status"],
            "retrievalId": weather_quality["retrieval_id"],
            "periodStart": weather_period_start,
            "periodEnd": weather_period_end,
            "retrievalWindowStart": weather_quality["period_start"],
            "retrievalWindowEnd": weather_quality["period_end"],
            "spatialMethod": config["weather"]["spatial_method"],
            "nativePolygonIntegration": False,
            "expectedRefreshCadenceHours": config["weather"][
                "expected_refresh_cadence_hours"
            ],
            "maximumDisplayAgeHours": config["weather"][
                "maximum_display_age_hours"
            ],
            "interpretation": config["weather"]["interpretation"],
        },
        "models": models,
    }

    output_directory = resolve_repo_path(config["outputs"]["directory"])
    snapshot_path = output_directory / config["outputs"]["snapshot"]
    quality_path = output_directory / config["outputs"]["quality"]
    frontend_path = resolve_repo_path(config["outputs"]["frontend_snapshot"])
    _write_json(snapshot_path, snapshot)
    _write_json(frontend_path, snapshot)
    if snapshot_path.read_bytes() != frontend_path.read_bytes():
        raise PrecautionSnapshotError("Model and frontend snapshots differ")

    input_records = {key: file_record(path) for key, path in inputs.items()}
    input_records["configuration"] = file_record(config_path)
    input_records["generator_code"] = file_record(Path(__file__).resolve())
    input_records["recent_activity_weather"] = file_record(recent_weather_path)
    input_records["recent_activity_weather_quality"] = file_record(weather_quality_path)
    quality = {
        "schema_version": 1,
        "status": "pass",
        "issue_week": issue_week.isoformat(),
        "checks": {
            "runtime_case_inputs_absent": True,
            "lyme_recent_cases_not_required": True,
            "kme_recent_cases_not_required": True,
            "weather_use_is_disease_specific_and_explicit": True,
            "lyme_weather_cross_municipality_medians_within_season_matched_training_fences": True,
            "weather_five_complete_pre_issue_weeks": True,
            "weather_source_is_operational_model_not_observation": True,
            "weather_uses_polygon_intersection_weights": True,
            "weather_activity_threshold_absent": True,
            "public_signal_is_current_issue_week_only": all(
                row["weekStart"] == issue_week.isoformat()
                and row["weekEnd"] == (issue_week + timedelta(days=6)).isoformat()
                for row in (*lyme_locations, *kme_locations)
            ),
            "lyme_model_target_matches_current_signal_week": (
                lyme_manifest["runtime_contract"]["output_target_timing"]
                == "current_signal_week"
            ),
            "lyme_weather_evidence_limit_disclosed": (
                "ni potrjena" in models["borelioza"]["validationSummary"]
                and lyme_selection["weather_candidate_passed_evidence_gate"] is False
            ),
            "municipality_count_is_212": len(lyme_locations) == len(kme_locations) == 212,
            "kme_scope_is_statistical_region": True,
            "personal_risk_output_absent": True,
            "low_never_declared_safe": True,
            "frontend_matches_canonical_snapshot": True,
        },
        "inputs": input_records,
        "outputs": {
            "snapshot": file_record(snapshot_path),
            "frontend_snapshot": file_record(frontend_path),
        },
    }
    if not all(quality["checks"].values()):
        raise PrecautionSnapshotError("One or more snapshot quality checks failed")
    _write_json(quality_path, quality)
    return quality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a no-current-cases public precaution snapshot"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--issue-week", required=True)
    parser.add_argument("--recent-weather", type=Path, required=True)
    parser.add_argument("--weather-quality", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_precaution_snapshot(
        issue_week=parse_monday(args.issue_week, context="issue_week"),
        recent_weather_path=args.recent_weather.resolve(),
        weather_quality_path=args.weather_quality.resolve(),
        config_path=args.config,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
