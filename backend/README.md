# Backend

`backend/` je rezerviran za prihodnji runtime API in drugo strežniško logiko.
Trenutni live deployment ne vključuje backenda; v produkciji se objavi samo
statični frontend build.

- `app/`: prostor za glavni zagon backend aplikacije
- `api/`: prostor za definicije API poti
- `services/`: prostor za izračune in delo s podatki
- `models/`: prostor za podatkovne sheme

## Python setup

Za delo s Copernicus Climate Data Store API uporabljamo Python paket `cdsapi`.
To ni del trenutnega live deployment workflowa.

Priporočen lokalni zagon iz korena repozitorija:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Po namestitvi mora biti v domači mapi še datoteka `~/.cdsapirc` z vašim CDS API ključem, sicer prenos podatkov ne bo deloval.
