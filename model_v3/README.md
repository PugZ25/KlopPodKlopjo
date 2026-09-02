# model_v3

`model_v3` is the clean boundary for the reproducible modelling and public
precaution-snapshot pipeline. Its implemented stages follow these design rules.

- The Lyme analysis unit is `municipality × issue_week`.
- The Lyme training target is the number of reported Lyme cases in `t+1` through `t+4`.
- Population will be used as an epidemiological denominator, exposure, or model offset.
- Features for issue week `t` will use only information available at prediction time.
- Evaluation will use time-aware rolling-origin validation.
- A four-week target will use a four-week purge/embargo at split boundaries.
- The original 2025 lockbox has been opened and is explicitly labelled as a retrospective audit; no untouched lockbox remains.
- KME/TBE is handled separately at `statistical_region × issue_week` with an eight-week horizon.
- ERA5-Land weather is a core, separate ablation layer. Its source `valid_time` is the retrospective cutoff; features use only completed weeks before `issue_week`, and weather is never extrapolated or synthesized after the verified source cutoff.
- The documented 2026 GURS municipality zones are the same fixed analytical zones for every model year.

The active public product uses a no-current-cases Lyme proxy and a separate KME
regional model. Fresh DWD ICON weather obtained through Open-Meteo is displayed
as a separate seven-day local context; it is not fed into either score. The
operational contract is documented in
[OPERATIONAL_OPEN_METEO_WEATHER.md](OPERATIONAL_OPEN_METEO_WEATHER.md), and the
model evidence in [PRECAUTION_PROXY_MODEL.md](PRECAUTION_PROXY_MODEL.md).
