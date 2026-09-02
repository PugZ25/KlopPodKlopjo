# Static municipality geography

This stage creates one verified static descriptor: `municipality_area_km2`.
No weather, elevation, land-cover, epidemiological outcome, target, prediction,
or 2025 lockbox value is read or created.

## Source and version

- Source: Geodetic Administration of the Republic of Slovenia (GURS), GeoHub
  municipality layer `TEMELJNE_VSEBINE/GH_Prostorske_enote/MapServer/1530`.
- Raw file: `data/raw/gurs/obcine-gurs-rpe.geojson`.
- Documented download date: `2026-04-04`.
- Export CRS: `EPSG:4326`.
- Municipality key: GURS `SIFRA`, formatted as a three-character code and
  required to match the canonical municipality dimension exactly.

The feature is the absolute geodesic polygon area on the WGS84 ellipsoid,
converted from square metres to square kilometres. Polygon holes are
subtracted and multipolygon parts would be summed. The raw `GEOM_AREA`
attribute is not used because its unit is not stated in active source
documentation. Missing, invalid, nonpositive, unmatched, or duplicate geometry
causes the build to fail; no value is imputed.

This is a static descriptor of the documented GURS snapshot. By explicit
project rule, these same 212 zones are the analytical municipalities for every
model year. The pipeline does not reconstruct time-varying historical
boundaries and does not interpret the geometry as a time-varying measurement.

## Excluded candidates

- Land cover is excluded because the stored CLC2018 package does not match the
  currently documented CLMS yearly-v3 download layout and has no matching
  manifest in the expected location.
- Elevation is excluded from this minimal ablation because municipality zonal
  processing would require an additional raster stack; it is not needed to
  establish the first static-geography comparison.
- SURS density is excluded because the active documentation does not establish
  the density unit and download provenance needed for a defensible area
  reconstruction.

## Reproduction

```bash
./.venv/bin/python -B -m model_v3.features.static_geography \
  --config model_v3/config/static_geography.json
```

Outputs are written to `model_v3/outputs/static_geography/`.
