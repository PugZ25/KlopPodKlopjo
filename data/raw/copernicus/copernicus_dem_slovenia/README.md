# Copernicus DEM Slovenia Raw

Ta mapa je cilj za reproducibilen prevzem Copernicus DEM za območje Slovenije.

- vir zbirke: `https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM`
- DEM API dokumentacija: `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html`
- OAuth avtentikacija: `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html`
- zadnje preverjeno: `2026-04-06`

Privzeti projektni izvoz:
- DEM instanca: `COPERNICUS_30`
- izhodni CRS: `EPSG:3794`
- višine: ortometrične
- ločljivost: `30 m`
- vhodni bbox: `46.9 13.3 45.3 16.6` v vrstnem redu `north west south east`

Po uspešnem zagonu skripte se pojavijo:
- `tiles/*.tif`
- `manifest.json`
- opcijsko `copernicus_dem_slovenia_*.vrt`

Skripta za prevzem:

```bash
python3 scripts/data/copernicus/download_copernicus_dem_slovenia.py
```

Opombe:
- zaradi omejitve Process API se Slovenija izvozi v več GeoTIFF ploščicah
- Copernicus DEM je digitalni model površja (DSM), zato vključuje tudi vegetacijo in infrastrukturo
- natančen datum posameznega prevzema se zapiše v `manifest.json`
