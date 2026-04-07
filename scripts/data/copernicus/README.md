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

## Prenos Copernicus DEM za Slovenijo

Glavna skripta:

```bash
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py
```

Ta skripta:
- uporablja uradni Copernicus Data Space Sentinel Hub Process API
- privzeto prenese `COPERNICUS_30` za območje Slovenije
- izvozi višine v `EPSG:3794` pri 30 m ločljivosti
- zaradi omejitve sinhronega Process API (`2500 x 2500` px) samodejno razreže izvoz na več GeoTIFF ploščic
- shrani ploščice v `data/raw/copernicus/copernicus_dem_slovenia/tiles/`
- zapiše `manifest.json` z bbox, CRS, ločljivostjo in seznamom ploščic

Pred zagonom nastavi bodisi veljaven bearer token bodisi OAuth odjemalca za Copernicus Data Space:

```bash
export CDSE_ACCESS_TOKEN='<your bearer token>'
```

ali:

```bash
export CDSE_CLIENT_ID='<your client id>'
export CDSE_CLIENT_SECRET='<your client secret>'
```

Uporabni primeri:

```bash
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py --dry-run
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py --dem-instance COPERNICUS_90
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py --build-vrt
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py --resolution-m 20 --max-tile-size 2000
```

Opombi:
- Copernicus DEM je digitalni model površja, ne bare-earth DTM.
- `--build-vrt` zahteva ukaz `gdalbuildvrt`; brez njega skripta še vedno prenese vse GeoTIFF ploščice.

## Prenos CLMS land cover za Slovenijo

Glavna skripta:

```bash
python3 scripts/data/copernicus/download_clms_land_cover_slovenia.py
```

Ta skripta:
- uporablja uradni Copernicus Data Space Sentinel Hub Process API
- cilja CLMS global land cover `100 m yearly v3`
- privzeto prenese zadnje uradno leto tega produkta, to je `2019`
- izvozi rastrske pasove za Slovenijo v `EPSG:3794`
- shrani GeoTIFF ploščice v `data/raw/copernicus/clms_land_cover_slovenia/tiles/`
- zapiše `manifest.json` z bbox, CRS, letom, pasovi in seznamom ploščic

Pred zagonom nastavi OAuth odjemalca za Copernicus Data Space:

```bash
export CDSE_CLIENT_ID='<your client id>'
export CDSE_CLIENT_SECRET='<your client secret>'
```

Uporabni primeri:

```bash
python3 scripts/data/copernicus/download_clms_land_cover_slovenia.py --dry-run
python3 scripts/data/copernicus/download_clms_land_cover_slovenia.py --year 2018
python3 scripts/data/copernicus/download_clms_land_cover_slovenia.py --build-vrt
python3 scripts/data/copernicus/download_clms_land_cover_slovenia.py --force
```

Opombe:
- to je surov rastrski prevzem; občinskih agregatov ali modelskih stolpcev ta korak še ne pripravi
- ta produkt je metodološko dober za poznejše preproste deleže, kot so `tree`, `grass`, `shrub` in `crops`

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

## Obcinski DEM feature pipeline

Ko imas prenesen Copernicus DEM in GURS GeoJSON z obcinami, lahko zgradis
obcinske statične visinske značilke:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_dem_features.py
```

Privzeti izhodi:
- `data/interim/features/copernicus/copernicus_dem_slovenia/obcina_dem_tile_coverage.csv`
- `data/processed/training/obcina_dem_features.csv`
- `data/processed/training/obcina_dem_features_manifest.json`

Ta korak:
- iz `manifest.json` in DEM GeoTIFF ploščic prebere layout rastra
- iz GeoJSON prebere poligone občin
- za vsako občino iz DEM pikslov izračuna pokritost in višinske statistike
- zapiše občina x DEM-tile coverage CSV za pregled
- pripravi občinske DEM feature vrstice za nadaljnjo združitev z drugimi značilkami

Uporabni primeri:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_dem_features.py --limit-obcine 5
./.venv/bin/python scripts/data/copernicus/build_obcina_dem_features.py --obcina-sifre 061,062,064
```

## Zdruzen tedenski weather + DEM CSV

Ko imas pripravljena oba občinska izhoda, lahko DEM višinske značilke pripneš na
tedenske vremenske značilke v novo datoteko:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_weekly_weather_dem_features.py
```

Ta korak v novo CSV doda:
- `elevation_m_mean`
- `elevation_m_std`
- `elevation_m_range`

Privzeti izhodi:
- `data/processed/training/obcina_weekly_weather_dem_features.csv`
- `data/processed/training/obcina_weekly_weather_dem_features_manifest.json`

## Obcinski CLC land-cover feature pipeline

Ko imas v `data/raw/copernicus/clms_land_cover_slovenia/` razpakiran
CLC 2018 raster `100 m`, lahko pripraviš občinske statične značilke rabe tal:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_clc_features.py
```

Ta korak:
- prebere surovi CLC GeoTIFF in njegov raster attribute table `.vat.dbf`
- poligone občin pretvori v `EPSG:3035`
- po metodi `pixel_center_mask` občinam pripiše CLC piksle
- izvozi preproste občinske deleže, npr. `forest_cover_pct`, `grassland_pasture_cover_pct`, `shrub_transitional_cover_pct`

Privzeti izhodi:
- `data/interim/features/copernicus/clms_land_cover_slovenia/obcina_clc_sampling.csv`
- `data/processed/training/obcina_clc_features.csv`
- `data/processed/training/obcina_clc_features_manifest.json`

Uporabni primeri:

```bash
./.venv/bin/python scripts/data/copernicus/build_obcina_clc_features.py --limit-obcine 5
./.venv/bin/python scripts/data/copernicus/build_obcina_clc_features.py --obcina-sifre 001,002,003
```
