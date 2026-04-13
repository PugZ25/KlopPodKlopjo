export type SourceLink = {
  label: string
  href?: string
}

export type ContentBlock = {
  title: string
  paragraphs: readonly string[]
}

export const topicNavItems = [
  { label: 'Ixodes ricinus', href: '#ixodes-ricinus' },
  { label: 'klopne bolezni', href: '#klopne-bolezni' },
  { label: 'cepljenje', href: '#cepljenje' },
  { label: 'preventiva', href: '#preventiva' },
  { label: 'odstranitev klopa', href: '#odstranitev-klopa' },
  { label: 'napoved tveganja', href: '#preverjanje-tveganja' },
  { label: 'posebnosti Slovenije', href: '#posebnosti-slovenije' },
] as const

export const ixodesIntro =
  'Ixodes ricinus, znan kot navadni gozdni klop, je najpogostejša vrsta klopa v Evropi in tudi v Sloveniji ter predstavlja enega najpomembnejših prenašalcev nalezljivih bolezni pri ljudeh. Spada med trde oziroma ščitaste klope (družina Ixodidae), kar pomeni, da ima na zgornji strani glavoprsja trdni ščit (scutum).'

export const ixodesSections: readonly ContentBlock[] = [
  {
    title: 'HABITAT',
    paragraphs: [
      'Vrsta je razširjena po skoraj celotni Evropi, njena prisotnost pa je močno odvisna od okoljskih razmer. Klopa najpogosteje najdemo v listnatih in mešanih gozdovih, na gozdnih robovih, v visoki travi in grmičevju, pa tudi v urbanih parkih in vrtovih, če so tam prisotni ustrezni pogoji. Klopi so zelo občutljivi na izsušitev, zato potrebujejo visoko relativno vlažnost (nad 80 %) in okolja z gosto vegetacijo, kjer se ohranja vlažna mikroklima. Njihova razširjenost in številčnost sta tesno povezani tudi s prisotnostjo gostiteljev, predvsem glodalcev in večjih sesalcev, kot je srnjad.',
    ],
  },
  {
    title: 'ŽIVLJENJSKI CIKEL KLOPA',
    paragraphs: [
      'Življenjski cikel klopa poteka v treh razvojnih stopnjah in običajno traja 2 do 3 leta. Poleti, ko je samica pripravljena na parjenje, se pritrdi na gostitelja in privabi samca. Po oploditvi se samica hrani s krvjo gostitelja nato pa odpade na tla in v vlažnem okolju izleže od 1000 do 2000 jajčec, nakar pogine.',
      'Po nekaj tednih, v jeseni se iz jajčec izvalijo ličinke, ki imajo 6 nog in so velike le en milimeter. V tem stadiju tudi prezimijo. Spomladi si poiščejo prvega gostitetelja, ki je ponavadi glodalec ali ptič. Na njem se hranijo par dni, nato pa odpadejo. Od prvega krvnega obroka dalje se lahko klopi okužijo s povzročitelji lymske borelioze ali klopnega meningoencefalitisa, saj so njihovi gostitelji naravni rezervoar povzročiteljev.',
      'Jeseni se ličinke prelevijo v nimfe, ki so velike 2,5 mm in imajo 8 nog. Nimfe prezimijo v listni stelji. Spomladi si poiščejo drugega gostitelja, ki je ponavadi glodalec. Na njem se nekaj dni hranijo, nato odpadejo, se prelevijo v odraslega klopa, ki ponovno prezimi.',
      'Spomladi se odrasli klopi premaknejo na vrh podrasti, kjer prežijo na tretjega gostitelja. Ko se samica pritrdi, je pripravljena na parjenje. Cikel je lahko krajši, če se ličinke izvalijo spomladi in se že pred zimo hranijo na prvem gostitelju.',
    ],
  },
  {
    title: 'KAKO KLOPI NAJDEJO GOSTITELJA?',
    paragraphs: [
      'Odrasli klop spleza na nizko grmičevje in in na konice trav. Med čakanjem se podlage drži s 3. in 4. parom nog, prvi par pa ima iztegnjen v zrak. Če pride mimo gostitelj, ga začuti s posebnim organom, ki zaznava CO2, telesno temperaturo, vlažnost in vibracije. Ob dotiku se oprime gostitelja.',
      'Človek je lahko gostitelj za katerokoli razvojno fazo klopa. Najbolj problematične so nimfe, saj so dovolj male, da jih zlahka spregledamo. Nimfe so odgovorne za večino primerov lymske borelioze.',
    ],
  },
] as const

