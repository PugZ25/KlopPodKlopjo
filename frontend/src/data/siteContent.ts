export const primaryNavItems = [
  { label: 'Preverjanje tveganja', href: '#preverjanje-tveganja' },
  { label: 'Zaščita', href: '#zascita' },
  { label: 'Informacije', href: '#znanje' },
] as const

export const topicNavItems = [
  { label: 'Preverite tveganje', href: '#preverjanje-tveganja' },
  { label: 'Cepljenje', href: '#cepljenje' },
  { label: 'Preventiva', href: '#preventiva' },
  { label: 'Odstranitev klopa', href: '#odstranitev-klopa' },
  { label: 'Klopne bolezni', href: '#klopne-bolezni' },
  { label: 'Posebnosti Slovenije', href: '#posebnosti-slovenije' },
] as const

export const noticeText =
  'Cepljenje proti KME je mogoče pri osebnem zdravniku, na območnih enotah NIJZ ali v ambulanti za cepljenje. V letu 2026 je za določene starostne skupine brezplačno.'

export const heroStats = [
  {
    label: 'Lymska borelioza letno',
    value: '5.000-7.000',
    description: 'prijavljenih primerov okužbe v Sloveniji v zadnjem desetletju.',
  },
  {
    label: 'KME letno',
    value: 'okoli 150',
    description: 'povprečno število obolelih za klopnim meningoencefalitisom.',
  },
  {
    label: 'Endemičnost',
    value: '70+ let',
    description: 'Slovenija ostaja endemično območje za lymsko boreliozo.',
  },
  {
    label: 'Brezplačno cepljenje 2026',
    value: '2016+ in 1970-1983',
    description: 'za otroke in del odraslih, ki še niso prejeli 3 odmerkov cepiva.',
  },
] as const

export const ixodesSections = [
  {
    title: 'Habitat',
    paragraphs: [
      'Vrsta je razširjena po skoraj celotni Evropi, njena prisotnost pa je močno odvisna od okoljskih razmer.',
      'Klopa najpogosteje najdemo v listnatih in mešanih gozdovih, na gozdnih robovih, v visoki travi in grmičevju, pa tudi v urbanih parkih in vrtovih, če so tam prisotni ustrezni pogoji.',
      'Klopi so zelo občutljivi na izsušitev, zato potrebujejo visoko relativno vlažnost, nad 80 odstotkov, in okolja z gosto vegetacijo, kjer se ohranja vlažna mikroklima.',
      'Njihova razširjenost in številčnost sta tesno povezani tudi s prisotnostjo gostiteljev, predvsem glodalcev in večjih sesalcev, kot je srnjad.',
    ],
  },
  {
    title: 'Življenjski cikel klopa',
    paragraphs: [
      'Življenjski cikel klopa poteka v treh razvojnih stopnjah in običajno traja 2 do 3 leta. Poleti se samica po oploditvi hrani s krvjo gostitelja, nato odpade na tla, izleže od 1.000 do 2.000 jajčec in pogine.',
      'Jeseni se iz jajčec izvalijo ličinke s šestimi nogami. Spomladi si poiščejo prvega gostitelja, najpogosteje glodalca ali ptico, in se po nekajdnevnem hranjenju znova spustijo na tla.',
      'Od prvega krvnega obroka dalje se lahko klopi okužijo s povzročitelji lymske borelioze ali klopnega meningoencefalitisa, saj so njihovi gostitelji naravni rezervoar povzročiteljev.',
      'Jeseni se ličinke prelevijo v nimfe, velike približno 2,5 milimetra, ki prezimijo v listni stelji. Po naslednjem hranjenju se razvijejo v odraslega klopa.',
      'Spomladi se odrasli klopi premaknejo na vrh podrasti, kjer prežijo na tretjega gostitelja. Cikel je lahko krajši, če se ličinke izvalijo že spomladi in se še pred zimo hranijo na prvem gostitelju.',
    ],
  },
  {
    title: 'Kako klopi najdejo gostitelja?',
    paragraphs: [
      'Odrasli klop spleza na nizko grmičevje in na konice trav. Med čakanjem se podlage drži s tretjim in četrtim parom nog, prvi par pa ima iztegnjen v zrak.',
      'Če pride mimo gostitelj, ga zazna s posebnim organom, ki prepoznava ogljikov dioksid, telesno temperaturo, vlažnost in vibracije. Ob dotiku se hitro oprime gostitelja.',
      'Človek je lahko gostitelj za katerokoli razvojno fazo klopa. Najbolj problematične so nimfe, saj so dovolj majhne, da jih zlahka spregledamo, in so odgovorne za večino primerov lymske borelioze.',
    ],
  },
] as const

