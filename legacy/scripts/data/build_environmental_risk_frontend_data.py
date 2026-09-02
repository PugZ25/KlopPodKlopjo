from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DATA_PATH = REPO_ROOT / "frontend" / "src" / "data" / "environmentalRisk.ts"
TRAINING_DIR = REPO_ROOT / "data" / "processed" / "training"

MODULE_HEADER = """export type RiskLevel = 'Nizko' | 'Srednje' | 'Visoko'

export type DiseaseModelKey = 'borelioza' | 'kme'

export type EnvironmentalRiskLocation = {
  id: string
  municipalityCode: string
  municipalityName: string
  score: number
  level: RiskLevel
  weekStart: string
  coordinates: [number, number]
}

export type EnvironmentalRiskModel = {
  key: DiseaseModelKey
  diseaseLabel: string
  modelId: string
  legacyResearchModelId: string
  snapshotWeekStart: string
  snapshotLabel: string
  purpose: string
  disclaimer: string
  scoreExplanation: string
  topDrivers: string[]
  thresholds: {
    lowUpper: number
    mediumUpper: number
  }
  metricSummary: string
  locations: EnvironmentalRiskLocation[]
  featuredLocations: Array<{
    municipalityName: string
    level: RiskLevel
    score: number
    id: string
  }>
}

export const environmentalRiskModels: Record<DiseaseModelKey, EnvironmentalRiskModel> = """


@dataclass(frozen=True)
class ModelSpec:
    key: str
    disease_label: str
    model_id: str
    legacy_research_model_id: str
    prediction_column: str
    artifact_dir: Path
    purpose: str
    disclaimer: str
    score_explanation: str
    top_drivers: list[str]


MODEL_SPECS = (
    ModelSpec(
        key="borelioza",
        disease_label="Borelioza",
        model_id="catboost_tick_borne_lyme_env_v2",
        legacy_research_model_id="catboost_tick_borne_lyme_v1",
        prediction_column="prediction_probability",
        artifact_dir=TRAINING_DIR / "catboost_tick_borne_lyme_env_v2",
        purpose="Okoljski risk model za boreliozo po lokaciji.",
        disclaimer=(
            "To ni napoved diagnoze ali individualne verjetnosti bolezni. "
            "Score je relativni okoljski indeks za primerjavo lokacij."
        ),
        score_explanation=(
            "Score je relativni okoljski indeks na lestvici 0-100, "
            "izracunan kot zaokrozen empiricni percentil zadnjega testnega "
            "tedna znotraj skupne holdout distribucije modela."
        ),
        top_drivers=[
            "sezonski signal",
            "urbaniziranost",
            "pokrovnost in tip rabe tal",
            "razgiban relief",
            "gozdni in prehodni habitat",
        ],
    ),
    ModelSpec(
        key="kme",
        disease_label="KME",
        model_id="catboost_tick_borne_kme_env_v2",
        legacy_research_model_id="catboost_tick_borne_kme_presence_v2",
        prediction_column="prediction_probability",
        artifact_dir=TRAINING_DIR / "catboost_tick_borne_kme_env_v2",
        purpose="Okoljski risk model za KME po lokaciji.",
        disclaimer=(
            "To ni epidemioloska napoved niti kalibrirana verjetnost bolezni. "
            "Score je relativni okoljski indeks za razvrstitev lokacij."
        ),
        score_explanation=(
            "Score je relativni okoljski indeks na lestvici 0-100, "
            "izracunan kot zaokrozen empiricni percentil zadnjega testnega "
            "tedna znotraj skupne holdout distribucije modela."
        ),
        top_drivers=[
            "mesani gozd",
            "nadmorska visina",
            "urbaniziranost",
            "kmetijska krajina",
            "sezonski signal",
        ],
    ),
)


def load_existing_environmental_risk_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    marker = "export const environmentalRiskModels"
    start = text.index("{", text.index(marker))
    return json.loads(text[start:])


