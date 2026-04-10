# Borelioza Baseline V1

Ta dokument formalno zaklene prvi uradni baseline model za boreliozo.

## Status

- status: `accepted`
- bolezen: `borelioza`
- baseline_id: `catboost_tick_borne_lyme_v1`
- datum potrditve: `2026-04-10`
- izvor zagona: `slurm-klop-catboost-66057321.out`

## Kaj tocno je baseline

Uradni baseline je CatBoost regresijski model za:

- target: `target_lyme_cases`
- konfiguracija: `ml/training/example_tick_borne_lyme_config.json`
- dataset: `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`
- artifacts: `data/processed/training/catboost_tick_borne_lyme_v1/`

Glavni artifacts:

- `model.cbm`
- `metadata.json`
- `holdout_predictions.csv`

## Referencni split

Vsi prihodnji poskusi za boreliozo se morajo primerjati na istem casovnem splitu:

- train: `2016-04-04` do `2023-01-16`
- validation: `2023-01-23` do `2024-07-01`
- test: `2024-07-08` do `2025-12-22`

Nakljucni split ni primerljiv s tem baseline modelom in se ne sme uporabljati za glavno porocanje rezultatov.

## Referencne metrike

Na ravni obcina-teden:

- validation: `RMSE 0.5893`, `MAE 0.3454`, `R² 0.6825`
- test: `RMSE 0.7253`, `MAE 0.4020`, `R² 0.6630`

Na ravni tedenskih agregatov po Sloveniji:

- validation weekly: `R² 0.624`, korelacija `0.962`
- test weekly: `R² 0.854`, korelacija `0.931`

## Interpretacija baseline modela

Ta baseline je dovolj dober, da ga uporabimo kot:

- prvi uradni model za primerjavo prihodnjih iteracij
- prvi referencni model za demonstracijo borelioze
- osnovo za pretvorbo napovedi v razrede tveganja

Pomembna omejitev:

- model je mocno podprt z epidemioloskimi lag znacilkami in sezonskostjo
- to pomeni, da je trenutno predvsem dober napovedni baseline, ne se koncni razlagalni model okoljskega tveganja

## Pravilo za prihodnje iteracije

Nov model za boreliozo lahko preglasi `baseline v1` samo, ce:

- uporablja isti ali metodolosko strozji casovni split
- je ovrednoten na istih holdout obdobjih
- poroca vsaj `RMSE`, `MAE`, `R²`
- dodatno poroca rezultate na tedenskih agregatih
- na testnem delu verodostojno izboljsa `v1` ali prinese pomembno metodolosko prednost

Dokler to ni izpolnjeno, ostane uradni baseline:

- `data/processed/training/catboost_tick_borne_lyme_v1/`
