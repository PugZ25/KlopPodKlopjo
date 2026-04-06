# Copernicus

V tej mapi hranimo originalne prenose iz Copernicus Climate Data Store.

## ERA5-Land za Slovenijo

- vir: ERA5-Land hourly data from 1950 to present
- dataset ID: `reanalysis-era5-land`
- območje: Slovenija, bbox `46.9 13.3 45.3 16.6` v vrstnem redu `north west south east`
- surove datoteke: `data/raw/copernicus/era5land_slovenia/hourly/*.nc`
- manifest prenosa: `data/raw/copernicus/era5land_slovenia/manifest.json`

Pravilo:
- `.nc` datotek v tej mapi ne popravljamo ročno
- izpeljane spremenljivke, kot je relativna vlaga, sodijo v `data/interim/features/`

Prenos se izvede s skripto:

```bash
python3 scripts/data/copernicus/download_era5land_slovenia.py
```

## Copernicus DEM za Slovenijo

- vir: Copernicus DEM prek Copernicus Data Space Sentinel Hub Process API
- uradna zbirka: `https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM`
- uradna DEM API dokumentacija: `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html`
- avtentikacija: `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html`
- privzeti DEM: `COPERNICUS_30`
- privzeti izhod: `EPSG:3794`, ortometrične višine, 30 m
- območje: Slovenija, bbox `46.9 13.3 45.3 16.6` v vrstnem redu `north west south east`
- surove ploščice: `data/raw/copernicus/copernicus_dem_slovenia/tiles/*.tif`
- manifest prenosa: `data/raw/copernicus/copernicus_dem_slovenia/manifest.json`

Prenos se izvede s skripto:

```bash
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py
```
