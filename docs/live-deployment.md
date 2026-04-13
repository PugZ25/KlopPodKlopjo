# Live Deployment

Ta dokument opisuje trenutni produkcijski workflow za live demo.

## Kaj je danes v produkciji

Live deployment je statični React + Vite frontend na Vercelu.

- Vercel konfiguracija je v `vercel.json`
- install command: `npm ci --prefix frontend`
- build command: `npm run build --prefix frontend`
- output directory: `frontend/dist`

Produkcijski deploy trenutno ne vključuje runtime backenda. Vse, kar frontend za
live demo potrebuje, je vnaprej zgenerirano in shranjeno v repozitoriju.

## Kateri artefakti morajo biti osveženi pred deployem

Pred objavo je treba lokalno osvežiti dve datoteki:

- `frontend/src/data/liveMunicipalityRisk.ts`
  vsebuje zadnji build-time snapshot občinskih score-ov za boreliozo in KME
- `frontend/public/municipality-boundaries.json`
  vsebuje poenostavljen GURS asset za geolokacijsko prepoznavo občine v brskalniku

Vercel teh datotek ne generira sam med buildom. Ce nista osvezeni pred push-em,
bo v produkciji ostal star snapshot.

## Predpogoji

Node del:

- `frontend/node_modules` ali `npm ci --prefix frontend`

Python del za osvežitev live snapshota:

- okolje z `catboost` in `shapely`
- primer namestitve: `python3 -m pip install -r ml/training/requirements.txt shapely`

## Priporocen postopek

1. Osvezi geolokacijski asset:

```bash
python3 scripts/data/build_municipality_boundary_asset.py
```

2. Osvezi live snapshot za frontend:

```bash
python3 scripts/data/build_live_municipality_risk_frontend_data.py --as-of-date YYYY-MM-DD
```

`--as-of-date` je opcijski. Ce ga izpustis, skripta uporabi danesnji datum in iz
njega izracuna zadnji zakljuceni tedenski snapshot.

3. Preveri produkcijski build:

```bash
npm run build --prefix frontend
```

4. Commitaj osvezeni generirani datoteki in jih potisni v vejo, ki jo deploya Vercel.

5. Sprozi produkcijski deploy v Vercelu:

- prek Git integracije z novim push-em
- ali rocno z `vercel --prod`, ce je projekt ze povezan

## Pomembne omejitve

- Live score-i so build-time snapshot, ne runtime izracun.
- Geolokacija uporabnika deluje v brskalniku, lookup občine pa bere lokalni JSON asset.
- Produkcija trenutno nima API poti za live inference.
- Za metodolosko razlago live snapshota glej
  [docs/metodologija/live-hackathon-obcina-open-meteo.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/live-hackathon-obcina-open-meteo.md).
