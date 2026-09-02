# Live Snapshot Reference Assets

Ta mapa hrani majhen, namensko verzioniran asset pack za tedensko osveževanje
`frontend/src/data/liveMunicipalityRisk.ts` brez lokalnega dostopa do
`data/raw/` in `data/processed/`.

## Kaj je notri

- `municipality_coordinates.json`: reprezentativne točke občin za Open-Meteo poizvedbe
- `municipality_static_features.json`: statične občinske značilke, ki jih live snapshot potrebuje za env_v2 modele
- `catboost_tick_borne_*_env_v2/`: model `.cbm`, `metadata.json` in skrčena `holdout_values.json` distribucija
- `manifest.json`: kratek opis izvora in sestave paketa

## Kako se osveži

Paket se zgradi iz trenutnih lokalnih artefaktov z:

```bash
python3 scripts/data/build_live_snapshot_reference_assets.py
```

To je treba pognati, kadar se spremeni vsaj eno od naslednjega:

- env_v2 model (`model.cbm`)
- `holdout` distribucija ali `metadata.json`
- statični feature kontrakt modela
- logika izbire reprezentativne točke občine

Ko je paket osvežen in commitan, lahko tedenski GitHub workflow osvežuje live
snapshot brez tvoje lokalne mašine.
