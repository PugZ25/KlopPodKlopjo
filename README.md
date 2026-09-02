# KlopPodKlopjo

`KlopPodKlopjo` je spletna aplikacija za učenje in previdnost pred klopi,
lymsko boreliozo in KME v Sloveniji. Modelni rezultat je relativni preventivni
signal, ne epidemiološko poročilo, meritev klopov, diagnoza ali osebna
verjetnost okužbe.

## Za hiter pregled

Če repozitorij odpirate prvič, začnite tukaj:

- [frontend/README.md](frontend/README.md): aplikacija in build-time podatkovna pogodba
- [model_v3/README.md](model_v3/README.md): aktivni reproducibilni modelni tok
- [model_v3/PRECAUTION_PROXY_MODEL.md](model_v3/PRECAUTION_PROXY_MODEL.md): izbor modela brez sprotnih primerov
- [model_v3/OPERATIONAL_OPEN_METEO_WEATHER.md](model_v3/OPERATIONAL_OPEN_METEO_WEATHER.md): dnevna vremenska osvežitev in objava

## Jedro projekta

Aktivno jedro je razdeljeno na:

- [frontend/](frontend): uporabniški zemljevid in preventivne vsebine
- [model_v3/](model_v3): podatkovne pogodbe, validacija, modeli in snapshot generator
- [data/](data): dokumentirani surovi viri; veliki prenosi ostanejo lokalni
- [.github/workflows/](.github/workflows): dnevna vremenska osvežitev in statična objava

## Trenutni status

- aplikacija je statični Vite build in ne vključuje runtime backenda
- frontend uporablja reproduciran `frontend/src/data/precautionSnapshot.json`
- tedenska inferenca ne potrebuje novejših prijav borelioze ali KME
- zadnjih sedem zaključenih dni Open-Meteo/DWD ICON vremena je prikazanih kot ločen, občinsko utežen modelni kontekst in niso vhod v izbrana modelna signala
- geolokacijski lookup občine uporablja `frontend/public/municipality-boundaries.json`
- KME je modeliran na ravni statistične regije; občine iste regije imajo isti signal

## Pravilo repozitorija

Če nekaj ne prispeva k razumevanju projekta, reproducibilnosti ali javni
predstavitvi, ne sodi v Git. To pomeni:

- surovi prenosi ostanejo v `data/raw/` lokalno, v Git pa sodijo predvsem `README` opisi, manifesti in nujni lahki artefakti
- vmesni in končni veliki izhodi ostanejo lokalni, razen če so reproducibilni modelni ali javni referenčni artefakti
- osnutki, delovni PDF-ji, SLURM logi, `.DS_Store` in podobni lokalni artefakti se ne verzionirajo
- zunanji eksperimentalni workspacei živijo v `contrib/`, dokler niso namensko refaktorirani v glavno strukturo
