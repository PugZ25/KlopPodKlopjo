# Skripti

`scripts/` vsebuje manjše pomožne skripte, ki ne sodijo v glavni aplikacijski ali modelni tok.

- `data/`: pomožna opravila za podatke
- `dev/`: razvojna opravila

Za live deployment sta trenutno pomembni skripti:

- `scripts/data/build_municipality_boundary_asset.py`: izdela `frontend/public/municipality-boundaries.json` za browser-side lookup občine
- `scripts/data/build_live_municipality_risk_frontend_data.py`: izdela `frontend/src/data/liveMunicipalityRisk.ts` za build-time live snapshot

Celoten deploy workflow je opisan v
[docs/live-deployment.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/live-deployment.md).

Za Copernicus `.nc` datoteke je na voljo pregledovalnik v [scripts/data/copernicus/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/scripts/data/copernicus/README.md).

Za SURS občinske podatke o prebivalstvu in gostoti prebivalcev so skripte opisane v [scripts/data/surs/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/scripts/data/surs/README.md).

Za zagon CatBoost treninga na ARNES SLING je pripravljena mapa [scripts/hpc/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/scripts/hpc/README.md).
