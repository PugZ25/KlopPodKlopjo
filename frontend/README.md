# Frontend

`frontend/` vsebuje React + TypeScript + Vite aplikacijo. To je
javni obraz projekta: uporabnik vidi relativni preventivni signal, zemljevid,
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
- `src/data/precautionSnapshot.json`: reproduciran tedenski build-time snapshot
- `src/data/liveMunicipalityRisk.ts`: TypeScript pogodba in varen uvoz snapshota
- `src/data/siteContent.ts`: vsebina, razlage in viri v aplikaciji
- `public/municipality-boundaries.json`: geometrije občin za geolokacijski lookup

## Pomembna omejitev

Frontend v produkciji ne kliče runtime API-ja za inference in ne potrebuje novih
prijav primerov. Uporablja vnaprej pripravljen artefakt, ki se osvežuje s
dnevnim GitHub workflowom. Modelni signal se spremeni ob ponedeljkih, vremenski
kontekst pa vsak dan zajame zadnjih sedem zaključenih UTC dni. Občinsko uteženi
Open-Meteo/DWD ICON podatki so prikazani ločeno in ne spreminjajo AI signala.
Celoten aktivni tok je opisan v
[../model_v3/OPERATIONAL_OPEN_METEO_WEATHER.md](../model_v3/OPERATIONAL_OPEN_METEO_WEATHER.md).
