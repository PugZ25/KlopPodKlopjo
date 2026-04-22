from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_LIVE_RISK_PATH = (
    REPO_ROOT / "frontend" / "src" / "data" / "liveMunicipalityRisk.ts"
)
TRAINING_DATASET_PATH = (
    REPO_ROOT / "data" / "processed" / "training" / "obcina_weekly_tick_borne_catboost_ready.csv"
)
OUTPUT_DIR = REPO_ROOT / "data" / "reference" / "live_snapshot"
MUNICIPALITY_STATIC_FEATURES_PATH = OUTPUT_DIR / "municipality_static_features.json"
MUNICIPALITY_COORDINATES_PATH = OUTPUT_DIR / "municipality_coordinates.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

MODULE_EXPORT_PREFIX = (
    "export const liveMunicipalityRiskModels: Record<DiseaseModelKey, LiveMunicipalityRiskModel> = "
)

STATIC_FEATURE_COLUMNS = (
    "dominant_clc_code",
    "elevation_m_mean",
    "elevation_m_std",
    "elevation_m_range",
    "dominant_clc_cover_pct",
    "urban_cover_pct",
    "agricultural_cover_pct",
    "grassland_pasture_cover_pct",
    "forest_cover_pct",
    "broad_leaved_forest_cover_pct",
    "coniferous_forest_cover_pct",
    "mixed_forest_cover_pct",
    "shrub_transitional_cover_pct",
    "wetland_cover_pct",
    "water_cover_pct",
)

MODEL_REFERENCE_SPECS = (
    {
        "model_id": "catboost_tick_borne_lyme_env_v2",
        "source_dir": REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_lyme_env_v2",
        "prediction_column": "prediction_probability",
    },
    {
        "model_id": "catboost_tick_borne_kme_env_v2",
        "source_dir": REPO_ROOT
        / "data"
        / "processed"
        / "training"
        / "catboost_tick_borne_kme_env_v2",
        "prediction_column": "prediction_probability",
    },
)


