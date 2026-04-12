# Live Hackathon Demo Po Obcinah

Ta dokument formalizira hackathon pristop za live demo po obcinah.

## Status

- status: `adopted`
- datum odlocitve: `2026-04-12`
- namen: `hiter in metodolosko posten live demo za zirijo`

## Kaj demo dela

Frontend za uporabnika:

- pridobi GPS lokacijo uporabnika
- lokacijo preslika v obcino z GURS obcinskimi poligoni
- iz statičnega build-time snapshot-a prebere score za izbrano obcino

Build-time generator:

- za vsako obcino vzame reprezentativno tocko znotraj GURS poligona obcine
- prenese zadnjih 6 tednov hourly weather iz Open-Meteo
- izracuna tedenske featureje po istem feature kontraktu kot `env_v2`
- uporabi posebna `per 100k` CatBoost modela za score zadnjega referencnega tedna

## Zakaj ni runtime backend inference

Za hackathon je to najboljsi kompromis zato, ker:

- obdrzi pravi model, ne rocne heuristike
- frontend ostane preprost za deploy na static hosting
- geolokacija je se vedno interaktivna in vezana na uporabnikovo obcino
- izognemo se dodatni strezniski infrastrukturi tik pred oddajo

## Referencni cas

Score ni definiran kot "trenutno stanje te sekunde", ampak kot:

- zadnji zakljuceni tedenski snapshot

To je metodolosko bolj pravilno od delno zakljucenega tedna, ker so bili tudi
ucni featureji definirani kot tedenske agregacije.

## Vremenski vir

Za live hackathon demo uporabljamo:

- `Open-Meteo best-match hourly weather`

Razlog:

- je hitro dostopen brez dodatne avtentikacije
- omogoca zadnje tedne in dovolj granularne hourly spremenljivke
- zadostuje za demo, kjer je najpomembnejsa stabilna in ponovljiva pot do score-a

## Geografski kompromis

Trening weather featureji so bili zgrajeni iz obcinsko agregiranih prostorskih
vrednosti. Live demo uporablja:

- reprezentativno tocko znotraj GURS poligona obcine za vremenski query

To ni popoln nadomestek za area-weighted obcinski weather pipeline, vendar je za
hackathon sprejemljiv kompromis, ker:

- staticne prostorske znacilke ostanejo obcinske
- frontend score ostane na ravni obcine
- pristop je bistveno lazji za reproducibilen demo v enem dnevu

Ta omejitev mora biti ob predstavitvi jasno povedana.

## Pragovi in score

`Nizko / Srednje / Visoko` se za live demo dolocijo iz holdout distribucije
istega `per 100k` modela.

To pomeni:

- live build ne preracunava pragov iz trenutnega batcha obcin
- score ostane primerljiv z zgodovinsko holdout distribucijo istega modela

## Interpretacija

Velja ista interpretacija kot pri `environmentalRisk.ts`:

- score je rangirni obcinski indeks
- score ni individualna verjetnost bolezni
- rezultat ni diagnoza
- target modela je normaliziran na `100k prebivalcev`

Za boreliozo pomeni signal za:

- naslednje 4 tedne

Za KME pomeni signal za:

- naslednjih 8 tednov

## Kaj je pomembno povedati ziriji

1. Demo uporablja pravi trenirani `per 100k` model, ne rocnega weightanja po napovedi.
2. Live del je omejen na zadnji zakljuceni tedenski snapshot.
3. Vreme pride iz Open-Meteo, ne iz ročno vnesenih podatkov.
4. Obcina iz GPS se doloci z GURS poligoni, zemljevid pa prikazuje dejanske obcinske poligone, ne centroid markerjev.
5. Score je rangirni obcinski indeks na `100k prebivalcev`, ne medicinska verjetnost.
