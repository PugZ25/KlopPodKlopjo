# Frontend

`frontend/` vsebuje React + TypeScript + Vite aplikacijo za live demo. To je
javni obraz projekta: uporabnik vidi oceno občinskega tveganja, zemljevid,
ključne razlage in preventivne informacije.

## Lokalni razvoj

Namestitev odvisnosti:

```bash
npm ci --prefix frontend
```

Zagon razvojnega strežnika:

```bash
npm run dev --prefix frontend
```

Produkcijski build:

```bash
npm run build --prefix frontend
```

Live deployment je konfiguriran v [../vercel.json](../vercel.json), produkcijski
izhod pa je `frontend/dist`.

## Ključne datoteke

- `src/App.tsx`: glavna sestava uporabniškega vmesnika
- `src/components/MapView.tsx`: interaktivni zemljevid občin
- `src/data/liveMunicipalityRisk.ts`: build-time snapshot live tveganja
- `src/data/siteContent.ts`: vsebina, razlage in viri v aplikaciji
- `public/municipality-boundaries.json`: geometrije občin za geolokacijski lookup

## Pomembna omejitev

Frontend v produkciji ne kliče runtime API-ja za live inference. Uporablja
vnaprej pripravljene artefakte, ki se praviloma osvežujejo prek tedenskega
GitHub workflowa in nato objavijo na Vercelu. Celoten workflow je opisan v
[../docs/live-deployment.md](../docs/live-deployment.md).