def build_coordinate_lookup(existing_data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    lookup: dict[str, tuple[float, float]] = {}
    for model_payload in existing_data.values():
        for location in model_payload["locations"]:
            lookup[str(location["municipalityCode"])] = tuple(location["coordinates"])
    return lookup


def percentile_threshold(sorted_values: list[float], percentile: float) -> float:
    index = (len(sorted_values) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[lower]
    lower_weight = upper - index
    upper_weight = index - lower
    return (sorted_values[lower] * lower_weight) + (sorted_values[upper] * upper_weight)


def classify_level(value: float, low_upper: float, medium_upper: float) -> str:
    if value < low_upper:
        return "Nizko"
    if value < medium_upper:
        return "Srednje"
    return "Visoko"


def score_percentile(sorted_values: list[float], value: float) -> int:
    rank = bisect.bisect_right(sorted_values, value)
    return round((100 * rank) / len(sorted_values))


def format_metric_summary(metrics: dict[str, float]) -> str:
    return (
        f"Test precision {metrics['precision']:.2f}, recall {metrics['recall']:.2f}, "
        f"F1 {metrics['f1']:.2f}, ROC AUC {metrics['roc_auc']:.2f}, PR-AUC {metrics['pr_auc']:.2f}."
    )


def build_model_payload(
    spec: ModelSpec,
    coordinate_lookup: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    metadata = json.loads((spec.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    with (spec.artifact_dir / "holdout_predictions.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    holdout_values = sorted(
        float(row[spec.prediction_column])
        for row in rows
        if row["split"] in {"validation", "test"}
    )
    low_upper = percentile_threshold(holdout_values, 1 / 3)
    medium_upper = percentile_threshold(holdout_values, 2 / 3)

    snapshot_week_start = max(row["week_start"] for row in rows if row["split"] == "test")
    snapshot_rows = [
        row for row in rows if row["split"] == "test" and row["week_start"] == snapshot_week_start
    ]

    locations: list[dict[str, Any]] = []
    for row in snapshot_rows:
        municipality_code = str(row["obcina_sifra"])
        raw_prediction = float(row[spec.prediction_column])
        locations.append(
            {
                "id": f"{spec.key}-{municipality_code}",
                "municipalityCode": municipality_code,
                "municipalityName": row["obcina_naziv"],
                "score": score_percentile(holdout_values, raw_prediction),
                "level": classify_level(raw_prediction, low_upper, medium_upper),
                "weekStart": snapshot_week_start,
                "coordinates": list(coordinate_lookup[municipality_code]),
                "_rawPrediction": raw_prediction,
            }
        )

    locations.sort(
        key=lambda location: (
            -location["score"],
            -location["_rawPrediction"],
            location["municipalityName"],
        )
    )

    featured_locations = [
        {
            "municipalityName": location["municipalityName"],
            "level": location["level"],
            "score": location["score"],
            "id": location["id"],
        }
        for location in locations[:8]
    ]

    for location in locations:
        location.pop("_rawPrediction", None)

    return {
        "key": spec.key,
        "diseaseLabel": spec.disease_label,
        "modelId": spec.model_id,
        "legacyResearchModelId": spec.legacy_research_model_id,
        "snapshotWeekStart": snapshot_week_start,
        "snapshotLabel": "zadnji razpolozljivi holdout teden",
        "purpose": spec.purpose,
        "disclaimer": spec.disclaimer,
        "scoreExplanation": spec.score_explanation,
        "topDrivers": spec.top_drivers,
        "thresholds": {
            "lowUpper": low_upper,
            "mediumUpper": medium_upper,
        },
        "metricSummary": format_metric_summary(metadata["metrics"]["test"]),
        "locations": locations,
        "featuredLocations": featured_locations,
    }


def build_environmental_risk_models() -> dict[str, Any]:
    existing_data = load_existing_environmental_risk_data(FRONTEND_DATA_PATH)
    coordinate_lookup = build_coordinate_lookup(existing_data)
    return {
        spec.key: build_model_payload(spec, coordinate_lookup)
        for spec in MODEL_SPECS
    }


def render_typescript_module(payload: dict[str, Any]) -> str:
    return f"{MODULE_HEADER}{json.dumps(payload, ensure_ascii=False, indent=2)}\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate frontend environmental risk data from env_v2 holdout artifacts."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FRONTEND_DATA_PATH,
        help="Where to write the generated TypeScript module.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with code 1 if the target file does not match the generated output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rendered = render_typescript_module(build_environmental_risk_models())

    if args.check:
        existing = args.output.read_text(encoding="utf-8")
        if existing != rendered:
            print(f"{args.output} is out of date. Re-run the generator.")
            return 1
        print(f"{args.output} is up to date.")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
