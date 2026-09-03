# KME current-week precaution proxy

The model target is the reported KME case count in the current signal week t at statistical-region level. Runtime inference uses region, annual seasonality and strictly earlier population; it uses neither recent case reports nor weather. The 0-100 display is the percentile of predicted current-week incidence against rolling-origin predictions from 2018-2024, not personal risk.

Development pooled MAE: model 0.2389, baseline 0.3000. Opened 2025 retrospective MAE: model 0.1968, baseline 0.2537.