export const vaccinationHighlights = [
  {
    title: 'Kje se lahko naročim?',
    text: 'Pri osebnem zdravniku, preko telefona ali eNaročanja, na območnih enotah NIJZ ali v ambulanti za cepljenje.',
  },
  {
    title: 'Sestava cepiva',
    text: 'V Evropi sta registrirani dve inaktivirani cepivi proti KME, obe varni in zelo učinkoviti.',
  },
  {
    title: 'Shema cepljenja',
    text: 'Osnovna serija vsebuje tri odmerke, prva revakcinacija pa sledi tri leta po tretjem odmerku.',
  },
] as const

export const preventionGroups = [
  {
    title: 'Pred odhodom',
    items: [
      'Obleci svetla oblačila, da so klopi bolj vidni.',
      'Nosi dolge hlače in dolge rokave.',
      'Hlače zatlači v nogavice ali čevlje.',
      'Uporabi repelent proti klopom na koži in oblačilih.',
    ],
  },
  {
    title: 'V naravi',
    items: [
      'Drži se urejenih poti.',
      'Izogibaj se podrastju, visoki travi in grmovju.',
      'Izogibaj se sedenju in ležanju neposredno na tleh.',
    ],
  },
  {
    title: 'Po vrnitvi domov',
    items: [
      'Čim prej se stuširaj.',
      'Temeljito preglej celo telo, še posebej za ušesi, na lasišču, pod pazduhami, v pregibih kolen in v dimljah.',
      'Preglej tudi oblačila, nahrbtnik in hišne ljubljenčke.',
    ],
  },
] as const

export const removalSteps = [
  'S koničasto pinceto zgrabimo klopa čim bližje koži in se izogibamo stiskanju trupa.',
  'Klopa izvlečemo z enakomernim gibom. Ne sučemo ga, saj to poveča tveganje, da v koži ostanejo deli klopa.',
  'Če v koži ostanejo deli klopa, jih lahko previdno izvlečemo s pinceto.',
  'Po odstranitvi si umijemo roke in ugrizno mesto z milom in vodo ali uporabimo razkužilo.',
] as const

export const regionInsight = {
  sloveniaIntro:
    'Velik del države je že več kot 70 let endemično območje za lymsko boreliozo, incidenca bolezni pa se nenehno povečuje. Slovenija je tudi endemično območje za klopni meningoencefalitis, zato je ozaveščenost o klopih pri nas zdravstveno še posebej pomembna.',
  sloveniaHighlights: [
    {
      title: 'Območje tveganja',
      value: 'celotna Slovenija',
      text: 'Borelioza se pojavlja po vsej državi, z izrazito obremenitvijo v zadnjem desetletju.',
    },
    {
      title: 'Letna pojavnost LB',
      value: '5.000-7.000',
      text: 'V Sloveniji vsako leto beležimo med pet in sedem tisoč primerov okužbe z lymsko boreliozo.',
    },
    {
      title: 'Evropski vrh',
      value: 'visoka incidenca',
      text: 'Slovenija je med vodilnimi evropskimi državami po številu okuženih z lymsko boreliozo.',
    },
  ],
  ixodesSources: [
    {
      label:
        'Gray J et al. Pathogens transmitted by Ixodes ricinus. Ticks and Tick-borne Diseases. 2024.',
      href: 'https://doi.org/10.1016/j.ttbdis.2024.102402',
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
      'Ogrinc K. Algoritem obravnave odraslega bolnika z lymsko boreliozo. UKC Ljubljana, 2019.',
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
