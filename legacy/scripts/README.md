# Skripti

`scripts/` vsebuje operativne skripte, ki podpirajo pripravo podatkov, generiranje
frontend artefaktov in občasne raziskovalne ali infrastrukturne naloge.

## Najpomembnejši skripti za demo

- `scripts/data/build_municipality_boundary_asset.py`
  izdela `frontend/public/municipality-boundaries.json` za geolokacijski lookup občine
- `scripts/data/build_live_municipality_risk_frontend_data.py`
  izdela `frontend/src/data/liveMunicipalityRisk.ts` za build-time live snapshot

Celoten postopek objave live dema je opisan v
[../docs/live-deployment.md](../docs/live-deployment.md).

## Dodatni sklopi

- [data/copernicus/README.md](data/copernicus/README.md): Copernicus prenos in pregled `.nc` datotek
- [data/surs/README.md](data/surs/README.md): SURS občinski podatki o prebivalstvu in gostoti
- [hpc/README.md](hpc/README.md): zagon treninga na ARNES SLING
