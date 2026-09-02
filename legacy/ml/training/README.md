# Učenje modela

Ta mapa vsebuje reproducibilen CatBoost trening za občinsko-časovne podatkovne
nabore. Privzeta logika je prilagojena tabularnim podatkom po načelu:

- ena vrstica predstavlja eno lokacijo in en časovni trenutek
- ciljna spremenljivka je v enem stolpcu
- časovni split vedno poteka po unikatnih časih, ne po naključnih vrsticah

## Kaj omogoča pipeline

- JSON konfiguracijo za trening
- validacijo vhodne CSV sheme
- samodejni ali eksplicitni izbor značilk
- podporo za numerične in kategorične značilke
- časovno urejen split `train / validation / test`
- izvoz modela, metapodatkov in holdout napovedi
- opcijsko uteževanje vrstic prek `sample_weight`

## Namestitev

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r ml/training/requirements.txt
```

## Hiter zagon

1. Pripravi vhodni CSV, na primer v `data/processed/training/`.
2. Izberi ali prilagodi konfiguracijo:
   - [example_config.json](example_config.json)
   - [example_weekly_config.json](example_weekly_config.json)
   - [example_tick_borne_lyme_config.json](example_tick_borne_lyme_config.json)
   - [example_tick_borne_kme_config.json](example_tick_borne_kme_config.json)
   - [example_tick_borne_kme_v2_config.json](example_tick_borne_kme_v2_config.json)
3. Najprej preveri shemo in split:

```bash
python3 -m ml.training.train --config ml/training/example_config.json --validate-only
```

4. Nato zaženi trening:

```bash
python3 -m ml.training.train --config ml/training/example_config.json
```

## Tipični vhodni stolpci

Obvezni:

- časovni stolpec, na primer `time`
- ciljna spremenljivka, na primer `target_risk_score`

Pogosti identifikatorji:

- `obcina_sifra`
- `obcina_naziv`

Pogoste numerične značilke:

- `air_temperature_c`
- `relative_humidity_pct`
- `precipitation_hourly_mm`
- `soil_temperature_level_1_c`
- `soil_water_layer_1_m3_m3`

Pogoste kategorične značilke:

- `obcina_sifra`
- `obcina_naziv`
- `assignment_method`

## Izhodi

Privzeti izhodni direktorij vsebuje:

- `model.cbm`: naučen CatBoost model
- `metadata.json`: konfiguracija, split, metrike in pomembnost značilk
- `holdout_predictions.csv`: napovedi za `validation` in `test`

## Trenutni referenčni modeli

### Borelioza

Od `2026-04-10` je uradni baseline za boreliozo:

- model: `catboost_tick_borne_lyme_v1`
- konfiguracija: [example_tick_borne_lyme_config.json](example_tick_borne_lyme_config.json)
- artefakti: `data/processed/training/catboost_tick_borne_lyme_v1/`
- metodološki zapis: [../../docs/metodologija/borelioza-baseline-v1.md](../../docs/metodologija/borelioza-baseline-v1.md)

To je trenutni referenčni model za vse naslednje iteracije borelioze.

### KME

Za KME je trenutno priporočena bolj konzervativna smer `v2`:

- target: `target_kme_presence`
- tip problema: `binary_classification`
- konfiguracija: [example_tick_borne_kme_v2_config.json](example_tick_borne_kme_v2_config.json)
- analiza: [../../docs/metodologija/kme-v2-analiza.md](../../docs/metodologija/kme-v2-analiza.md)

Ta konfiguracija uporablja manj značilk, strožjo regularizacijo in uravnoteženje
razredov, zato je primernejša za redek KME signal.
