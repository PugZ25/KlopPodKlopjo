# Environmental Risk Env V2 Pragovi

Ta dokument formalizira izbor pragov `Nizko / Srednje / Visoko` za frontend
`environmental risk` podatke, ki temeljijo na novih `env_v2` modelih.

## Status

- status: `adopted`
- datum odlocitve: `2026-04-12`
- namen: `demo risk bands za frontend in zemljevid`
- izvor podatkov: `holdout_predictions.csv` iz novih `env_v2` artifactov

## Modela

Za izbor pragov se uporabljata:

- `catboost_tick_borne_lyme_env_v2`
- `catboost_tick_borne_kme_env_v2`

Oba modela sta binarna klasifikatorja, ki vračata `prediction_probability`.

## Holdout osnova

Pragovi se ne racunajo iz enega samega tedna, ampak iz celotne holdout baze
vsakega modela:

- `validation`
- `test`

To je pomembno zato, ker:

- en sam snapshot teden je lahko sezonsko nenavaden
- pragovi morajo ostati primerljivi med tedni istega modela
- frontend potrebuje stabilne risk band-e, ne tedensko premikajocih se mej

## Pravilo za pragove

Za vsak model vzamemo vse surove holdout napovedi `prediction_probability`
in izracunamo:

- `lowUpper`: 33.33 percentil celotne holdout distribucije
- `mediumUpper`: 66.67 percentil celotne holdout distribucije

Razredi so nato definirani takole:

- `Nizko`: `prediction_probability < lowUpper`
- `Srednje`: `lowUpper <= prediction_probability < mediumUpper`
- `Visoko`: `prediction_probability >= mediumUpper`

To pomeni:

- pragovi so vezani na surovi modelni izhod
- pragovi niso izracunani iz frontend `score`
- `score` je relativni okoljski indeks, ne verjetnost in ne osnova za klasifikacijo

## Pravilo za frontend score

Frontend `score` na lestvici `0-100` je relativni okoljski indeks, definiran
kot zaokrozen empiricni percentil vrednosti iz zadnjega testnega tedna znotraj
celotne holdout distribucije istega modela.

Formula:

`score = round(100 * rank(x) / N)`

kjer je:

- `x`: surova napoved za obcino v zadnjem testnem tednu
- `rank(x)`: stevilo holdout napovedi `<= x`
- `N`: stevilo vseh holdout napovedi modela v `validation + test`

Pomembna posledica:

- `score 90` ne pomeni `90 % verjetnosti bolezni`
- pomeni, da je lokacija v zgornjem delu zgodovinske holdout razvrstitve tega modela

## Izbrani pragovi

### Borelioza

- model: `catboost_tick_borne_lyme_env_v2`
- snapshot week: `2025-11-24`
- `lowUpper`: `0.3104672754`
- `mediumUpper`: `0.6677368232`

### KME

- model: `catboost_tick_borne_kme_env_v2`
- snapshot week: `2025-10-27`
- `lowUpper`: `0.0993442705133333`
- `mediumUpper`: `0.3756022169333333`

## Zakaj je ta izbira metodolosko smiselna

Ta izbira je primerna za demo in frontend zato, ker:

- uporablja samo holdout podatke, ne train obdobja
- ohranja isti referencni okvir za vse obcine v istem modelu
- je robustnejsa od ad-hoc ročnih pragov
- omogoca ponovljiv izracun iz artifactov

Ta izbira ni namenjena temu, da bi:

- trdili, da gre za kalibrirane epidemioloske verjetnosti
- primerjali surove pragove med boreliozo in KME

Surovih pragov med modeloma ne smemo neposredno primerjati, ker vsak model
ima svojo distribucijo izhodov.

## Implementacija v repozitoriju

Generator:

- `scripts/data/build_environmental_risk_frontend_data.py`

Izhod:

- `frontend/src/data/environmentalRisk.ts`

Preverjanje:

```bash
python3 scripts/data/build_environmental_risk_frontend_data.py --check
```

## Opomba o trenutnem UI

Ta datoteka trenutno usklajuje vir podatkov za `environmentalRisk.ts`.
Trenutni landing page se se vedno opira na `frontend/src/data/regionRisk.ts`,
zato sama menjava pragov tukaj se ne spremeni obstojecega prikaza na strani.
