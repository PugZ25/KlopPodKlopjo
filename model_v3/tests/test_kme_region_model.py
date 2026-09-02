from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from model_v3.models.kme_region_model import (
    CATBOOST_FEATURE_COLUMNS,
    CATBOOST_WEATHER,
    GLM_BASE,
    GLM_FULL,
    GLM_SEASONAL_WEATHER,
    GLM_WEATHER_ONLY,
    SYSTEM_IDS,
    WEATHER_FEATURE_COLUMNS,
    Fold,
    KmeModelError,
    PreparedRow,
    TargetObservation,
    aggregate_region_weather,
    build_catboost_pool,
    generate_folds,
    glm_continuous_features,
    prepare_rows,
    select_system,
    selected_region_population,
)


def prepared_row(issue_week: date, *, target_value: int = 1) -> PreparedRow:
    weather = {feature: float(index + 1) for index, feature in enumerate(WEATHER_FEATURE_COLUMNS)}
    return PreparedRow(
        region_code="R1",
        region_name="Region One",
        issue_week=issue_week,
        target_start=issue_week + timedelta(weeks=1),
        target_end=issue_week + timedelta(weeks=8),
        target_value=target_value,
        population=200_000,
        population_year_min=issue_week.year - 1,
        population_year_max=issue_week.year - 1,
        seasonal_sin=0.1,
        seasonal_cos=0.9,
        past_cases=2,
        past_incidence=1.0,
        past_window_start=issue_week - timedelta(weeks=8),
        past_window_end=issue_week - timedelta(weeks=1),
        weather_values=weather,
        weather_window_start=issue_week - timedelta(weeks=4),
        latest_weather_week=issue_week - timedelta(weeks=1),
        latest_weather_week_end=issue_week - timedelta(days=1),
    )


