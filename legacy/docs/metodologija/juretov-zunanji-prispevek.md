# Juretov Zunanji Prispevek

Ta dokument formalizira status Juretovega zunanjega workspacea po uvozu v ta repozitorij.

## Status

- status: `reference_only`
- avtor prispevka: `Jure`
- datum umestitve v repozitorij: `2026-04-14`
- lokacija v repozitoriju: `contrib/jure/`
- namen: `metodološka referenca in revizijska sled`

## Kaj prispevek vsebuje

Prispevek ima dve glavni veji.

### Okoljski razlagalni branch

Mapa:

- `contrib/jure/okoljski-raziskovalni-model/`

Ta veja prispeva:

- ločen explanatory baseline na ravni `obcina x teden`
- grouped ablation primerjave okoljskih faktorjev
- jasno ločitev med explanatory in predictive ciljem
- rezervacijo leta `2025` kot finalni holdout
- dokumentiran argument, da disease-history predictorji ne sodijo v glavno explanatory primerjavo

Ta del je metodološko uporaben za razlago:

- zakaj okoljske faktorje predstavljamo kot podporni signal, ne kot čisto kavzalni dokaz
- zakaj je grouped interpretacija smiselnejša od posameznih surovih feature rankingov
- zakaj mora biti explanatory branch ločen od forecast brancha

### Predictive eksperimentalni branch

Mapa:

- `contrib/jure/predictive-model-prevalence-v1/`

Ta veja prispeva:

- reproducibilne acquisition pipeline za prihodnje Copernicus vhodne podatke
- `Model A` short-range forecast eksperiment
- `Model C` climate-scenario eksperiment
- `V2 residual` formulacije za oba branch-a
- spremljevalna validacijska in integritetna poročila

Ta del je uporaben predvsem kot:

- raziskovalni dokaz, da sta bili napovedni veji dejansko razvijani
- podporni material za razlago prihodnjih iteracij
- ločen eksperimentalni sandbox, ne pa kot trenutni uradni baseline

## Kako se prispevek navezuje na glavni projekt

Prispevek vsebinsko podpira obstoječe uradne dokumente, vendar jih ne nadomešča.

Najpomembnejše povezave:

- `borelioza-baseline-v1`
  - glavni uradni baseline za boreliozo ostaja v `ml/` in `data/processed/`
- `kme-v2-analiza`
  - Juretov predictive branch daje dodatni raziskovalni kontekst, ne pa uradne baseline odločitve
- `environmental-risk-env-v2-pragovi`
  - okoljski explanatory branch pomaga pojasniti, zakaj so env modeli primerni za relativne risk band-e in ne za absolutne epidemiološke verjetnosti

## Kaj velja za predstavitev žiriji

Za žirijo je varno trditi:

- da je ekipa razvijala tudi ločene raziskovalne branch-e za explanatory in predictive namen
- da obstaja ločen environmental research baseline
- da obstaja ločen predictive workspace za kratkoročne in climate-scenario eksperimente
- da je vse to ohranjeno v repozitoriju kot zunanji prispevek in ne kot pomešana glavna koda

Za žirijo ni korektno trditi:

- da je celoten Juretov workspace že integriran v glavni produkcijski pipeline
- da so vsi njegovi modeli uradni baseline modeli projekta
- da so njegovi acquisition outputi del trenutnega deploya ali frontend vira podatkov

## Odločitev o umestitvi

Juretov prispevek ostane ločen v `contrib/jure/`, ker je to najbolj metodološko čista rešitev:

- loči zunanji import od glavne kode
- ohrani revizijsko sled
- zmanjša tveganje, da bi eksperimentalne poti ali outputi pokvarili glavni commit
- žiriji pokaže, da je ekipa delala raziskovalno širino, ne da bi zaradi tega izgubila tehnični red

## Pravilo za prihodnjo promocijo kode

Noben del iz `contrib/jure/` ne sme neposredno postati uradni del produkcijskega toka brez:

1. nove metodološke odločitve v `docs/metodologija/`
2. refaktorja v trenutno projektno strukturo
3. ločene validacije v istem referenčnem splitu kot glavni modeli
