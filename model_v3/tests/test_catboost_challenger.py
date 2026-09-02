from __future__ import annotations

import json
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from catboost import CatBoostRegressor

from model_v3.models.catboost_challenger import (
    BASE_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    SCALED_WEATHER_COLUMNS,
    ChallengerRow,
    build_pool,
    build_reference_design,
    classify_difference,
    exposure_baseline,
    feature_matrix,
    validate_municipality_one_hot_contract,
)
from model_v3.models.seasonal_count_models import MODEL_S3, PastIncidence, make_design_spec
from model_v3.models.weather_ablation import (
    IssueWeather,
    WEATHER_FEATURE_COLUMNS,
    WeatherScaler,
)


def fixture_row(
    *,
    issue_week: date = date(2020, 2, 3),
    population: int = 20_000,
    population_year: int = 2019,
    past_cases: int = 4,
    target_value: int = 5,
    municipality_code: str = "001",
) -> ChallengerRow:
    return ChallengerRow(
        municipality_code=municipality_code,
        issue_week=issue_week,
        target_window_start=issue_week + timedelta(weeks=1),
        target_window_end=issue_week + timedelta(weeks=4),
        target_value=target_value,
        population=population,
        population_year=population_year,
        seasonal_sin=0.1,
        seasonal_cos=0.9,
        past_incidence=PastIncidence(
            case_count=past_cases,
            incidence_per_100000=past_cases / population * 100000.0,
            status="available",
            window_start=issue_week - timedelta(weeks=4),
            window_end=issue_week - timedelta(weeks=1),
            latest_information_week=issue_week - timedelta(weeks=1),
        ),
        weather=IssueWeather(
            values={
                feature: float(index + 1)
                for index, feature in enumerate(WEATHER_FEATURE_COLUMNS)
            },
            window_start=issue_week - timedelta(weeks=4),
            latest_week_start=issue_week - timedelta(weeks=1),
            latest_week_end=issue_week - timedelta(days=1),
        ),
    )


def fixture_scaler() -> WeatherScaler:
    return WeatherScaler(
        means={feature: 0.0 for feature in WEATHER_FEATURE_COLUMNS},
        standard_deviations={feature: 1.0 for feature in WEATHER_FEATURE_COLUMNS},
    )