class KmeRegionModelTests(unittest.TestCase):
    def test_population_is_strictly_earlier_and_aggregated_consistently(self) -> None:
        mapping = {"001": "R1", "002": "R1"}
        population = {
            "001": {2020: 100, 2021: 110, 2022: 999},
            "002": {2020: 200, 2021: None, 2022: 999},
        }
        value, minimum_year, maximum_year = selected_region_population(
            "R1", date(2022, 6, 6), mapping, population
        )
        self.assertEqual(value, 310)
        self.assertEqual((minimum_year, maximum_year), (2020, 2021))

        with self.assertRaisesRegex(KmeModelError, "No safely earlier population"):
            selected_region_population(
                "R1", date(2020, 6, 1), mapping, {"001": {2020: 100}, "002": {2020: 200}}
            )

    def test_weather_is_area_weighted_overlay_output_not_point_selection(self) -> None:
        week = date(2022, 1, 3)
        mapping = {"001": "R1", "002": "R1"}
        areas = {"001": 1.0, "002": 3.0}
        weather = {}
        for municipality, value in (("001", 2.0), ("002", 10.0)):
            weather[(municipality, week)] = {
                "week_end": week + timedelta(days=6),
                "status": "complete",
                "values": {
                    "t2m_mean_c": value,
                    "d2m_mean_c": value,
                    "tp_sum_mm": value,
                    "stl1_mean_c": value,
                    "stl2_mean_c": value,
                    "swvl1_mean_m3_m3": value,
                    "swvl2_mean_m3_m3": value,
                },
            }
        result = aggregate_region_weather(weather, mapping, areas)
        self.assertAlmostEqual(result[("R1", week)]["values"]["t2m_mean_c"], 8.0)

    def test_prepared_features_stop_before_issue_week(self) -> None:
        issue = date(2022, 3, 7)
        target = TargetObservation(
            "R1", issue, issue + timedelta(weeks=1), issue + timedelta(weeks=8), 3
        )
        region_cases = {
            ("R1", issue - timedelta(weeks=offset)): offset
            for offset in range(1, 9)
        }
        region_weather = {}
        for offset in range(1, 5):
            week = issue - timedelta(weeks=offset)
            region_weather[("R1", week)] = {
                "week_end": week + timedelta(days=6),
                "values": {
                    "t2m_mean_c": float(offset),
                    "d2m_mean_c": float(offset),
                    "tp_sum_mm": float(offset),
                    "stl1_mean_c": float(offset),
                    "stl2_mean_c": float(offset),
                    "swvl1_mean_m3_m3": float(offset),
                    "swvl2_mean_m3_m3": float(offset),
                },
            }
        rows, exclusions = prepare_rows(
            [target],
            {"R1": "Region One"},
            {"001": "R1"},
            region_cases,
            {"001": {2021: 100_000}},
            region_weather,
        )
        self.assertEqual(exclusions, {})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.past_window_end, issue - timedelta(weeks=1))
        self.assertEqual(row.latest_weather_week, issue - timedelta(weeks=1))
        self.assertLess(row.latest_weather_week_end, issue)
        self.assertEqual(row.past_cases, sum(range(1, 9)))
        self.assertAlmostEqual(row.weather_values["tp_sum_mm_previous_4w_sum"], 10.0)

    def test_rolling_origin_uses_target_end_and_purges_boundary(self) -> None:
        safe_2018 = prepared_row(date(2018, 6, 4))
        safe_2019 = prepared_row(date(2019, 6, 3))
        crossing = prepared_row(date(2019, 11, 11))
        validation = prepared_row(date(2020, 1, 6))
        config = {
            "validation": {
                "first_candidate_validation_iso_year": 2020,
                "last_validation_iso_year": 2020,
                "minimum_distinct_training_iso_years": 2,
            }
        }
        folds = generate_folds([safe_2018, safe_2019, crossing, validation], config)
        self.assertEqual(len(folds), 1)
        fold = folds[0]
        self.assertEqual(fold.n_purged, 1)
        self.assertEqual(fold.train_rows, (safe_2018, safe_2019))
        self.assertTrue(all(row.target_end < fold.validation_start for row in fold.train_rows))
        self.assertTrue(
            all(row.target_end.isocalendar().year == 2020 for row in fold.validation_rows)
        )

    def test_weather_only_and_adjusted_weather_are_distinct_predeclared_ablations(self) -> None:
        self.assertEqual(glm_continuous_features(GLM_WEATHER_ONLY), WEATHER_FEATURE_COLUMNS)
        self.assertEqual(
            glm_continuous_features(GLM_SEASONAL_WEATHER), WEATHER_FEATURE_COLUMNS
        )
        self.assertGreater(len(glm_continuous_features(GLM_FULL)), len(WEATHER_FEATURE_COLUMNS))
        self.assertNotIn("municipality_area_km2", CATBOOST_FEATURE_COLUMNS)
        self.assertNotIn("d2m_mean_c", CATBOOST_FEATURE_COLUMNS)

    def test_catboost_baseline_is_population_offset(self) -> None:
        row = prepared_row(date(2022, 6, 6))
        pool = build_catboost_pool([row], include_labels=True)
        self.assertAlmostEqual(float(pool.get_baseline()[0, 0]), math.log(2.0))

    def test_catboost_requires_improvement_in_every_fold(self) -> None:
        aggregate = []
        fold_metrics = []
        for candidate_id in SYSTEM_IDS:
            pooled_mae = 1.0 if candidate_id == GLM_BASE else 2.0
            if candidate_id == CATBOOST_WEATHER:
                pooled_mae = 0.9
            aggregate.append({"candidate_id": candidate_id, "pooled_mae": pooled_mae})
            for fold_id, mae in (("f1", pooled_mae), ("f2", pooled_mae)):
                if candidate_id == CATBOOST_WEATHER and fold_id == "f2":
                    mae = 1.1
                fold_metrics.append(
                    {"candidate_id": candidate_id, "fold_id": fold_id, "mae": mae}
                )
        selection = select_system(aggregate, fold_metrics)
        self.assertEqual(selection["selected_candidate_id"], GLM_BASE)
        self.assertFalse(selection["catboost_promoted"])


if __name__ == "__main__":
    unittest.main()
