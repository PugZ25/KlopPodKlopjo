# KlopPodKlopjo

`KlopPodKlopjo` je podatkovno podprta spletna rešitev za ocenjevanje občinskega
tveganja za stik s klopi, lymsko boreliozo in KME v Sloveniji. Repozitorij je
pripravljen za javni pregled: v Git sodijo koda, dokumentacija, konfiguracije in
ključni reproducibilni artefakti, medtem ko surovi prenosi, osnutki, lokalni
logi in sistemska navlaka ostanejo lokalni.

## Za hiter pregled

Če repozitorij odpirate prvič, začnite tukaj:

- [docs/README.md](docs/README.md): kuriran pregled gradiv za žirijo
- [docs/presentation/hackathon-research-report.html](docs/presentation/hackathon-research-report.html): raziskovalni povzetek z grafi
- [frontend/README.md](frontend/README.md): live demo in struktura aplikacije
- [ml/training/README.md](ml/training/README.md): reproducibilen trening modelov
- [docs/live-deployment.md](docs/live-deployment.md): kako se osveži live snapshot in objavi demo

## Jedro projekta

Repo je zavestno razdeljen na nekaj jasnih delov:

- [frontend/](frontend): uporabniška spletna aplikacija za prikaz tveganja in preventivnih vsebin
- [docs/](docs): metodologija, predstavitvena gradiva in raziskovalni povzetki
- [data/](data): pravila za surove, vmesne in končne podatke
- [pipelines/](pipelines): ponovljivi koraki za pripravo značilk in podatkovnih naborov
- [ml/](ml): trening modelov, konfiguracije in referenčni baseline
- [scripts/](scripts): operativni skripti za generiranje frontend artefaktov in podatkovnih izhodov
- [tests/](tests): enotski testi za ključne podatkovne in modelne korake
- [contrib/](contrib): ločeni zunanji importi, ki niso del uradnega glavnega toka

Podrobnejša razlaga organizacije je v
[docs/struktura-projekta.md](docs/struktura-projekta.md).

## Trenutni status

- live demo je statični Vite build na Vercelu
- produkcija ne vključuje runtime backenda
- frontend uporablja build-time snapshot tveganja v `frontend/src/data/liveMunicipalityRisk.ts`
- geolokacijski lookup občine uporablja `frontend/public/municipality-boundaries.json`
- uradni baseline za boreliozo je `catboost_tick_borne_lyme_v1`

Za metodološko potrditev baseline modela glej
[docs/metodologija/borelioza-baseline-v1.md](docs/metodologija/borelioza-baseline-v1.md).

## Pravilo repozitorija

Če nekaj ne prispeva k razumevanju projekta, reproducibilnosti ali javni
predstavitvi, ne sodi v Git. To pomeni:

- surovi prenosi ostanejo v `data/raw/` lokalno, v Git pa sodijo predvsem `README` opisi, manifesti in nujni lahki artefakti
- vmesni in končni veliki izhodi ostanejo lokalni, razen če so namensko kurirani kot referenčni rezultat
- osnutki, delovni PDF-ji, SLURM logi, `.DS_Store` in podobni lokalni artefakti se ne verzionirajo
- zunanji eksperimentalni workspacei živijo v `contrib/`, dokler niso namensko refaktorirani v glavno strukturo
