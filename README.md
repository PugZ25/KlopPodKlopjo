# KlopPodKlopjo

Projekt `KlopPodKlopjo` razvija podatkovno podprto spletno rešitev za ocenjevanje tveganja za stik s klopi ter za boreliozo in KME v Sloveniji.

Ta repozitorij je namenoma urejen preprosto:
- da ekipa hitro razume, kaj sodi kam
- da je metodološki tok projekta jasen tudi žiriji
- da se podatki, model, aplikacija in dokumentacija ne mešajo med seboj

## Osnovna logika projekta

Projekt teče v štirih korakih:
1. V `data/` zberemo in hranimo podatke iz virov, kot so ARSO, NIJZ, Copernicus, SURS in ZGS.
2. V `pipelines/` in `scripts/` podatke očistimo, združimo in pripravimo značilke za model.
3. V `ml/` razvijemo model za oceno tveganja.
4. V `backend/` in `frontend/` pripravimo spletno aplikacijo za prikaz rezultatov.

## Struktura repozitorija

```text
KlopPodKlopjo/
├── .github/                # GitHub workflowi in nastavitve za sodelovanje
├── backend/                # Strežniški del aplikacije
├── data/                   # Surovi, vmesni in končni podatki
├── docs/                   # Ideja, metodologija in gradiva za oddajo
├── frontend/               # Uporabniški vmesnik spletne aplikacije
├── infra/                  # Docker, deployment in tehnična infrastruktura
├── ml/                     # Učenje modelov in napovedovanje
├── notebooks/              # Raziskovalne analize in prototipi
├── pipelines/              # Koraki podatkovnega procesa
├── scripts/                # Manjši pomožni skripti
└── tests/                  # Testi
```

Podrobnejša razlaga je v [docs/struktura-projekta.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/struktura-projekta.md).

## Najpomembnejše mape

- [data/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/data/README.md): kako hranimo surove, očiščene in končne podatke
- [ml/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/ml/README.md): kam sodijo modeli, značilke in napovedi
- [backend/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/backend/README.md): strežniški del aplikacije
- [frontend/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/frontend/README.md): prikaz za uporabnika
- [docs/README.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/README.md): metodologija, ideja in materiali za žirijo

## Pravilo za ekipo

Če niste prepričani, kam nekaj spada, uporabite to pravilo:
- dokument spada v `docs/`
- podatkovna datoteka spada v `data/`
- model ali feature engineering spada v `ml/`
- avtomatiziran korak obdelave spada v `pipelines/`
- uporabniški vmesnik spada v `frontend/`
- strežniška logika in API spadata v `backend/`

## Trenutna referenčna gradiva

- [docs/okvirna-ideja/okvirna-ideja.txt](/Users/zankespert/Desktop/KlopPodKlopjo/docs/okvirna-ideja/okvirna-ideja.txt)
- [docs/okvirna-ideja/heart-hackers-klop-pod-klopjo.pdf](/Users/zankespert/Desktop/KlopPodKlopjo/docs/okvirna-ideja/heart-hackers-klop-pod-klopjo.pdf)
