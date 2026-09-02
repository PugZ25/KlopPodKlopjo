# Model A V2 Residual Forecasting

This workspace contains the Version 2 monthly operational forecasting branch.

Key change from V1:

- the model no longer predicts prevalence directly
- it starts from a seasonal baseline, mainly same-month-last-year prevalence
- it then predicts the residual adjustment around that baseline using forecast weather anomalies

Outputs include holdout validation tables, future latest-issue forecasts, and
presentation-ready charts.

## Main Commands

```powershell
py -3 scripts/run_model_a_v2_residual_modeling.py
py -3 scripts/generate_model_a_v2_presentation_graphs.py
```
