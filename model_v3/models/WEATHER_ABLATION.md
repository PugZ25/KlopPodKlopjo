# Lyme weather ablation

This Phase 12 experiment keeps the Phase 9 S1 Poisson count model and previous-
year population exposure unchanged while comparing four arms on the same
rolling-origin folds:

1. S1 baseline;
2. S1 plus fixed municipality area;
3. S1 plus lagged ERA5-Land weather;
4. S1 plus fixed municipality area and lagged ERA5-Land weather.

All arms use the same training rows with complete weather support. Because the
active weather archive starts on 2016-03-30, early 2016 issue rows without four
prior completed weather weeks are excluded from every arm rather than imputed.
All validation rows from 2017 through 2024 retain complete weather and the
existing validation folds remain unchanged.

For each of the seven weekly weather variables, the model uses lag 1, lag 2,
and the previous-four-completed-week aggregation. Instantaneous-variable
four-week features are means; precipitation is a four-week sum. Every weather
window ends before `issue_week`; centered, current-week, and future weather are
forbidden. Weather columns are standardized using training-fold means and
standard deviations only.

By explicit project rule, ERA5-Land `valid_time` is the retrospective weather
cutoff. No extra publication embargo is added. The development weather source
ends at `2024-12-31 23:00 UTC`, and no post-cutoff weather is extrapolated or
synthesized. The documented 2026 GURS zones are the same fixed analytical
municipalities for all years.

Reproduce after the weekly weather layer with:

```bash
./.venv/bin/python -B -m model_v3.models.weather_ablation \
  --config model_v3/config/lyme_weather_ablation.json
```

The experiment uses MAE, RMSE and mean Poisson deviance. All incremental
differences are candidate minus the common-support S1 control, so negative is a
descriptive improvement. It does not use CatBoost, classification, risk
categories, or 2025 outcomes.