export const diseaseCards: readonly ContentBlock[] = [
  {
    title: 'LYMSKA BORELIOZA',
    paragraphs: [
      'V Sloveniji je borelioza najpogostejša nalezljiva bolezen, ki jo prenašajo klopi. Pojavlja se po celi državi in letno beležimo okoli 5.000-7.000 zbolelih. Tveganje za okužbo je največje od februarja do novembra. Blage zime in vlažne pomladi spodbujajo pojavnost klopov.',
      'Lmysko boreliozo povzročajo bakterije iz rodu Borrelia, ki so razširjene v evropskem in severnoameriškem prostoru ter v nekaterih državah Azije. Klop se z bakterijo okuži med sesanjem krvi okužene živali, najpogosteje so to mali gozdni sesalci in ptiči, lahko pa tudi večji sesalci, kot so srne.',
      'Ko okužen klop ugrizne človeka, lahko bakterijo prenese preko sline v kožo. Bakterija se nahaja v črevesju klopa in se mora po začetku hranjenja aktivirati in premakniti v klopove žleze slinavke, od koder pride v slino. Ta proces traja 24 do 36 ur, zato zgodnja odstranitev klopa izrazito zmanjša tveganje za okužbo.',
      'Borelioza običajno poteka v treh fazah. V prvi fazi bolezni (3-32 dni po ugrizu okuženega klopa) se pojavijo značilne spremembe na koži. Nastane neboleča rdečina, ki se počasi širi po koži, na sredi bledi in dobi obliko kolobarja. Kožna sprememba je lahko ena sama ali pa jih je več na različnih delih telesa. Pomembno je razlikovati običajno alergično reakcijo kože, ki se lahko pojavi takoj na mestu ugriza od značilnih kožnih sprememb za boreliozo. Kožne spremembe niso vedno prisotne. V drugi in tretji fazi bolezni (lahko tudi več mesecev ali let po okužbi) se pokažejo znaki prizadetosti številnih organov ali organskih sistemov: kože, živčevja, sklepov, mišic, tudi oči in srca.',
      'Boreliozo zdravimo z antibiotiki. Pomembna je zgodnja prepoznava bolezni, saj je zdravljenje v prvi fazi bolezni praviloma zelo učinkovito. Prvo fazo zdravimo s tabletami antibiotika 2 tedna. Kasnejše faze zahtevajo daljši čas jemanja antibiotika ali celo intravensko terapijo z antibiotikom.',
      'Vsak, ki je izpostavljen ugrizom okuženih klopov, je dovzeten za razvoj bolezni. Predhodna okužba ne pušča zaščite pred boleznijo.',
    ],
  },
  {
    title: 'KLOPNI MENINGOENCEFALITIS',
    paragraphs: [
      'Klopni meningoencefalitis (KME) je virusna bolezen osrednjega živčevja, ki je v Sloveniji endemična. Letno zanj zboli okoli 150 ljudi.',
      'KME povzroča virus klopnega meningoencefalitisa iz družine flavivirusov. Virus se nahaja v slini okuženega klopa in se lahko že v nekaj minutah po ugrizu prenese na človeka. Z virusom se lahko okužimo tudi z uživanjem nepasteriziranega mleka ali mlečnih izdelkov narejenih iz mleka okužene živine.',
      'Prvi simptomi bolezni se pojavijo v 7 – 14 dneh po ugrizu. KME običajno poteka v dveh fazah. Začetni simptomi so podobni gripi (glavobol, vročina, bolečine v mišicah, slabost), nato sledi obdobje brez simptomov, ki traja, običajno osem dni. Druga faza se začne s ponovnim dvigom temperature, kar predstavlja začetek meningoencefalitisa (vnetja možganskih ovojnic in možganovine). Klasična trido sestavljajo vročina, otrdelost vratnih mišic in slabost z bruhanjem, spremljajo jo lahko še fotofobija, spremenjeno duševno stanje in epileptični napadi.',
      'Med 70 % in 80% obolelih za KME je asimptomatskih ali pa ima le simptome prve faze. Pri 20 % do 30 % pa se stanje razvije v meningoencefalitis. Pri otrocih in mladostnikih ima bolezen običajno lažji potek kot pri odraslih.',
      'Klopni meningoencefalitis je bolezen, za katero nimamo zdravila, zaščitimo pa se lahko s cepljenjem. Na voljo je le podporno zdravljenje, ki vključuje nesteroidna protivnetna zdravila, pri resnih okvarah osrednjega živčevja pa je včasih potrebna intubacija in ventilacija. Pri starejših bolnikih (posebej starejših od 60 let) se pogosteje pojavlja resen potek bolezni, ki lahko vodi v paralize in večkrat pušča trajne posledice (slabši spomin, motnje ravnotežja, glavobol, motnje govora, slabši sluh, pareze).',
      'Smrtnost je med 0,5 in 2 %.',
    ],
  },
] as const

