# Frontend

`frontend/` vsebuje React + TypeScript + Vite aplikacijo za live demo.

## Lokalni razvoj

Namestitev odvisnosti:

```bash
npm ci --prefix frontend
```

Zagon development serverja:

```bash
npm run dev --prefix frontend
```

## Produkcijski build

Lokalni build:

```bash
npm run build --prefix frontend
```

Trenutni live deployment uporablja Vercel in je konfiguriran v
[`vercel.json`](/Users/zankespert/Desktop/KlopPodKlopjo/vercel.json).
Produkcijski artefakt je `frontend/dist`.

## Podatki za live deployment

Frontend v produkciji ne kliče runtime API-ja za live inference. Uporablja
vnaprej pripravljene artefakte:

- `src/data/liveMunicipalityRisk.ts`: zadnji build-time snapshot live občinskih score-ov
- `public/municipality-boundaries.json`: poenostavljen GURS asset za geolokacijski lookup
- `src/data/siteContent.ts`: statična vsebina in viri za razlage v aplikaciji

Pred produkcijskim deployem je treba generirane datoteke osvežiti lokalno in jih
shraniti v Git. Celoten workflow je opisan v
[docs/live-deployment.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/live-deployment.md).
