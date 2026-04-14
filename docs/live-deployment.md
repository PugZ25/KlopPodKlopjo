# Live Deployment

Ta dokument opisuje trenutni produkcijski workflow za live demo.

## Kaj je danes v produkciji

Live deployment je statični React + Vite frontend na Vercelu.

- Vercel konfiguracija je v `vercel.json`
- `installCommand`: `npm ci --prefix frontend`
- `buildCommand`: `npm run build --prefix frontend`
- `outputDirectory`: `frontend/dist`

Produkcija trenutno ne vključuje runtime backenda. Frontend uporablja vnaprej
zgenerirane podatke, ki jih je treba pred objavo osvežiti lokalno.

## Artefakti, ki morajo biti osveženi pred objavo

Pred deployem je treba preveriti vsaj dve datoteki:

- `frontend/src/data/liveMunicipalityRisk.ts`
  zadnji build-time snapshot občinskih score-ov za boreliozo in KME
- `frontend/public/municipality-boundaries.json`
  poenostavljen GURS geolokacijski asset za prepoznavo občine v brskalniku

Če ti datoteki nista osveženi, bo produkcija prikazovala star snapshot.

## Predpogoji

Node del:

- `npm ci --prefix frontend`

Python del za osvežitev live snapshota:

- okolje z nameščenima paketoma `catboost` in `shapely`
- primer: `python3 -m pip install -r ml/training/requirements.txt shapely`

## Priporočen postopek

1. Osveži geolokacijski asset:

```bash
python3 scripts/data/build_municipality_boundary_asset.py
```

2. Osveži live snapshot za frontend:

```bash
python3 scripts/data/build_live_municipality_risk_frontend_data.py --as-of-date YYYY-MM-DD
```

`--as-of-date` je opcijski. Če ga izpustiš, skripta uporabi današnji datum in iz
njega izračuna zadnji zaključeni tedenski snapshot.

3. Preveri produkcijski build:

```bash
npm run build --prefix frontend
```

4. Commitaj osvežena artefakta in jih potisni v vejo, ki jo spremlja Vercel.

## Pomembne omejitve

- live score-i so build-time snapshot, ne runtime izračun
- geolokacija uporabnika teče v brskalniku in uporablja lokalni JSON asset
- produkcija trenutno nima API poti za live inference
- metodološka razlaga live snapshota je v
  [metodologija/live-hackathon-obcina-open-meteo.md](metodologija/live-hackathon-obcina-open-meteo.md)