export const vaccinationParagraphs = [
  'Obolevnost za klopnim meningoencefalitisom je v Sloveniji med najvišjimi v Evropi, letno zboli v povprečju okrog 150 oseb, delež cepljenih oseb pa je zelo nizek.',
  'KME najučinkoviteje preprečujemo s cepljenjem. V Evropi sta registrirani dve inaktivirani cepivi proti KME, obe sta varni in zelo učinkoviti.',
  'Otrok se lahko prvič cepi proti KME po dopolnjenem 1. letu starosti. V letu 2026 je cepljenje brezplačno za otroke, rojene leta 2016 ali kasneje (po dopolnjenem enem letu starosti), in za odrasle, rojene med letoma 1970 in 1983, ki še niso prejeli 3 odmerkov cepiva. Cepiti se je mogoče pri osebnemu zdravniku (telefon ali eNaročanje) ali na območnih enotah NIJZ ali v ambulanti za cepljenje.',
  'Pri cepljenju otrok najprej dobi prvi odmerek. Sledi drugi odmerek čez 1 do 3 mesece in tretji odmerek čez 5 do 12 mesecev po drugem.',
  'Prvi revakcinacijo se opravi z enim odmerkom tri leta po 3. odmerku, naslednje pa na 5 let. Po 60. letu se priporoča poživitveni odmerek na vsaka 3 leta. Poživitveni odmerki so samoplačniški, cena pa se giblje okrog 30 evrov.',
  'Osebe, ki so prebolele KME (laboratorijsko dokazan), so zaščitene proti bolezni in ne potrebujejo cepljenja.',
] as const

export const vaccinationHighlights = [
  {
    title: 'Kje se lahko naročim?',
    text: 'Pri osebnemu zdravniku (telefon ali eNaročanje) ali na območnih enotah NIJZ ali v ambulanti za cepljenje.',
  },
  {
    title: 'Sestava cepiva',
    text: 'V Evropi sta registrirani dve inaktivirani cepivi proti KME, obe sta varni in zelo učinkoviti.',
  },
  {
    title: 'Shema cepljenja',
    text: 'Osnovna serija vsebuje tri odmerke, prva revakcinacijo pa se opravi tri leta po 3. odmerku.',
  },
] as const

export const preventionIntroParagraphs = [
  'Kljub temu da ste cepljeni, pa vas cepivo ščiti le pred KME, medtem ko cepivo za Lymsko boreliozo še ne obstaja. Tako navkljub cepivu, velja previdnost ko pride do težko pričakovanega pohoda, kampiranja ali raziskovanja bližnjega gozda.',
  'Tako ti priporočamo, da kar se da dosledno upoštevaš naslednje ukrepe:',
] as const

export const preventionGroups = [
  {
    title: 'PRED ODHODOM:',
    items: [
      'Obleci svetla oblačila (klopi bodo tako bolj vidni!)',
      'Nosi dolge hlače in dolge rokave',
      'Hlače zatlači v nogavice ali čevlje',
      'Uporabi repelent proti klopom (na koži in oblačilih)',
    ],
  },
  {
    title: 'V NARAVI:',
    items: [
      'Drži se urejenih poti',
      'Izogibaj se podrastju, visoki travi in grmovju',
      'Izogibaj se sedenju in ležanju neposredno na tleh',
    ],
  },
  {
    title: 'PO VRNITVI DOMOV:',
    items: [
      'Čimprej se stuširaj',
      'Temeljito preglej celo telo, še posebej za ušesi, na lasišču, pod pazduhami, v pregibi kolen, v dimljah)',
      'Preglej tudi oblačila, nahrbtnik in hišne ljubljenčke!',
      'Če opaziš klopa, ga čimprej odstrani.',
    ],
  },
] as const

export const removalIntro =
  'Če pri pregledu telesa opazimo klopa, ga čimprej previdno odstranimo.'

