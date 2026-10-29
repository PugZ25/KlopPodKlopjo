# Rezultati — besedilo za članek

Nadaljuje razdelek o metodah (podatki, rolling-origin, MAE/RMSE/devianca) in
uporablja isto izrazje: *zgodovinsko povprečje*, *Poissonov GLM*, *CatBoost*.

## Stavek, ki ga je treba dodati v metode

Brez njega leto 2025 v rezultatih ni pojasnjeno. Predlagan zaključek odstavka o
vrednotenju:

> Zadnje leto (2025) smo pri boreliozi izločili iz razvoja: modelne odločitve
> smo zamrznili in model na tem letu ovrednotili samo enkrat.

## Rezultati

**Borelioza.** V razvojnih letih (2017–2024, 81.832 napovedi) je CatBoost dosegel
MAE 1,183, kar je 10,4 % manj kot Poissonov GLM z enakimi informacijami in 11,5 %
manj kot zgodovinsko povprečje po občinah in letnih časih. Na zamrznjenem letu
2025 (9.964 napovedi za 212 občin) je MAE znašal 1,169, kar je 4,1 % manj kot pri
GLM (1,218) in 2,9 % manj kot pri zgodovinskem povprečju (1,204); pri Poissonovi
devianci je bila prednost pred GLM 7,8 % (slika 2). Pri RMSE je bilo zgodovinsko
povprečje z 2,118 rahlo boljše od CatBoosta (2,163), kar pomeni, da je prednost
strojnega učenja v pogostih majhnih napakah in ne v redkih velikih odstopanjih.
Prednost pred GLM se je na neodvisnem letu več kot prepolovila, model pa število
prijavljenih primerov sistematično podcenjuje za približno 13,5 %.

**KME.** Izbrani Poissonov GLM je na osmih preverjevalnih letih (2018–2025, 4.236
napovedi) dosegel MAE 1,229, kar je 22,4 % manj kot zgodovinsko povprečje po
regijah (1,583). CatBoost z vremenskimi značilkami je imel sicer nekoliko nižji
skupni MAE (1,208), a je bil boljši le v štirih od osmih preverjevalnih let, zato
ga nismo izbrali; različici z vremenom (1,262) in s preteklimi primeri (1,233)
sta bili slabši od izbranega modela.

> Če je prostora premalo: prvi in drugi stavek pri boreliozi ter prvi stavek pri
> KME nosijo celoten rezultat, ostalo so poštena pojasnila.

## Napis pod sliko

**Slika 2:** Vrednotenje napovednih modelov za boreliozo na zamrznjenem letu 2025
(9.964 napovedi na sistem, 212 občin, napoved za štiri tedne vnaprej). Krajši
stolpec pomeni manjšo napako. Vir: `model_v3/outputs/lockbox_2025/`.

## Kratek opis grafa v besedilu (če napis pod sliko ni dovolj)

Slika 2 primerja izbrani model, primerjalni GLM in zgodovinsko povprečje na letu
2025, ki pri razvoju modela ni sodelovalo. Izbrani model ima najnižji MAE, pri
RMSE pa ga zgodovinsko povprečje rahlo prehiti; razlike med sistemi so majhne,
kar je pri tako redkih tedenskih dogodkih pričakovano.

## Preverjene številke

Zaklenjeno leto 2025, borelioza (`lockbox_2025/lyme_lockbox_metrics.csv`):

| Sistem | MAE | RMSE | Poissonova devianca |
|---|---|---|---|
| CatBoost — izbrani model | 1,1688 | 2,1629 | 1,5385 |
| Poissonov GLM — primerjalni model | 1,2183 | 2,3498 | 1,6689 |
| Zgodovinsko povprečje (občina × letni čas) | 1,2041 | 2,1181 | ni veljavno |

Razvojna leta 2017–2024, borelioza
(`catboost_challenger/lyme_catboost_development_comparison.csv`): CatBoost 1,1826,
GLM 1,3202, zgodovinsko povprečje 1,3358.

KME, rolling-origin 2018–2025 (`kme_region_model/kme_aggregate_metrics.csv` in
`kme_model_selection.json`): GLM (regija + sezonskost + prebivalstvo) 1,2289,
zgodovinsko povprečje po regijah 1,5827, CatBoost z vremenom 1,2076 (boljši v
4 od 8 let, zato ni bil izbran), GLM z vremenom 1,2618, GLM s preteklimi primeri
1,2328.

Odstotki v besedilu: −10,42 % in −11,47 % (razvoj), −4,07 %, −2,93 % in −7,81 %
(2025), RMSE +2,12 % (slabše), podcenjevanje 13,5 % (razmerje opazovano/napovedano
1,157, `lyme_lockbox_calibration_overall.csv`), KME −22,35 %.

Zgodovinsko povprečje nima izračunane Poissonove deviance, ker je za 157 napovedi
predvidelo točno nič primerov, opaženih pa je bilo več; vrednost je takrat
matematično nedefinirana. Zato deviance ni na grafu, ampak samo v besedilu.

## Trije popravki v razdelku o metodah

1. **Poissonova devianca**, ne »deviacija« — deviacija je odklon, devianca je
   merilo prileganja pri štetnih modelih.
2. Podatkovno obdobje: KME zajema 2015–2025, borelioza pa 2016–2025. Natančneje:
   »za obdobje 2015–2025 (podatki o boreliozi od leta 2016)«.
3. Če slika 1 prikazuje objavljeni tedenski signal v aplikaciji, je treba
   povedati, da so tu ovrednoteni raziskovalni modeli (borelioza štiri tedne
   vnaprej, KME osem tednov), objavljeni signal pa je ločen model za tekoči teden,
   ki deluje brez sprotnih prijav primerov.

## Graf

`graf-rezultati-belo-ozadje.png` in `.pdf` (belo ozadje, črn izris), izriše ju
`izris_grafa.py`:

```bash
.venv/bin/python docs/clanek/izris_grafa.py
```
