# Analiza Prvih SLING Rezultatov

Ta dokument povzema prva trening zagona na ARNES SLING za:

- boreliozo (`target_lyme_cases`)
- KME (`target_kme_cases`)

Analiza temelji na:

- `slurm-klop-catboost-66057321.out`
- `slurm-klop-catboost-66057327.out`
- `data/processed/training/catboost_tick_borne_lyme_v1/metadata.json`
- `data/processed/training/catboost_tick_borne_kme_v1/metadata.json`
- `data/processed/training/catboost_tick_borne_lyme_v1/holdout_predictions.csv`
- `data/processed/training/catboost_tick_borne_kme_v1/holdout_predictions.csv`

## 1. Kaj je bilo dejansko validirano

Oba modela uporabljata isti dataset:

- `107696` vrstic
- ena vrstica = ena obcina in en teden
- casovni split brez mesanja prihodnosti v preteklost

Split je metodolosko pravilen za napovedovanje:

- train: `2016-04-04` do `2023-01-16`
- validation: `2023-01-23` do `2024-07-01`
- test: `2024-07-08` do `2025-12-22`

To pomeni, da rezultati niso optimisticni zaradi nakljucnega splitanja po vrsticah.

## 2. Hiter povzetek rezultatov

### Borelioza

Na ravni obcina-teden je model uporaben:

- validation: `RMSE 0.589`, `MAE 0.345`, `R² 0.683`
- test: `RMSE 0.725`, `MAE 0.402`, `R² 0.663`

Na ravni skupnih tedenskih vsot po Sloveniji model zelo dobro sledi sezonskemu valu:

- validation weekly: `R² 0.624`, korelacija `0.962`
- test weekly: `R² 0.854`, korelacija `0.931`

Interpretacija:

- model dobro zajame relativni vzorec tveganja
- model ni se natancen stevec primerov za vsako posamezno obcino
- pri poletnih vrhovih v testu veckrat podceni najvisje valove

### KME

Na ravni obcina-teden je model trenutno sibek:

- validation: `RMSE 0.0889`, `MAE 0.0163`, `R² 0.0365`
- test: `RMSE 0.0839`, `MAE 0.0157`, `R² 0.0368`

Na ravni skupnih tedenskih vsot po Sloveniji je rezultat nekoliko boljsi, a se vedno omejen:

- validation weekly: `R² 0.235`, korelacija `0.659`
- test weekly: `R² 0.491`, korelacija `0.758`

Interpretacija:

- model nekaj sezonskega signala zazna
- na ravni posamezne obcine in tedna se signal skoraj izgubi
- trenutna regresijska formulacija za KME se ni dovolj dobra za operativno uporabo

## 3. Zakaj sta rezultata tako razlicna

Glavni razlog je redkost cilja.

Porazdelitev targetov v celotnem datasetu:

- borelioza: povprecje `0.419`, nicle v `78.0%` vrstic
- KME: povprecje `0.0098`, nicle v `99.1%` vrstic

To pomeni:

- borelioza ima dovolj pozitivnih primerov, da model vidi uporaben signal
- KME je skoraj povsod nicla, zato je problem mocno zero-inflated
- pri KME nizka `MAE` ne pomeni nujno dobrega modela, ker je ze skoraj vedno pravilno napovedati "skoraj nic"

Dodatni znak tezave pri KME:

- model vraca tudi negativne napovedi, ceprav stevilo primerov ne more biti negativno
- v holdoutu je takih napovedi veliko, kar pomeni, da navadna regresija ni dobro usklajena z naravo cilja

## 4. Kaj model v resnici uporablja

### Borelioza

Najpomembnejse znacilke so pretezno:

- `lyme_cases_prev_4w_sum` (`53.66`)
- `lyme_cases_lag_2w` (`5.97`)
- sezonski kazalci: `iso_week`, `week_of_year_sin`, `week_of_year_cos`, `month`
- populacija in lokacija: `log_population_total`, `obcina_sifra`

Pomen:

