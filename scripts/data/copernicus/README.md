# Copernicus NetCDF

Ta mapa vsebuje orodja za Copernicus / ERA5-Land datoteke za Slovenijo.

## Namestitev odvisnosti

```bash
python3 -m pip install -r scripts/data/copernicus/requirements.txt
```

## Prenos ERA5-Land za Slovenijo

Glavna skripta:

```bash
python3 scripts/data/copernicus/download_era5land_slovenia.py
```

Privzeto skripta:
- prenese ERA5-Land hourly podatke za območje Slovenije
- vzame zadnjih 10 let od najnovejšega razpoložljivega dne
- shrani surove mesečne `.nc` datoteke v `data/raw/copernicus/era5land_slovenia/hourly/`
- izračuna projektne značilke in jih shrani v `data/interim/features/copernicus/era5land_slovenia/hourly/`

Uporabni primeri:

```bash
python3 scripts/data/copernicus/download_era5land_slovenia.py --dry-run
python3 scripts/data/copernicus/download_era5land_slovenia.py --max-months 1
python3 scripts/data/copernicus/download_era5land_slovenia.py --transform-only
python3 scripts/data/copernicus/download_era5land_slovenia.py --end-date 2026-03-30
```

## Pregledovanje `.nc` datotek

Za hitro pregledovanje `.nc` datotek uporabi:

```bash
python3 -m pip install xarray netCDF4
python scripts/data/copernicus/inspect_nc.py path/to/file.nc
```

Primer za dodatne informacije o posamezni spremenljivki:

```bash
python scripts/data/copernicus/inspect_nc.py data/raw/copernicus/era5land_slovenia/hourly/era5land_slovenia_2026_03.nc --variable t2m --stats
```

Skripta izpiše:
- dimenzije
- koordinate
- spremenljivke in njihove tipe
- globalne atribute
- podrobnosti in osnovno statistiko za izbrano spremenljivko

## Obcinski tedenski feature pipeline

Ko imas monthly feature `.nc` datoteke in GURS GeoJSON z obcinami, lahko zgradis
obcinske dnevne in tedenske znacilke z area-weighted polygon overlay pristopom:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_weekly_features.py
```

Privzeti izhodi:
- `data/interim/features/copernicus/era5land_slovenia/obcina_grid_overlay.csv`
- `data/interim/features/copernicus/era5land_slovenia/obcina_daily_weather.csv`
- `data/processed/training/obcina_weekly_weather_features.csv`
- `data/processed/training/obcina_weekly_weather_features_manifest.json`

Ta korak:
- iz ERA5-Land mreze zgradi dejanske poligone grid celic
- iz GeoJSON prebere poligone obcin
- za vsako obcino izracuna preseke `obcina x grid-celica`
- uporabi preseke kot utezi za agregacijo vremenskih spremenljivk
- pripravi tedenske znacilke in lag/rolling stolpce za model

Uporabni primeri:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_weekly_features.py --limit-files 1 --keep-partial-weeks
./.venv/bin/python scripts/data/copernicus/build_obcina_weekly_features.py --start-date 2019-01-01 --end-date 2019-12-31
```
