# Struktura projekta

Ta struktura je pripravljena tako, da je:
- metodološko čista
- tehnično pravilna
- razumljiva tudi članom ekipe, ki niso programerji

## Zakaj je taka struktura dobra

Loči tri različne stvari, ki se pri podatkovnih projektih pogosto pomešajo:
- `data/` hrani podatke
- `ml/` hrani modelno logiko
- `backend/` in `frontend/` hranita aplikacijo

S tem žiriji pokažete, da projekt ni samo ideja, ampak ima urejen tehnični in raziskovalni tok.

## Priporočen potek dela

1. V `docs/okvirna-ideja/` je osnovna projektna ideja.
2. V `data/raw/` se odlagajo originalni podatki iz virov.
3. V `pipelines/` se definirajo koraki čiščenja in združevanja.
4. V `data/interim/` nastanejo očiščene in povezane tabele.
5. V `ml/` nastanejo značilke, model in napovedi.
6. V `data/processed/` se shranijo rezultati, pripravljeni za uporabo.
7. V `backend/` se pripravi API.
8. V `frontend/` se prikaže zemljevid, tveganje in razlage za uporabnika.

## Pomen posameznih map

### `.github/`

GitHub tehnične datoteke, predvsem workflowi za avtomatske preglede in morebitni CI.

### `backend/`

Strežniški del aplikacije.

- `app/`: zagon aplikacije
- `api/`: API poti
- `services/`: poslovna logika
- `models/`: podatkovni modeli in sheme

### `frontend/`

Uporabniški del spletne aplikacije.

- `public/`: statične datoteke
- `src/components/`: manjši gradniki
- `src/pages/`: posamezni zasloni
- `src/styles/`: slogovne datoteke

### `data/`

Podatki so ločeni po stopnjah obdelave.

- `raw/`: originalni podatki po virih
- `interim/`: očiščeni in povezani podatki
- `processed/`: končni podatki za model ali aplikacijo

Za vsako novo podmapo v `data/raw/` dodajte tudi `README.md`, kjer ostanejo zapisani izvor, URL, datum prevzema in osnovni opis datotek.

### `ml/`

Modelni del projekta.

- `features/`: priprava značilk
- `training/`: učenje modela
- `inference/`: generiranje napovedi

### `pipelines/`

Jasno ločeni koraki podatkovnega procesa.

- `ingest/`: prevzem podatkov
- `clean/`: čiščenje
- `features/`: priprava značilk
- `train/`: učenje
- `inference/`: napovedovanje

### `docs/`

Gradiva za ekipo in žirijo.

- `okvirna-ideja/`: začetna prijava in osnovna ideja
- `metodologija/`: metodološki zapisi
- `oddaja/`: dokumenti za finalno oddajo

### `tests/`

Testi, s katerimi pokažete tehnično zrelost.

- `unit/`: testi posameznih funkcij
- `integration/`: testi povezovanja komponent

### `scripts/`

Manjši pomožni skripti.

- `data/`: pomožna opravila za podatke
- `dev/`: razvojna opravila

### `notebooks/`

Eksperimentalna analiza in hitri prototipi, ki še niso del glavne kode.

### `infra/`

Tehnična infrastruktura.

- `docker/`: kontejnerji
- `deploy/`: nastavitve za objavo

## Pravila poimenovanja

Za tehnične poti uporabljamo:
- male črke
- vezaje namesto presledkov
- angleška ali tehnično nevtralna imena map

To zmanjša napake in deluje bolj profesionalno pri predstavitvi.

## Opomba za ekipo

Datoteka `.gitkeep` obstaja samo zato, da Git shrani tudi prazne mape. Ne gre za vsebino projekta, ampak za tehnični označevalec.
