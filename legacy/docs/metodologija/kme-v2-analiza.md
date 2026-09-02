# KME V2 Analiza

Ta dokument formalizira trenutno oceno modela `KME v2`.

## Status

- status: `evaluated`
- bolezen: `KME`
- model_id: `catboost_tick_borne_kme_presence_v2`
- datum ocene: `2026-04-10`
- priporocena raba: `demo risk ranking`
- ni sprejet kot produkcijski probability model

## Kaj tocno je model

Model je CatBoost klasifikator za redek dogodek:

- target: `target_kme_presence`
- problem type: `binary_classification`
- konfiguracija: `ml/training/example_tick_borne_kme_v2_config.json`
- dataset: `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`
- artifacts: `data/processed/training/catboost_tick_borne_kme_presence_v2/`

Glavni artifacts:

- `model.cbm`
- `metadata.json`
- `holdout_predictions.csv`

## Metodologija validacije

Analiza temelji na naslednjih virih:

- `data/processed/training/catboost_tick_borne_kme_presence_v2/metadata.json`
- `data/processed/training/catboost_tick_borne_kme_presence_v2/holdout_predictions.csv`
- `ml/training/example_tick_borne_kme_v2_config.json`
- `pipelines/features/obcina_weekly_tick_borne_catboost.py`

Validacija ohrani isti casovni split kot ostali glavni modeli:

- train: `2016-04-04` do `2023-01-16`
- validation: `2023-01-23` do `2024-07-01`
- test: `2024-07-08` do `2025-12-22`

To je metodolosko pravilen split za napovedovanje, ker:

- se prihodnost ne mesa v preteklost
- se vsi glavni poskusi primerjajo na istih holdout obdobjih
- epidemioloski lagi uporabljajo samo pretekle tedne `t-1 ... t-k`

Za KME feature engineering uporablja:

- prostorske in vremenske znacilke
- demografske znacilke
- epidemioloske lage `kme_cases_lag_2w` in `kme_cases_prev_8w_sum`
- dodatne lage borelioze `lyme_cases_lag_2w` in `lyme_cases_prev_4w_sum`

Pomembna metodoloska opomba:

- to ni cist okoljski model
- model uporablja tudi preteklo epidemiolosko zgodovino

## Porocane metrike iz artifactov

Pozitivni razred je zelo redek:

- validation positive rate: `0.006765`
- test positive rate: `0.006984`

Metrike, ki jih trenutni pipeline izvozi pri pragu `0.5`:

### Validation

- accuracy: `0.8172`
- precision: `0.0267`
- recall: `0.7339`
- F1: `0.0515`

### Test

- accuracy: `0.8006`
- precision: `0.0262`
- recall: `0.7632`
- F1: `0.0507`

Interpretacija:

- model pri pragu `0.5` zazna velik del pozitivnih tednov
- hkrati oznaci prevec laznih pozitivnih primerov
- accuracy pri tem problemu ni uporabna glavna metrika

Trivialni baseline `vedno 0` doseze:

- validation accuracy: `0.9932`
- test accuracy: `0.9930`

To pomeni, da accuracy pri tako redkem targetu zavaja in ne sme biti glavna metrika za predstavitev.

## Dodatna analiza holdout napovedi

Iz `holdout_predictions.csv` je bila dodatno izracunana rangirna in kalibracijska analiza.

### ROC AUC in PR-AUC

Validation:

- ROC AUC: `0.8481`
- PR-AUC: `0.1013`

Test:

- ROC AUC: `0.8792`
- PR-AUC: `0.0665`

Interpretacija:

- model ima uporaben rangirni signal
- pozitivni primeri so v povprecju postavljeni visje od negativnih
- zaradi zelo nizke prevalence je PR-AUC bolj posten pokazatelj od accuracy

### Top-k signal

Za najbolj tvegane vrstice po napovedi:

Validation:

- top 20 precision: `0.3500` (`7 / 20`)
- top 1% precision: `0.1366`
- lift proti bazi: `20.2x`

Test:

- top 20 precision: `0.1500` (`3 / 20`)
- top 1% precision: `0.1104`
- lift proti bazi: `15.8x`

Interpretacija:

- najvisje rangirani primeri so bistveno bogatejsi s pozitivnimi primeri kot povprecje
- to je dober signal za risk ranking ali izpostavljanje hotspotov

### Kalibracija

Povprecna napovedana verjetnost je mocno previsoka:

- validation mean predicted probability: `0.2897`
- validation real positive rate: `0.0068`
- validation calibration ratio: `42.8x`

- test mean predicted probability: `0.3017`
- test real positive rate: `0.0070`
- test calibration ratio: `43.2x`

Interpretacija:

- surove izhodne verjetnosti niso dobro kalibrirane
- model ni primeren za neposredno razlago v smislu "verjetnost KME je 30 %"
- izhod je primernejsi kot relativni score, ne kot dobesedna verjetnost

## Pragovi

Pri privzetem pragu `0.5` model favorizira recall.

Grob pregled pragov pokaze, da se F1 izboljsa sele pri precej visjem pragu:

- validation best F1 v grobem pregledu: prag `0.86`, F1 `0.1896`
- test best F1 v grobem pregledu: prag `0.85`, F1 `0.1379`

To spremlja drug tradeoff:

- validation precision `0.1961`, recall `0.1835`
- test precision `0.1224`, recall `0.1579`

Pomen:

- za frontend ali demo je bolj smiselna pretvorba v `Nizko / Srednje / Visoko`
- en sam privzeti prag `0.5` ni dober poslovni ali predstavitveni default

## Kaj model dejansko uporablja

Med najpomembnejsimi znacilkami so:

- `log_population_total`
- `soil_temperature_level_2_c_mean`
- `elevation_m_mean`
- `air_temperature_c_mean_rolling_4w_mean`
- `mixed_forest_cover_pct`
- `lyme_cases_prev_4w_sum`
- `kme_cases_prev_8w_sum`

Pomen:

- signal ni samo sezonski ali samo epidemioloski
- model uporablja kombinacijo lokacije, okolja in pretekle pojavnosti
- vseeno ne smete trditi, da model temelji izkljucno na vremenu in okolju

## Glavne ugotovitve

1. `KME v2` je bistveno bolj smiselna formulacija kot `KME v1` regresija za redek target.
2. Model ima uporaben rangirni signal, zato je primeren za risk bands in hotspot demo.
3. Model ni dobro kalibriran, zato ni primeren za neposredno porocanje surovih verjetnosti.
4. Accuracy je pri tem problemu zavajajoca in ne sme biti glavna metrika za zirijo.
5. Model uporablja tudi epidemioloske lage, zato ni posten opis, da gre za cisto okoljsko napoved.

## Priporocilo za hackathon predstavitev

`KME v2` je validen za hackathon, ce ga predstavite posteno kot:

- prototip za zaznavanje relativno bolj tveganih `obcina-teden` kombinacij
- sistem za razvrscanje v `Nizko / Srednje / Visoko`
- podporni signal za geografski prikaz tveganja

Ni pa validno trditi:

- da model napoveduje tocno verjetnost KME
- da je score neposredno epidemiolosko kalibriran
- da model dela samo iz okoljskih podatkov

## Odlocitev

Trenutna odlocitev za projekt je:

- `KME v2` ostane priporocen demo model za klasifikacijski risk ranking
- ni se sprejet kot uradni produkcijski baseline
- za nadaljnje iteracije je treba dodati vsaj `ROC AUC`, `PR-AUC` in kalibracijsko analizo v sam pipeline