- model se trenutno najbolj opira na epidemiolosko zgodovino in sezonskost
- vremenski in prostorski signal obstaja, vendar je sekundaren
- to je dober baseline model, ne pa se cisti "okoljski" model tveganja

### KME

Najpomembnejse znacilke so bolj razprsene:

- `week_of_year_cos`
- `lyme_cases_prev_4w_sum`
- `kme_cases_prev_8w_sum`
- `lyme_cases_lag_2w`
- `log_population_total`

Pomen:

- tudi pri KME model vecinoma lovi sezono in zgodovino primerov
- ker je pozitivnih KME dogodkov zelo malo, je informacija za ucenje presibka

## 5. Primerjava z enostavnimi baseline modeli

Za boreliozo CatBoost dejansko prinese dodano vrednost:

- validation `R² 0.683` proti `0.630` za enostavni `prev_4w_avg`
- test `R² 0.663` proti `0.590` za enostavni `prev_4w_avg`

To pomeni, da model ni le kopija preteklega povprecja.

Za KME je slika drugacna:

- CatBoost premaga surovi lag baseline po `RMSE` in `R²`, ne pa nujno po `MAE`
- absolutni napredek je majhen
- `R²` ostaja skoraj na nicli, zato model metodolosko se ni dovolj mocan

## 6. Kaj je trenutno najbolj posten sklep

Najbolj racionalen sklep po prvem SLING zagonu je:

- model za boreliozo je dober prvi baseline in ga je smiselno razvijati naprej
- model za KME v trenutni regresijski obliki ni dober kandidat za glavni produkcijski model
- ce zelite hitro demonstracijo za hackathon ali zirijo, je borelioza trenutno glavni uspeh
- KME je bolje preoblikovati kot locen problem, ne pa vztrajati na isti regresijski formulaciji

## 7. Priporocen naslednji korak

### Korak 1: zaklenite boreliozo kot baseline v1

Ohranite trenutni model kot referencni baseline, ker:

- uporablja pravilen casovni split
- daje stabilen holdout rezultat
- premaga enostavne lag baseline

### Korak 2: KME preoblikujte iz regresije v redkejso napoved

Najbolj smiseln naslednji eksperiment ni dodatno fine-tunanje istih hiperparametrov, ampak sprememba formulacije problema:

- opcija A: binarna klasifikacija `target_kme_presence`
- opcija B: dvostopenjski model
- stopnja 1: prisotnost dogodka `0/1`
- stopnja 2: stevilo primerov samo za pozitivne tedne

To je metodolosko bolj skladno z redkim in skoraj nicelnim ciljem.

### Korak 3: evaluacijo razsirite izven RMSE

Za naslednjo iteracijo dodajte:

- primerjavo proti trivialnim baseline modelom
- metrike na ravni obcina-teden in tudi na ravni tedenskih agregatov
- za klasifikacijo se `precision`, `recall`, `F1`, `PR-AUC`
- za regresijo pregled vrhov, podcenjevanja vrhuncev in kalibracije po sezonah

### Korak 4: model prevedite v razumljivo tveganje

Za uporabo v produktu ali predstavitvi ne kazite surovih decimalnih napovedi primerov, ampak:

- `Nizko`
- `Srednje`
- `Visoko`

Pragove dolocite na osnovi percentilov holdout napovedi ali epidemiolosko smiselnih cut-offov.

## 8. Operativni plan za naslednjih 1 do 2 iteraciji

1. Borelioza: obdrzite `catboost_tick_borne_lyme_v1` kot uradni baseline.
2. KME: pripravite novo konfiguracijo za `binary_classification` na `target_kme_presence`.
3. Dodajte skript, ki po treningu avtomatsko izpise se baseline primerjave in tedenske agregate.
4. Na podlagi holdout napovedi pripravite tri risk bande za frontend ali predstavitev.
5. Sele nato se lotite hiperparametrskega tunanja, ker je trenutno vecji problem formulacija naloge kot tuning.

## 9. Kratek povzetek v eni povedi

Prvi SLING rezultat je uspesen za boreliozo, za KME pa je pokazal, da moramo problem preoblikovati iz navadne regresije v pristop za redek dogodek.
