# No-current-cases precaution proxy

This phase evaluates a public-facing precaution proxy whose weekly inference does not use recent case reports. The training target remains reported Lyme cases in t+1..t+4, so the output is a relative disease-burden proxy, not a direct tick count, infection probability, diagnosis, or personal risk.

Selected candidate: `catboost_no_case_seasonal_municipality_offset`.

Compact weather improved MAE in 5/8 development folds. Weather selected: **false**. The current weather context is displayed separately from the AI score because the weather candidate did not pass the predeclared stability and opened-2025 gates.

The display score is the selected model's predicted incidence percentile against rolling-origin development predictions from 2017-2024. Low/medium/high are relative communication bands and never mean safe/unsafe.
