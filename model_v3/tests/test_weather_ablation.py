from __future__ import annotations

import unittest
from datetime import date, timedelta

from model_v3.models.weather_ablation import (
    COMBINED_ID,
    CONTROL_ID,
    OUTPUT_VARIABLES,
    WEATHER_FEATURE_COLUMNS,
    IssueWeather,
    ModelRow,
    WeeklyWeather,
    build_design_matrix,
    candidate_columns,
    fit_weather_scaler,
    issue_weather_features,
)


def weather_mapping(
    *, issue_week: date = date(2020, 2, 3), current_value: float = 999.0
) -> dict[tuple[str, date], WeeklyWeather]:
    result: dict[tuple[str, date], WeeklyWeather] = {}
    for lag in (4, 3, 2, 1):
        week_start = issue_week - timedelta(weeks=lag)
        values = {
            variable: float(lag * 10 + index)
            for index, variable in enumerate(OUTPUT_VARIABLES)
        }
        result[("001", week_start)] = WeeklyWeather(
            municipality_code="001",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            status="complete",
            values=values,
        )
    result[("001", issue_week)] = WeeklyWeather(
        municipality_code="001",
        week_start=issue_week,
        week_end=issue_week + timedelta(days=6),
        status="complete",
        values={variable: current_value for variable in OUTPUT_VARIABLES},
    )
    return result


def model_row(*, weather_offset: float = 0.0) -> ModelRow:
    values = {
        feature: float(index + 1) + weather_offset
        for index, feature in enumerate(WEATHER_FEATURE_COLUMNS)
    }
    return ModelRow(
        municipality_code="001",
        issue_week=date(2020, 2, 3),
        target_window_start=date(2020, 2, 10),
        target_window_end=date(2020, 3, 2),
        target_value=3,
        population=20_000,
        population_year=2019,
        seasonal_sin=0.2,
        seasonal_cos=0.8,
        municipality_area_km2=50.0,
        weather=IssueWeather(
            values=values,
            window_start=date(2020, 1, 6),
            latest_week_start=date(2020, 1, 27),
            latest_week_end=date(2020, 2, 2),
        ),
    )


class WeatherAblationTests(unittest.TestCase):
    def test_features_use_exactly_t_minus_4_through_t_minus_1(self) -> None:
        issue_week = date(2020, 2, 3)
        features = issue_weather_features(
            weather_mapping(issue_week=issue_week),
            municipality_code="001",
            issue_week=issue_week,
        )
        self.assertIsNotNone(features)
        assert features is not None
        self.assertEqual(features.window_start, issue_week - timedelta(weeks=4))
        self.assertEqual(features.latest_week_start, issue_week - timedelta(weeks=1))
        self.assertEqual(features.latest_week_end, issue_week - timedelta(days=1))
        self.assertEqual(features.values["t2m_mean_c_lag_1w"], 10.0)
        self.assertEqual(features.values["t2m_mean_c_lag_2w"], 20.0)
        self.assertEqual(features.values["t2m_mean_c_previous_4w_mean"], 25.0)
        precipitation_index = OUTPUT_VARIABLES.index("tp_sum_mm")
        expected_precipitation = sum(lag * 10 + precipitation_index for lag in (4, 3, 2, 1))
        self.assertEqual(
            features.values["tp_sum_mm_previous_4w_sum"], expected_precipitation
        )

    def test_current_and_future_weather_cannot_change_features(self) -> None:
        issue_week = date(2020, 2, 3)
        first = issue_weather_features(
            weather_mapping(issue_week=issue_week, current_value=1.0),
            municipality_code="001",
            issue_week=issue_week,
        )
        second_mapping = weather_mapping(issue_week=issue_week, current_value=9999.0)
        future_week = issue_week + timedelta(weeks=1)
        second_mapping[("001", future_week)] = WeeklyWeather(
            "001",
            future_week,
            future_week + timedelta(days=6),
            "complete",
            {variable: -9999.0 for variable in OUTPUT_VARIABLES},
        )
        second = issue_weather_features(
            second_mapping,
            municipality_code="001",
            issue_week=issue_week,
        )
        self.assertEqual(first, second)

    def test_missing_completed_week_is_not_zero_imputed(self) -> None:
        issue_week = date(2020, 2, 3)
        weekly = weather_mapping(issue_week=issue_week)
        del weekly[("001", issue_week - timedelta(weeks=3))]
        self.assertIsNone(
            issue_weather_features(
                weekly, municipality_code="001", issue_week=issue_week
            )
        )

    def test_population_is_not_an_ordinary_design_column(self) -> None:
        self.assertNotIn("population", candidate_columns(CONTROL_ID))
        self.assertNotIn("population", candidate_columns(COMBINED_ID))

    def test_weather_scaling_uses_supplied_training_rows_only(self) -> None:
        training = [model_row(weather_offset=0.0), model_row(weather_offset=2.0)]
        scaler = fit_weather_scaler(training)
        first_feature = WEATHER_FEATURE_COLUMNS[0]
        self.assertEqual(scaler.means[first_feature], 2.0)
        self.assertEqual(scaler.standard_deviations[first_feature], 1.0)
        matrix = build_design_matrix(training, COMBINED_ID, scaler)
        self.assertEqual(matrix.shape[0], 2)
        self.assertEqual(matrix[0, 4], -1.0)
        self.assertEqual(matrix[1, 4], 1.0)


if __name__ == "__main__":
    unittest.main()
