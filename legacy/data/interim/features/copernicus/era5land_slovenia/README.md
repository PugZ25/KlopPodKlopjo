# ERA5-Land Slovenia Features

Ta mapa vsebuje izpeljane mesečne NetCDF datoteke za projektne značilke, pripravljene iz ERA5-Land surovih podatkov.

Lokacija:
- `data/interim/features/copernicus/era5land_slovenia/hourly/*.nc`

Glavne spremenljivke:
- `air_temperature_c`
- `relative_humidity_pct`
- `precipitation_hourly_mm`
- `soil_temperature_level_1_c`
- `soil_temperature_level_2_c`
- `soil_water_layer_1_m3_m3`
- `soil_water_layer_2_m3_m3`

Opombe:
- relativna vlaga je izračunana iz `2m_temperature` in `2m_dewpoint_temperature`
- padavine so deakumulirane iz ERA5-Land `total_precipitation` in pretvorjene v milimetre
