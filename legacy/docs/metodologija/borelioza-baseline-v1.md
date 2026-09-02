# Borelioza Baseline V1

Ta dokument formalno potrjuje prvi uradni baseline model za boreliozo.

## Status

- status: `accepted`
- bolezen: `borelioza`
- baseline_id: `catboost_tick_borne_lyme_v1`
- datum potrditve: `2026-04-10`
- izvor potrditve: rezultati prvega uspešnega SLING treninga in pripadajoči artefakti

## Kaj je baseline

Uradni baseline je CatBoost regresijski model za:

- target: `target_lyme_cases`
- konfiguracija: `ml/training/example_tick_borne_lyme_config.json`
- dataset: `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`
- artefakti: `data/processed/training/catboost_tick_borne_lyme_v1/`

Ključni izhodi:

- `model.cbm`
- `metadata.json`
- `holdout_predictions.csv`

## Referenčni split

Vsi prihodnji poskusi za boreliozo se morajo primerjati na istem časovnem splitu:

- train: `2016-04-04` do `2023-01-16`
- validation: `2023-01-23` do `2024-07-01`
- test: `2024-07-08` do `2025-12-22`

Naključni split ni primerljiv s tem baseline modelom in se ne sme uporabljati za
glavno poročanje rezultatov.

## Referenčne metrike

Na ravni `občina x teden`:

- validation: `RMSE 0.5893`, `MAE 0.3454`, `R² 0.6825`
- test: `RMSE 0.7253`, `MAE 0.4020`, `R² 0.6630`

Na ravni tedenskih agregatov po Sloveniji:

- validation weekly: `R² 0.624`, korelacija `0.962`
- test weekly: `R² 0.854`, korelacija `0.931`

## Interpretacija

Ta baseline je dovolj dober, da ga uporabljamo kot:

- prvi uradni primerjalni model za boreliozo
- referenčni model za predstavitev trenutne rešitve
- osnovo za pretvorbo napovedi v razrede tveganja

Pomembna omejitev:

- model se močno opira na epidemiološke lag značilke in sezonskost
- zato je trenutno predvsem dober napovedni baseline, ne pa še končni razlagalni model okoljskega tveganja

## Pravilo za prihodnje iteracije

Nov model za boreliozo lahko preglasi `baseline v1` samo, če:

- uporablja isti ali metodološko strožji časovni split
- je ovrednoten na istih holdout obdobjih
- poroča vsaj `RMSE`, `MAE` in `R²`
- dodatno poroča rezultate na tedenskih agregatih
- na testnem delu verodostojno izboljša `v1` ali prinese jasno metodološko prednost

Dokler to ni izpolnjeno, ostaja uradni baseline:

- `data/processed/training/catboost_tick_borne_lyme_v1/`