export const removalSteps = [
  'S koničasto pinceto zgrabimo klopa čim bližje koži. Izogibamo se stiskanju trupa.',
  'Klopa izvlečemo z enakomernim gibom. Pri tem ga ne sučemo, saj to poveča tveganje, da v koži ostanejo deli klopa. Če do tega pride, lahko dele klopa prav tako izvlečemo s pinceto.',
  'Klopa zavijemo v lepilni trak, ga splaknemo v školjki ali pa ga potopimo v alkohol ali razkužilo. Ne zmečkamo klopa s prsti.',
  'Po odstranitvi si umijemo roke in ugrizno mesto z milom in vodo ali pa uporabimo razkužilo.',
] as const

export const removalImportantParagraphs = [
  'Za odstranjevanje klopov ne uporabljamo olja, krem, petroleja ali drugih mazil.',
] as const

export const regionInsight = {
  sloveniaIntro:
    'Velik del države je že več kot 70 let endemično območje za Lymsko boreliozo, pri čemer je treba poudariti, da se incidenca LB nenehno povečuje. Poleg tega je Slovenija med vodilnimi evropskimi državami po številu okuženih z LB. V zadnjem desetletju je bilo v Sloveniji letno zabeleženih med 5000 in 7000 primerov okužbe z LB. Smo tudi v endemičnem področju za klopni meningoencefalitis (KME).',
  sloveniaHighlights: [
    {
      title: 'Območje tveganja',
      value: 'celotna Slovenija',
      text: 'Borelioza se pojavlja po vsej državi, z izrazito obremenitvijo v zadnjem desetletju.',
    },
    {
      title: 'Letna pojavnost LB',
      value: '5.000-7.000',
      text: 'V Sloveniji vsako leto beležimo med pet in sedem tisoč primerov okužbe z LB.',
    },
    {
      title: 'Evropski vrh',
      value: 'visoka incidenca',
      text: 'Slovenija je med vodilnimi evropskimi državami po številu okuženih z LB.',
    },
  ],
  ixodesSources: [
    {
      label:
        'www.ecdc.europa.eu/en/disease-vectors/facts/tick-factsheets/ixodes-ricinus',
      href: 'https://www.ecdc.europa.eu/en/disease-vectors/facts/tick-factsheets/ixodes-ricinus',
    },
  ],
} as const

export const diseaseSources = [
  {
    label: 'NIJZ. Lymska borelioza in KME - tedenska poročila NIJZ.',
    href: 'https://nijz.si/nalezljive-bolezni/lymska-borelioza-in-kme-tedenska-porocila-nijz/',
  },
  {
    label:
      'Ogrinc K. Algoritem obravnave odraslega bolnika z lymsko boreliozo. Ljubljana: Univerzitetni klinični center Ljubljana; 2019.',
  },
  {
    label: 'NIJZ. Lymska borelioza.',
    href: 'https://nijz.si/nalezljive-bolezni/nalezljive-bolezni-od-a-do-z/lymska-borelioza/',
  },
  {
    label: 'NIJZ. Klopni meningoencefalitis.',
    href: 'https://nijz.si/nalezljive-bolezni/nalezljive-bolezni-od-a-do-z/klopni-meningoencefalitis/',
  },
  {
    label: 'NIJZ, Območna enota Novo mesto. Varni pred klopi v naravi.',
    href: 'https://nijz.si/obmocna-enota-novo-mesto/varni-pred-klopi-v-naravi/',
  },
] as const

export const vaccinationSources = [
  {
    label: 'NIJZ. Cepljenje proti klopnemu meningoencefalitisu.',
    href: 'https://nijz.si/nalezljive-bolezni/cepljenje/cepljenje-proti-klopnemu-meningoencefalitisu/',
  },
  {
    label: 'NIJZ. Program cepljenja in zaščite z zdravili.',
    href: 'https://nijz.si/nalezljive-bolezni/cepljenje/program-cepljenja-in-zascite-z-zdravili/',
  },
  {
    label: 'CDC. FSME-IMMUN development 2000-2020.',
    href: 'https://stacks.cdc.gov/view/cdc/157609/cdc_157609_DS1.pdf',
  },
] as const

export const removalSources = [
  {
    label: 'NIJZ, Območna enota Novo mesto. Varni pred klopi v naravi.',
    href: 'https://nijz.si/obmocna-enota-novo-mesto/varni-pred-klopi-v-naravi/',
  },
] as const

export const sloveniaSources = [
  {
    label:
      'Donša D, Grujić VJ, Pipenbaher N, Ivajnšič D. The Lyme Borreliosis Spatial Footprint in the 21st Century: A Key Study of Slovenia.',
    href: 'https://doi.org/10.3390/ijerph182212061',
  },
] as const
