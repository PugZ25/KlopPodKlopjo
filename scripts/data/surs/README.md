# SURS

Ta mapa vsebuje skripte za prevzem in pripravo občinskih podatkov iz SURS SiStat.

## Prenos občinskega prebivalstva

Glavna skripta:

```bash
./.venv/bin/python scripts/data/surs/download_obcina_population.py
```

Ta skripta:
- uporablja uradni SURS SiStat API za tabelo `2640010S`
- prenese mero `Population - Total - 1 January`
- shrani surovi `json-stat2` izvoz v `data/raw/surs/obcina_population_sistat.json`

Uporabni primeri:

```bash
./.venv/bin/python scripts/data/surs/download_obcina_population.py --years 2016,2017,2018,2019,2020,2021,2022,2023,2024,2025
./.venv/bin/python scripts/data/surs/download_obcina_population.py --include-slovenia
```

## Letni občinski log-population CSV

Ko imaš surovi JSON izvoz, lahko pripraviš letne občinske značilke:

```bash
./.venv/bin/python scripts/data/surs/build_obcina_population_features.py
```

Privzeti izhodi:
- `data/processed/training/obcina_surs_log_population_yearly_features.csv`
- `data/processed/training/obcina_surs_log_population_yearly_features_manifest.json`

Ta korak:
- pretvori SURS `json-stat2` strukturo v letni občina x leto CSV
- normalizira občinske šifre iz SURS oblike `001` v projektno obliko `1`
- pripravi samo feature `log_population_total = log(1 + population_total)`
