# Metodologija za žirijo

Ta dokument je namenjen hitremu branju pred predstavitvijo. Napisano je tako, da
lahko poveš po domače in brez preveč tehničnega jezika.

## Verzija v 20 sekundah

"Naša metodologija temelji na tem, da za vsako občino združimo več javnih
podatkovnih virov v enoten tedenski pregled. Upoštevamo predvsem vreme,
značilnosti prostora in sezono, nato pa s CatBoost modelom ocenimo, kje so v
naslednjih tednih okoljski pogoji bolj ugodni za pojav borelioze ali KME. Rezultat
uporabniku pokažemo kot enostaven razred tveganja: nizko, srednje ali visoko."

## Verzija v 45 do 60 sekundah

"Najprej združimo podatke na isti enoti, torej po občini in po tednih. V model
vključimo vremenske podatke, na primer temperaturo, vlago in padavine, potem
značilnosti prostora, kot so nadmorska višina, gozdnatost in raba tal, ter
sezonske vzorce skozi leto. Tako dobimo za vsako občino enoten profil razmer.

Nato uporabimo CatBoost, ki se iz zgodovinskih primerov nauči, katere kombinacije
teh dejavnikov so bile v preteklosti povezane z večjim tveganjem. Pomembno je, da
model preverjamo časovno pravilno: učimo ga na starejših tednih, testiramo pa na
novejših, da ne mešamo prihodnosti v preteklost.

Na koncu rezultata ne predstavljamo kot diagnozo ali točno medicinsko verjetnost,
ampak kot razumljiv relativni indeks tveganja za občino: nizko, srednje ali
visoko."

## Kako po domače razložiti CatBoost

"CatBoost si lahko predstavljaš kot zelo veliko zaporedje majhnih odločitev. Model
vedno znova preverja, katere kombinacije pogojev, recimo toplejše vreme, več vlage
in bolj gozdnata okolica, so bile v preteklosti pogosteje povezane s pojavom
bolezni. Iz veliko takih drobnih pravil potem sestavi končno oceno tveganja."

Kratek še bolj preprost stavek:

"CatBoost iz zgodovinskih podatkov prepozna vzorce in iz njih oceni, kje je
tveganje relativno večje."

## Kaj smo dali not

Za predstavitev lahko rečeš:

- vremenske podatke: temperatura, vlaga, padavine, stanje tal
- prostorske podatke: nadmorska višina in relief
- podatke o okolju: gozd, travniki, kmetijske in urbane površine
- sezonski vidik: v katerem delu leta smo

Če želiš malo širše in še vedno varno:

"V širšem projektu združujemo več javnih virov podatkov na ravni občin in tednov,
za trenutni spletni prikaz pa uporabljamo predvsem okoljske, prostorske in
sezonske značilke."

## Kako deluje rezultat na strani

- za boreliozo model gleda signal za naslednje 4 tedne
- za KME model gleda signal za naslednjih 8 tednov
- surovi modelni izhod pretvorimo v razumljive razrede `Nizko`, `Srednje`, `Visoko`
- rezultat je relativni občinski indeks, ne diagnoza

Če kdo vpraša bolj natančno:

"Razrede določimo glede na to, kam posamezna občina pade znotraj zgodovinske
porazdelitve modela. Torej ne gre za ročno izmišljene pragove, ampak za stabilno
primerjavo z dosedanjimi rezultati modela."

Najbolj varen stavek za žirijo:

"Uporabniku ne kažemo gole tehnične verjetnosti, ampak poenostavljen in razumljiv
indikator relativnega tveganja za njegovo občino."

## O drugih modelih

"Poleg modelov, ki jih prikazujemo na spletni strani, smo razvili tudi dodatne
raziskovalne modele. Z njimi smo preverjali, kateri dejavniki imajo največ
napovedne vrednosti, in testirali kratkoročne epidemiološke napovedi, da smo
lahko primerjali različne pristope in izbrali najbolj smiseln model za javni
prikaz."

## Kratek govor za slide o boreliozi v1

Zelo kratka verzija:

"Tukaj pokažemo, da model dobro sledi dejanskim podatkom tudi na validaciji in
testu, torej na tednih, ki jih pri učenju ni videl. To nam pove, da model ne dela
samo na trening podatkih, ampak ima tudi realno napovedno vrednost."

Malo bolj konkretna verzija:

"Pri boreliozi v1 vidimo, da model podobno dobro deluje tako na validacijskem kot
na testnem delu, kar je dober znak stabilnosti. Testni `R²` je okoli `0,663`,
validacijski pa okoli `0,683`, zato ga lahko uporabljamo kot močan napovedni
baseline za boreliozo."

Če želiš še bolj po domače:

"Poenostavljeno: model dovolj dobro ujame vzorec gibanja borelioze tudi na novih
podatkih, zato vemo, da ni naučen samo na pamet."

Varen zaključni stavek za ta slide:

"Model ni popoln, je pa dovolj dober in dovolj stabilen, da ga uporabljamo kot
referenčni napovedni model za boreliozo."

## Če te vprašajo, zakaj je to metodološko smiselno

- ker združimo več različnih signalov in ne gledamo samo enega podatka
- ker vse podatke uskladimo na isto časovno in prostorsko raven
- ker model preverjamo na prihodnjih tednih, ne na istih podatkih, na katerih se uči
- ker rezultat prevedemo v obliko, ki je razumljiva tudi netehničnemu uporabniku

## Česa raje ne trdi

- da model postavlja medicinsko diagnozo
- da rezultat pomeni točno osebno verjetnost okužbe
- da je to nadomestilo za zdravnika ali uradne epidemiološke ocene

## Moj predlog za najbolj naraven govor

"Mi smo več javnih podatkov, predvsem vreme, prostor in sezonske vzorce, povezali
na ravni občin in tednov. Nato smo s CatBoost modelom iz zgodovinskih podatkov
naučili sistem, da prepozna kombinacije razmer, ki so povezane z večjim tveganjem
za boreliozo ali KME. Ključ je, da model preverjamo na kasnejših tednih, zato je
pristop metodološko bolj pošten. Končni rezultat pa namenoma poenostavimo v nizko,
srednje ali visoko tveganje, da je rešitev razumljiva tudi širši javnosti."

## Repo reference

- `docs/metodologija/environmental-risk-env-v2-pragovi.md`
- `docs/metodologija/live-hackathon-obcina-open-meteo.md`
- `docs/metodologija/tick-borne-catboost-dataset.md`
- `docs/predstavitev/metodologija-zirija.html`
