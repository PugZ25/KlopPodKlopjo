# Live Deployment

Ta dokument opisuje priporočeni produkcijski workflow za live demo, kjer se
live snapshot osveži samodejno brez lokalnega zagona modela.

## Kaj je danes v produkciji

Live deployment je statični React + Vite frontend na Vercelu.

- Vercel konfiguracija je v `vercel.json`
- `installCommand`: `npm ci --prefix frontend`
- `buildCommand`: `npm run build --prefix frontend`
- `outputDirectory`: `frontend/dist`

Produkcija še vedno ne vključuje runtime backenda. Frontend uporablja build-time
snapshot v `frontend/src/data/liveMunicipalityRisk.ts`, vendar je priporočena
osvežitev zdaj avtomatizirana.

## Priporočena avtomatizacija

Priporočeni tok je:

1. GitHub Actions enkrat tedensko zažene
   `.github/workflows/weekly-live-snapshot.yml`
2. workflow namesti `catboost`, požene
   `scripts/data/build_live_municipality_risk_frontend_data.py`
3. če se `frontend/src/data/liveMunicipalityRisk.ts` spremeni, workflow commitne
   datoteko v privzeto vejo
4. Vercel zaradi push-a sam sproži nov deploy statičnega frontenda

Ta pristop je namenoma izbran namesto Vercel Cron + runtime inference, ker
trenutni live snapshot potrebuje CatBoost model in nekaj referenčnih artefaktov,
medtem ko je produkcija sicer povsem statična.

## Enkratna priprava

Preden tedenski workflow deluje samostojno, moraš urediti naslednje:

1. Repo mora biti na GitHubu in povezan z Vercel projektom.
2. Vercel mora deployati privzeto vejo repozitorija.
3. V Git moraš commitati mapo `data/reference/live_snapshot/`.
   Ta mapa vsebuje majhen referenčni asset pack:
   - `municipality_coordinates.json`
   - `municipality_static_features.json`
   - `catboost_tick_borne_*_env_v2/model.cbm`
   - `catboost_tick_borne_*_env_v2/metadata.json`
   - `catboost_tick_borne_*_env_v2/holdout_values.json`
4. GitHub Actions mora imeti dovoljenje za `contents: write`.
   Če je privzeta veja strogo zaščitena, moraš dovoliti push za
   `github-actions[bot]` ali workflow prilagoditi na PR-based tok.

Tedenski workflow je nastavljen na:

```yaml
schedule:
  - cron: "15 4 * * 1"
```

To pomeni vsak ponedeljek ob `04:15 UTC`.

## Kdaj moraš lokalno posodobiti referenčni asset pack

Tedenski workflow ne potrebuje več `data/raw/` in `data/processed/`, ker bere
trackan `data/reference/live_snapshot/`. Ta paket pa moraš ročno obnoviti samo
takrat, ko se spremeni katera od teh stvari:

- env_v2 model (`model.cbm`)
- `holdout` distribucija ali `metadata.json`
- statični feature kontrakt modela
- logika koordinat občin za Open-Meteo sampling

Paket osvežiš z:

```bash
python3 scripts/data/build_live_snapshot_reference_assets.py
```

Nato commitaj spremembe v `data/reference/live_snapshot/`.

## Ročni fallback

Če želiš snapshot osvežiti takoj, ne da čakaš na tedenski schedule:

```bash
python3 -m pip install -r ml/training/requirements.txt
python3 scripts/data/build_live_municipality_risk_frontend_data.py --as-of-date YYYY-MM-DD
npm run build --prefix frontend
```

`--as-of-date` je opcijski. Če ga izpustiš, skripta uporabi današnji datum in iz
njega izračuna zadnji zaključeni tedenski snapshot.

## Pomembne omejitve

- live score-i ostanejo build-time snapshot, ne runtime izračun
- geolokacija uporabnika teče v brskalniku in uporablja lokalni JSON asset
- produkcija še vedno nima API poti za live inference
- GitHub scheduled workflow teče samo na privzeti veji; pri neaktivnih javnih
  repozitorijih ga lahko GitHub po daljšem mirovanju začasno izklopi
- metodološka razlaga live snapshota je v
  [metodologija/live-hackathon-obcina-open-meteo.md](metodologija/live-hackathon-obcina-open-meteo.md)
