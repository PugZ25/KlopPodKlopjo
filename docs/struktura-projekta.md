# Struktura projekta

Repo je organiziran tako, da je tok projekta berljiv tudi brez razlage ekipe.
Vsaka večja mapa ima eno jasno vlogo, brez mešanja podatkov, modela,
aplikacije in zunanjih eksperimentov.

## Zakaj je ta delitev pomembna

Takšna struktura pokaže tri stvari:

- da je raziskovalni tok ločen od produkcijskega prikaza
- da so podatki, modeli in aplikacija reproducibilni deli istega sistema
- da zunanji ali zgodovinski importi ne zameglijo uradnega jedra projekta

## Glavne mape

- `docs/`: metodologija, predstavitvena gradiva in raziskovalni povzetki
- `data/`: pravila za surove, vmesne in končne podatke
- `pipelines/`: ponovljivi koraki priprave podatkov in značilk
- `ml/`: trening modelov, konfiguracije in referenčni baseline
- `frontend/`: live demo in uporabniška razlaga rezultatov
- `backend/`: rezerviran prostor za morebitni prihodnji API
- `scripts/`: operativni skripti za generiranje podatkovnih in frontend artefaktov
- `tests/`: enotski testi za ključne komponente
- `contrib/`: ločeni zunanji workspacei in reference, ki še niso del glavnega toka

## Praktično pravilo

Če nova datoteka:

- pojasnjuje odločitev, sodi v `docs/`
- predstavlja vir ali podatkovni artefakt, sodi v `data/`
- gradi značilke ali model, sodi v `pipelines/` ali `ml/`
- vpliva na prikaz za uporabnika, sodi v `frontend/`
- predstavlja zunanji import ali zgodovinski eksperiment, sodi v `contrib/`

## Kaj namenoma ni v Git

Repo ni arhiv vseh lokalnih delovnih datotek. V Git ne sodijo:

- veliki surovi prenosi in začasni izhodi, če niso namensko kurirani
- lokalni osnutki, izvozi in predstavitveni odpad
- SLURM logi, `.DS_Store` in podobni sistemski artefakti
- prazne mape, ki ne nosijo nobene vsebinske vrednosti