class CatBoostChallengerTests(unittest.TestCase):
    def test_configuration_declares_exact_feature_columns(self) -> None:
        config_path = (
            Path(__file__).resolve().parents[1]
            / "config"
            / "lyme_catboost_challenger.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(config["challenger"]["feature_columns"], list(FEATURE_COLUMNS))

    def test_feature_contract_matches_s3_plus_weather_information(self) -> None:
        self.assertEqual(FEATURE_COLUMNS[:4], BASE_FEATURE_COLUMNS)
        self.assertEqual(FEATURE_COLUMNS[4:], SCALED_WEATHER_COLUMNS)
        self.assertEqual(len(SCALED_WEATHER_COLUMNS), 21)
        self.assertEqual(CATEGORICAL_FEATURES, ("municipality_code",))
        self.assertNotIn("population", FEATURE_COLUMNS)
        self.assertNotIn("municipality_area_km2", FEATURE_COLUMNS)

    def test_population_is_fixed_exposure_baseline_not_feature(self) -> None:
        row = fixture_row(population=20_000)
        matrix = feature_matrix([row], fixture_scaler())
        baseline = exposure_baseline([row])

        self.assertEqual(len(matrix[0]), len(FEATURE_COLUMNS))
        self.assertAlmostEqual(baseline[0], math.log(0.2))
        self.assertNotIn(20_000, matrix[0])

    def test_validation_pool_has_no_label(self) -> None:
        pool = build_pool(
            [fixture_row()], fixture_scaler(), include_labels=False
        )

        self.assertIsNone(pool.get_label())
        self.assertEqual(pool.get_baseline().shape, (1, 1))

    def test_municipality_must_remain_one_hot_without_unseen_categories(self) -> None:
        train_rows = [
            fixture_row(municipality_code="001"),
            fixture_row(municipality_code="002"),
        ]
        validation_rows = [fixture_row(municipality_code="002")]

        self.assertEqual(
            validate_municipality_one_hot_contract(
                train_rows, validation_rows, one_hot_max_size=2
            ),
            (2, 1),
        )
        with self.assertRaisesRegex(ValueError, "exceeds one_hot_max_size"):
            validate_municipality_one_hot_contract(
                train_rows, validation_rows, one_hot_max_size=1
            )
        with self.assertRaisesRegex(ValueError, "absent from training"):
            validate_municipality_one_hot_contract(
                train_rows,
                [fixture_row(municipality_code="003")],
                one_hot_max_size=2,
            )

    def test_pool_baseline_is_added_before_poisson_exponentiation(self) -> None:
        rows = [
            fixture_row(issue_week=date(2020, 2, 3), past_cases=1, target_value=1),
            fixture_row(issue_week=date(2020, 2, 10), past_cases=2, target_value=3),
            fixture_row(issue_week=date(2020, 2, 17), past_cases=3, target_value=2),
            fixture_row(issue_week=date(2020, 2, 24), past_cases=4, target_value=5),
        ]
        scaler = fixture_scaler()
        train_pool = build_pool(rows, scaler, include_labels=True)
        prediction_pool = build_pool(rows, scaler, include_labels=False)
        model = CatBoostRegressor(
            loss_function="Poisson",
            iterations=5,
            depth=2,
            learning_rate=0.05,
            random_seed=0,
            thread_count=1,
            one_hot_max_size=255,
            allow_writing_files=False,
            verbose=False,
            has_time=True,
        )
        model.fit(train_pool)
        raw_without_baseline = model.predict(
            feature_matrix(rows, scaler), prediction_type="RawFormulaVal"
        )
        predicted_with_pool = model.predict(
            prediction_pool, prediction_type="Exponent"
        )
        stored_baseline = prediction_pool.get_baseline().reshape(-1)

        np.testing.assert_allclose(
            stored_baseline,
            exposure_baseline(rows),
            rtol=1e-7,
            atol=1e-7,
        )

        np.testing.assert_allclose(
            predicted_with_pool,
            np.exp(stored_baseline + raw_without_baseline),
            rtol=1e-12,
            atol=1e-12,
        )

    def test_current_or_future_information_is_rejected(self) -> None:
        row = fixture_row()
        invalid = ChallengerRow(
            **{
                **row.__dict__,
                "past_incidence": PastIncidence(
                    **{
                        **row.past_incidence.__dict__,
                        "latest_information_week": row.issue_week,
                    }
                ),
            }
        )

        with self.assertRaisesRegex(ValueError, "reaches issue time"):
            feature_matrix([invalid], fixture_scaler())

    def test_current_weather_is_rejected(self) -> None:
        row = fixture_row()
        invalid = ChallengerRow(
            **{
                **row.__dict__,
                "weather": IssueWeather(
                    **{
                        **row.weather.__dict__,
                        "latest_week_end": row.issue_week,
                    }
                ),
            }
        )

        with self.assertRaisesRegex(ValueError, "reaches issue time"):
            feature_matrix([invalid], fixture_scaler())

    def test_reference_and_challenger_share_numeric_information(self) -> None:
        rows = [fixture_row(municipality_code="001")]
        scaler = fixture_scaler()
        spec = make_design_spec(MODEL_S3, rows)
        reference = build_reference_design(rows, spec, scaler)
        challenger = feature_matrix(rows, scaler)

        self.assertEqual(reference.shape, (1, 4 + len(SCALED_WEATHER_COLUMNS)))
        self.assertEqual(len(challenger[0]), len(FEATURE_COLUMNS))
        np.testing.assert_allclose(
            reference[0, 1:],
            np.asarray(challenger[0][1:], dtype=np.float64),
        )

    def test_metric_differences_are_lower_is_better(self) -> None:
        self.assertEqual(classify_difference(-0.1), "improvement")
        self.assertEqual(classify_difference(0.1), "deterioration")
        self.assertEqual(classify_difference(0.0), "no_change")


if __name__ == "__main__":
    unittest.main()
