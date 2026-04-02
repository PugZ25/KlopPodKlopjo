# Backend

`backend/` vsebuje strežniški del aplikacije.

- `app/`: glavni zagon backend aplikacije
- `api/`: definicije API poti
- `services/`: logika za izračune in delo s podatki
- `models/`: podatkovne sheme

## Python setup

Za delo s Copernicus Climate Data Store API uporabljamo Python paket `cdsapi`.

Priporočen lokalni zagon iz korena repozitorija:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Po namestitvi mora biti v domači mapi še datoteka `~/.cdsapirc` z vašim CDS API ključem, sicer prenos podatkov ne bo deloval.
