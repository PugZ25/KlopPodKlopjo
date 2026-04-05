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

## Namestitev

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r ml/training/requirements.txt
```

## Hiter zagon

1. Pripravite CSV datoteko, na primer v `data/processed/training/`.
2. Kopirajte ali prilagodite [example_config.json](/Users/zankespert/Desktop/KlopPodKlopjo/ml/training/example_config.json).
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

## Opombe

- Trenutni scaffold podpira `regression` in `binary_classification`.
- Za vas projekt je za prvi produkcijski model se vedno najbolj smiseln `regression`, nato pa pragove pretvorite v `Nizko / Srednje / Visoko`.
- Ce vhodni podatki se nimajo NIJZ ciljne spremenljivke, lahko isti pipeline najprej uporabljate z internim `risk score` targetom.