def parse_live_models(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    marker_index = text.find(MODULE_EXPORT_PREFIX)
    if marker_index == -1:
        raise ValueError(f"Could not find liveMunicipalityRisk export in {path}.")

    payload_text = text[marker_index + len(MODULE_EXPORT_PREFIX) :].strip()
    return json.loads(payload_text)


def municipality_sort_key(value: str) -> tuple[int, str]:
    stripped = str(value).strip()
    if stripped.isdigit():
        return (int(stripped), stripped)
    return (10**9, stripped)


def build_coordinate_lookup(path: Path) -> dict[str, list[float]]:
    live_models = parse_live_models(path)
    lookup: dict[str, list[float]] = {}
    for model_payload in live_models.values():
        if not isinstance(model_payload, dict):
            continue
        for location in model_payload.get("locations", []):
            municipality_code = str(location["municipalityCode"]).strip()
            coordinates = location.get("coordinates")
            if not isinstance(coordinates, list) or len(coordinates) != 2:
                raise ValueError(
                    f"Invalid coordinates for municipality {municipality_code} in {path}."
                )
            normalized = [float(coordinates[0]), float(coordinates[1])]
            previous = lookup.get(municipality_code)
            if previous is not None and previous != normalized:
                raise ValueError(
                    f"Coordinate mismatch for municipality {municipality_code} across models."
                )
            lookup[municipality_code] = normalized

    if not lookup:
        raise ValueError(f"No municipality coordinates found in {path}.")

    return {
        municipality_code: lookup[municipality_code]
        for municipality_code in sorted(lookup, key=municipality_sort_key)
    }


def build_static_feature_lookup(path: Path) -> dict[str, dict[str, object]]:
    required_columns = {"obcina_sifra", "obcina_naziv", *STATIC_FEATURE_COLUMNS}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Training dataset is missing a header row: {path}.")

        missing = sorted(required_columns - set(reader.fieldnames))
        if missing:
            raise ValueError(
                "Training dataset is missing required columns: " + ", ".join(missing)
            )

        lookup: dict[str, dict[str, object]] = {}
        for row in reader:
            municipality_code = str(row["obcina_sifra"]).strip()
            feature_values: dict[str, object] = {
                "obcina_naziv": str(row["obcina_naziv"]).strip(),
            }
            for column in STATIC_FEATURE_COLUMNS:
                raw_value = row[column].strip()
                if column == "dominant_clc_code":
                    feature_values[column] = raw_value or "__MISSING__"
                    continue
                feature_values[column] = float(raw_value) if raw_value else None

            lookup[municipality_code] = feature_values

    if not lookup:
        raise ValueError(f"No municipality rows found in {path}.")

    return {
        municipality_code: lookup[municipality_code]
        for municipality_code in sorted(lookup, key=municipality_sort_key)
    }


def build_holdout_values(path: Path, *, prediction_column: str) -> list[float]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        values = sorted(
            float(row[prediction_column])
            for row in rows
            if row["split"] in {"validation", "test"}
        )
    if not values:
        raise ValueError(f"No holdout values found in {path}.")
    return values


def write_json(path: Path, payload: object, *, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if indent is None:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    path.write_text(text, encoding="utf-8")


def copy_model_assets() -> dict[str, dict[str, object]]:
    model_manifest: dict[str, dict[str, object]] = {}
    for spec in MODEL_REFERENCE_SPECS:
        model_id = str(spec["model_id"])
        source_dir = Path(spec["source_dir"])
        prediction_column = str(spec["prediction_column"])
        output_dir = OUTPUT_DIR / model_id
        output_dir.mkdir(parents=True, exist_ok=True)

        source_model_path = source_dir / "model.cbm"
        source_metadata_path = source_dir / "metadata.json"
        source_holdout_path = source_dir / "holdout_predictions.csv"

        holdout_values = build_holdout_values(
            source_holdout_path,
            prediction_column=prediction_column,
        )
        holdout_values_path = output_dir / "holdout_values.json"

        shutil.copy2(source_model_path, output_dir / "model.cbm")
        shutil.copy2(source_metadata_path, output_dir / "metadata.json")
        write_json(holdout_values_path, holdout_values, indent=None)

        model_manifest[model_id] = {
            "holdoutValueCount": len(holdout_values),
            "modelPath": str((output_dir / "model.cbm").relative_to(REPO_ROOT)),
            "metadataPath": str((output_dir / "metadata.json").relative_to(REPO_ROOT)),
            "holdoutValuesPath": str(holdout_values_path.relative_to(REPO_ROOT)),
        }

    return model_manifest


def main() -> int:
    coordinates = build_coordinate_lookup(FRONTEND_LIVE_RISK_PATH)
    static_features = build_static_feature_lookup(TRAINING_DATASET_PATH)
    model_manifest = copy_model_assets()

    write_json(MUNICIPALITY_COORDINATES_PATH, coordinates)
    write_json(MUNICIPALITY_STATIC_FEATURES_PATH, static_features)
    write_json(
        MANIFEST_PATH,
        {
            "generatedFrom": {
                "liveFrontendModule": str(FRONTEND_LIVE_RISK_PATH.relative_to(REPO_ROOT)),
                "trainingDataset": str(TRAINING_DATASET_PATH.relative_to(REPO_ROOT)),
            },
            "municipalityCount": len(coordinates),
            "staticFeatureColumnCount": len(STATIC_FEATURE_COLUMNS),
            "models": model_manifest,
        },
    )

    print(f"Live snapshot reference assets written to {OUTPUT_DIR}")
    print(f"- municipality coordinates: {len(coordinates)}")
    print(f"- municipality static features: {len(static_features)}")
    for model_id, payload in model_manifest.items():
        print(f"- {model_id}: {payload['holdoutValueCount']} holdout values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
