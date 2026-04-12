# Ucenje modela

Ta mapa vsebuje prvi ponovljiv scaffold za ucenje modela tveganja s `CatBoost`.

Scaffold je namenjen tabularnim podatkom po nacelu:
- ena vrstica = ena lokacija in en casovni trenutek
- ciljna spremenljivka je v enem stolpcu
- casovni split vedno poteka po unikatnih casih, ne po nakljucnih vrsticah

## Kaj je pripravljeno

- JSON konfiguracija za ucenje
- validacija sheme vhodne CSV datoteke
- avtomatski izbor znacilk ali eksplicitni seznam znacilk
- podpora za numericne in kategoricne znacilke
- casovno urejen split `train / validation / test`
- izvoz modela, metapodatkov in holdout napovedi
- opcijska podpora za `sample_weight` iz dodatnega numericnega stolpca

## Namestitev

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r ml/training/requirements.txt
```

## Hiter zagon

1. Pripravite CSV datoteko, na primer v `data/processed/training/`.
2. Kopirajte ali prilagodite [example_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_config.json).
   Za tedenski obcinski weather pipeline lahko uporabite tudi
   [example_weekly_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_weekly_config.json).
   Za koncni zdruzeni dataset za boreliozo in KME sta pripravljena tudi
   [example_tick_borne_lyme_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_tick_borne_lyme_config.json)
   in
   [example_tick_borne_kme_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_tick_borne_kme_config.json).
   Za redek KME target je priporocena novejsa klasifikacijska konfiguracija
   [example_tick_borne_kme_v2_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_tick_borne_kme_v2_config.json).
3. Najprej preverite samo shemo in split:

```bash
python3 -m ml.training.train --config ml/training/example_config.json --validate-only
```

4. Nato zazeni ucenje:

```bash
python3 -m ml.training.train --config ml/training/example_config.json
```

## Priakovani vhodni stolpci

Obvezni stolpci:
- casovni stolpec, npr. `time`
- ciljna spremenljivka, npr. `target_risk_score`

Tipicni identifikatorji:
- `obcina_sifra`
- `obcina_naziv`

Tipicne numericne znacilke:
- `air_temperature_c`
- `relative_humidity_pct`
- `precipitation_hourly_mm`
- `soil_temperature_level_1_c`
- `soil_water_layer_1_m3_m3`

Tipicne kategoricne znacilke:
- `obcina_sifra`
- `obcina_naziv`
- `assignment_method`

## Izhodi

Privzeti izhodni direktorij iz konfiguracije vsebuje:
- `model.cbm`: CatBoost model
- `metadata.json`: metapodatki o konfiguraciji, splitu, metrikah in pomembnosti znacilk
- `holdout_predictions.csv`: napovedi za `validation` in `test`

## Trenutni uradni baseline

Od `2026-04-10` je uradni baseline za boreliozo:

- `catboost_tick_borne_lyme_v1`
- konfiguracija: [example_tick_borne_lyme_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_tick_borne_lyme_config.json)
- artifacts: `data/processed/training/catboost_tick_borne_lyme_v1/`
- metodoloski zapis: [borelioza-baseline-v1.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/borelioza-baseline-v1.md)

To je trenutni `model to beat` za vse naslednje iteracije borelioze.

## KME v2

Za KME je priporocen `v2` pristop:

- target: `target_kme_presence`
- problem type: `binary_classification`
- konfiguracija: [example_tick_borne_kme_v2_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_tick_borne_kme_v2_config.json)
- analiza: [kme-v2-analiza.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/kme-v2-analiza.md)

Ta konfiguracija je namenoma bolj konzervativna:

- uporablja manj znacilk kot `kme v1`
- zmanjsa globino dreves
- poveca regularizacijo
- vklopi `auto_class_weights=Balanced` zaradi zelo malo pozitivnih primerov
- dodatno utezi vrstice po oceni velikosti populacije obcine prek `sample_weight`

Trenutna interpretacija `KME v2`:

- uporaben je za `risk ranking` in `Nizko / Srednje / Visoko`
- ni se dovolj dober kot neposreden probability model

## Opombe

- Trenutni scaffold podpira `regression` in `binary_classification`.
- `sample_weight` lahko uporabite za utezevanje vrstic brez tega, da bi isti signal
  dodajali med featureje ali target.
- Za vas projekt je za prvi produkcijski model se vedno najbolj smiseln `regression`, nato pa pragove pretvorite v `Nizko / Srednje / Visoko`.
- Ce vhodni podatki se nimajo NIJZ ciljne spremenljivke, lahko isti pipeline najprej uporabljate z internim `risk score` targetom.
- Za zdruzeni dataset z NIJZ targeti uporabite
  `data/processed/training/obcina_weekly_tick_borne_catboost_ready.csv`.
