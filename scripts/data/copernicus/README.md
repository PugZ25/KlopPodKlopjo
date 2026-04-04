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
