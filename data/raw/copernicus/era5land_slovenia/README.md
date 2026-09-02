# ERA5-Land Slovenia Raw

Ta mapa je cilj za surove mesečne NetCDF prenose ERA5-Land za območje Slovenije.

Ta zgodovinski NetCDF tok ostaja vhod za zamrznjeni retrospektivni model.
Operativni tok uporablja GRIB, da ohrani oznako `expver`, in piše nespremenljive
prenose v `data/raw/copernicus/era5land_operational/retrievals/`; glej
`model_v3/OPERATIONAL_ERA5_LAND.md`.

Ko prenos steče do konca, se pojavijo:
- `hourly/era5land_slovenia_YYYY_MM.nc`
- `manifest.json`

Datoteke v tej mapi ostanejo v izvorni Copernicus obliki. Izpeljane značilke za projekt gredo v:
- `data/interim/features/copernicus/era5land_slovenia/`
