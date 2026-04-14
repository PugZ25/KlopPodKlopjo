# Juretov Zunanji Prispevek

Ta mapa je kuriran uvoz Juretovega dela, ki je bilo prvotno pripravljeno izven glavnega repozitorija in je bilo nato začasno odloženo v `tests/juredata/`.

Namen te umestitve je:

- ločiti Juretov zunanji workspace od glavne projektne kode
- ohraniti vsebinsko uporabne metodološke in skriptne dele
- preprečiti, da bi zunanji eksperimentalni outputi zameglili uradne baseline modele in frontend

## Kaj je bilo prestavljeno

Prejšnja začasna pot v repozitoriju:

- `tests/juredata/model 1 data`
- `tests/juredata/test`
- `tests/juredata/model 1 data.zip`

Nova kurirana umestitev:

- `contrib/jure/okoljski-raziskovalni-model/`
- `contrib/jure/predictive-model-prevalence-v1/`
- `contrib/jure/raw-import/model-1-data.zip` `ignored`

Grob inventory uvoženega materiala:

- približno `31` Python skript
- približno `105` Markdown dokumentov
- približno `67` CSV tabel
- približno `71` JSON artefaktov
- približno `249 MB` surovega acquisition outputa, ki je namenoma `ignored`

## Kaj je Jure dejansko naredil

Juretov import ima dve vsebinsko ločeni veji.

### 1. `okoljski-raziskovalni-model`

To je razlagalni okoljski baseline na ravni `obcina x teden`.

V njem je naredil:

- ločen explanatory branch za `KME`, `Lyme` in kombinirano tick-borne breme
- date-aligned tarče tekočega bremena namesto future targetov
- odstranitev disease-history prediktorjev iz glavne explanatory primerjave
- grouped CatBoost ablation primerjavo po družinah okoljskih faktorjev
- rezervacijo leta `2025` kot holdout validacijo
- spremljevalne skripte za gradnjo panela, validacijo in predstavitvene grafe

Ta veja je metodološko uporabna kot podporna razlaga okoljskega signala, ni pa uradni produkcijski forecast branch.

### 2. `predictive-model-prevalence-v1`

To je ločen predictive workspace z več podsistemi:

- `reproducible_acquisition_pipelines/`
  - reproducibilni downloaderji za Copernicus seasonal forecast in climate Atlas podatke
- `modeling - model_a_operational_forecast/`
  - starejši kratkoročni operativni forecast branch `V1`
- `modeling - model_a_v2_residual_forecast/`
  - aktivni `Model A V2` residual short-range forecast pristop
- `modeling - model_c_climate_effect/`
  - starejši climate-effect branch `V1`
- `modeling - model_c_v2_residual_climate/`
  - aktivni `Model C V2` residual climate-scenario branch
- `reports/`
  - cross-pipeline integritetna in procesna poročila

Vsebina kaže, da je Jure delal predvsem na:

- reproducibilnem acquisition layerju za prihodnje Copernicus podatke
- kratkoročnih forecast eksperimentih `Model A`
- dolgoročnih climate-scenario eksperimentih `Model C`
- residual formulacijah `V2`, kjer model napoveduje odmik od baseline trajektorije

## Kako se to navezuje na trenutni projekt

Juretov prispevek se vsebinsko navezuje na obstoječi projekt takole:

- podpira razlagalno okoljsko zgodbo, ki je relevantna za `env` metodološke dokumente
- podpira raziskovalni kontekst za `KME v2` in prihodnje forecast iteracije
- ni pa trenutni uradni vir resnice za glavne artefakte v `ml/`, `pipelines/`, `frontend/` ali `data/processed/`

Najbližje obstoječe uradne projektne reference so:

- [docs/metodologija/borelioza-baseline-v1.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/borelioza-baseline-v1.md)
- [docs/metodologija/kme-v2-analiza.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/kme-v2-analiza.md)
- [docs/metodologija/environmental-risk-env-v2-pragovi.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/environmental-risk-env-v2-pragovi.md)
- [docs/metodologija/juretov-zunanji-prispevek.md](/Users/zankespert/Desktop/KlopPodKlopjo/docs/metodologija/juretov-zunanji-prispevek.md)

## Zakaj ni integrirano v glavno kodo

Material namenoma ni prenesen neposredno v `pipelines/`, `ml/` ali `scripts/`, ker bi to povzročilo metodološko in tehnično zmedo:

- v importu so ohranjeni originalni eksperimentalni workspacei
- nekatere notranje README reference še vedno odražajo originalni standalone layout
- nekatere poti v poročilih še vedno referencirajo originalno Windows okolje
- acquisition `output/` vsebuje približno `249 MB` surovih datotek in ne sodi v glavni commit
- imena in struktura map odražajo ločen branch, ne pa trenutno projektno konvencijo

Zato ta mapa velja kot:

- `reference_only` za revizijo in branje
- vir za selektivno kasnejšo integracijo posameznih idej

Ne velja pa kot:

- uradni baseline
- glavni produkcijski pipeline
- neposreden vir frontend podatkov

## Pravilo za nadaljnjo uporabo

Če se kaj iz tega prispevka kasneje prenese v glavni projekt, mora iti po tem vrstnem redu:

1. najprej metodološka odločitev v `docs/metodologija/`
2. nato refaktor v trenutno projektno strukturo
3. šele potem prenos v `pipelines/`, `ml/`, `scripts/` ali `frontend/`
