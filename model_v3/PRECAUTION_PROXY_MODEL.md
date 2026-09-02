# No-current-cases precaution proxy

This phase evaluates a public-facing precaution proxy whose weekly inference does not use recent case reports. The training target remains reported Lyme cases in t+1..t+4, so the output is a relative disease-burden proxy, not a direct tick count, infection probability, diagnosis, or personal risk.

Evidence-selected candidate: `catboost_no_case_seasonal_municipality_offset`.

Deployed candidate under the reviewed weather-required product policy: `catboost_no_case_compact_weather_offset`.

Compact weather improved MAE in 5/8 development folds. Weather passed the predictive evidence gate: **false**. The weather candidate remains deployed only because weather was explicitly made a product requirement; this is an override, not a claim of improved validation.

The display score is the selected model's predicted incidence percentile against rolling-origin development predictions from 2017-2024. Low/medium/high are relative communication bands and never mean safe/unsafe.
