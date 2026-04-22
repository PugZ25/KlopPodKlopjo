# Podatki

Mapa `data/` je razdeljena po stopnjah obdelave. Namen te delitve je, da so
jasno ločeni originalni prenosi, delovni vmesni artefakti in končni izhodi za
model ali aplikacijo.

## Stopnje obdelave

- `reference/`: lahki, namensko verzionirani referenčni artefakti za deploy ali avtomatizacijo
- `raw/`: originalni preneseni podatki iz virov
- `interim/`: očiščeni ali združeni vmesni podatki
- `processed/`: končni podatki za model, validacijo ali frontend

## Politika verzioniranja

Repo namenoma ne hrani vsega, kar nastane med delom s podatki.

- v Git sodijo predvsem `README` opisi, manifesti in izbrani lahki referenčni artefakti
- veliki surovi prenosi, začasni izhodi in večina generiranih tabel ostanejo lokalni
- v `raw/` se ničesar ne popravlja ročno
- vsaka nova podmapa vira mora imeti kratek opis izvora, datuma prevzema in vsebine

## Glavni viri

Trenutno uporabljeni javni viri vključujejo:

- `arso/`
- `copernicus/`
- `gurs/`
- `nijz/`
- `surs/`
- `zgs/`
