# No-current-cases precaution proxy

This phase evaluates a public-facing precaution proxy whose weekly inference does not use recent case reports. The training target is the reported Lyme case count in the current signal week t. Runtime inputs use only information available before t, including weather from completed weeks t-4 through t-1. The output is a relative current-week disease-burden proxy, not a direct tick count, infection probability, diagnosis, or personal risk.

Evidence-selected candidate: `catboost_current_week_seasonal_municipality_offset`.

Deployed candidate under the reviewed weather-required product policy: `catboost_current_week_compact_weather_offset`.

Compact weather improved MAE in 6/8 development folds. Weather passed the predictive evidence gate: **false**. The weather candidate remains deployed only because weather was explicitly made a product requirement; this is an override, not a claim of improved validation.

Operational inputs are four-week air temperature, precipitation, and shallow-soil temperature. DWD ICON soil moisture is excluded from the score because the live audit placed it outside ERA5-Land training support. Inference fails closed when the cross-municipality median of a scored operational feature is outside a season-matched training outer fence after source-resolution tolerance; cross-source bias calibration remains incomplete.

The display score is the deployed model's predicted current-week incidence percentile against rolling-origin development predictions from 2017-2024. Low/medium/high are relative communication bands and never mean safe/unsafe.
