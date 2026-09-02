# Model C V2 Residual Climate Modeling

This workspace contains the Version 2 yearly climate-effect branch.

Key changes from V1:

- training uses one collapsed historical climate row per calendar year
- the model predicts climate adjustment around a prevalence baseline
- future scenario paths are driven by climate anomaly indices rather than raw duplicated scenario calibration rows

## Main Commands

```powershell
py -3 scripts/run_model_c_v2_residual_modeling.py
py -3 scripts/generate_model_c_v2_presentation_graphs.py
```
