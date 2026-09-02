# Repository guidance

## 1. Legacy boundary — highest priority

`legacy/` is archived, read-only, excluded from active development, and must not be inspected or imported unless the user explicitly requests legacy work.

- Do not search, read, modify, fix, refactor, or run code under `legacy/` during active development.
- Do not import from `legacy/` or copy its algorithms into `model_v3`.
- Do not use legacy model outputs, predictions, artifacts, scores, thresholds, or derived datasets as inputs to `model_v3`.
- Historical raw source data may be reused only when its provenance is clear and it is not a model-generated artifact.
- If the user explicitly requests legacy work, limit access and changes to that exact request.

## 2. No invented semantics

- Never invent column meanings, epidemiological definitions, municipality semantics, missing-value semantics, dates, targets, provenance, model parameters, paths, APIs, or thresholds.
- Inspect active source data, configuration, and documentation when clarification is needed.
- If the answer remains unclear, report it as `UNKNOWN`; do not silently select an interpretation.

## 3. Scope control

- Modify only files required for the current task.
- Do not perform unrelated cleanup, modernization, or frontend changes.
- Do not add weather or environmental features until explicitly requested.
- Do not add CatBoost or other machine-learning models until explicitly requested.
- Do not continue into another project phase automatically.

## 4. Reproducibility and provenance

- Every derived dataset must be reproducible from documented inputs.
- Every pipeline stage must declare explicit inputs and outputs, use deterministic transformations where possible, validate schemas, and test critical assumptions.
- Preserve clear provenance between raw source data, derived data, and model-generated outputs.

## 5. Epidemiological design

- The initial Lyme analysis unit is `municipality × issue_week`.
- The planned primary Lyme target is the reported Lyme case count in `t+1` through `t+4`; do not implement it before the dedicated target phase.
- Treat population as an epidemiological denominator, exposure, or model offset, not merely as an arbitrary predictive feature.
- Handle KME/TBE separately. Do not assume it shares Lyme's analysis unit or horizon, and do not implement it without an explicit request.
- Use the documented 2026 GURS municipality snapshot as the fixed analytical municipality zones for every model year. Do not reconstruct time-varying historical municipality boundaries unless the user explicitly changes this rule.

## 6. Information availability

- Features for issue week `t` may use only information available at prediction time.
- Never allow future information into features.
- For the retrospective ERA5-Land weather layer, the weather valid-time cutoff is the availability cutoff: only completed weather weeks strictly before `issue_week` may be used. Do not add an inferred publication embargo, extrapolate weather beyond the verified source cutoff, or synthesize post-cutoff weather.

## 7. Validation and lockbox

- Use time-aware rolling-origin evaluation.
- A four-week future target requires a four-week purge/embargo at split boundaries.
- Reserve 2025 as the initial retrospective lockbox unless the user explicitly changes it.
- The lockbox must not influence feature engineering, hyperparameters, model selection, thresholds, or calibration choices.

## 8. Dependencies

- Add a dependency only when the requested phase requires it.
- First check whether an existing project dependency provides the needed capability.
- Explain any necessary addition and keep it minimal.

## 9. Verification and handoff

- After implementation, run the smallest relevant tests and broader project tests when reasonably available.
- Inspect the final diff and status for unexpected changes.
- End every task with these sections: `CHANGED FILES`, `TESTS RUN`, `RESULTS`, `ASSUMPTIONS MADE`, `UNRESOLVED QUESTIONS`, and `NEXT PHASE READINESS`.
- Report exact commands, results, changes, assumptions, and uncertainties, then stop.
