export type RiskLevel = 'Nizko' | 'Srednje' | 'Visoko'

export type DiseaseModelKey = 'borelioza' | 'kme'

export type LiveMunicipalityRiskLocation = {
  id: string
  municipalityCode: string
  municipalityName: string
  score: number
  level: RiskLevel
  trendDeltaScore: number
  trendLabel: string
  weekStart: string
  weekEnd: string
  coordinates: [number, number]
}

export type LiveMunicipalityRiskModel = {
  key: DiseaseModelKey
  diseaseLabel: string
  modelId: string
  legacyResearchModelId: string
  asOfDate: string
  generatedAt: string
  referenceWeekStart: string
  referenceWeekEnd: string
  snapshotLabel: string
  weatherSource: string
  methodologyNote: string
  purpose: string
  disclaimer: string
  scoreExplanation: string
  topDrivers: string[]
  thresholds: {
    lowUpper: number
    mediumUpper: number
  }
  locations: LiveMunicipalityRiskLocation[]
  featuredLocations: Array<{
    municipalityName: string
    municipalityCode: string
    level: RiskLevel
    score: number
    id: string
  }>
}

export const liveMunicipalityRiskModels: Record<DiseaseModelKey, LiveMunicipalityRiskModel> = {
  "borelioza": {
    "key": "borelioza",
    "diseaseLabel": "Borelioza",
    "modelId": "catboost_tick_borne_lyme_env_v2",
    "legacyResearchModelId": "catboost_tick_borne_lyme_env_per100k_v1",
    "asOfDate": "2026-04-22",
    "generatedAt": "2026-04-22T17:20:30",
    "referenceWeekStart": "2026-04-13",
    "referenceWeekEnd": "2026-04-19",
    "snapshotLabel": "zadnji zaklju\u010deni tedenski hackathon snapshot",
    "weatherSource": "Open-Meteo best-match hourly weather",
    "methodologyNote": "Live hackathon demo uporablja Open-Meteo hourly weather za zadnjih 6 tednov, tedensko agregacijo po istem feature kontraktu kot env_v2 in reprezentativno to\u010dko znotraj GURS poligona posamezne ob\u010dine. Score temelji na surovi napovedi env_v2 klasifikacijskega modela in je namenjen primerjavi ob\u010din znotraj iste bolezni.",
    "purpose": "Live hackathon relativni ob\u010dinski okoljski indeks za boreliozo.",
    "disclaimer": "To ni diagnoza ali individualna verjetnost bolezni. Gre za relativni ob\u010dinski risk indeks, ki je uporaben predvsem za primerjavo lokacij znotraj iste bolezni.",
    "scoreExplanation": "Score je relativni ob\u010dinski indeks 0-100, izra\u010dunan kot empiri\u010dni percentil surove napovedi modela znotraj holdout distribucije istega env_v2 modela.",
    "topDrivers": [
      "sezonski signal",
      "urbaniziranost",
      "tip rabe tal",
      "visinska raznolikost",
      "razgiban relief"
    ],
    "thresholds": {
      "lowUpper": 0.3104672754,
      "mediumUpper": 0.6677368232
    },
    "locations": [
      {
        "id": "borelioza-52",
        "municipalityCode": "52",
        "municipalityName": "Kranj",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25405493617421,
          14.258306205043977
        ]
      },
      {
        "id": "borelioza-61",
        "municipalityCode": "61",
        "municipalityName": "Ljubljana",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.06002832481608,
          14.591227050900212
        ]
      },
      {
        "id": "borelioza-1",
        "municipalityCode": "1",
        "municipalityName": "Ajdov\u0161\u010dina",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91223397414079,
          13.876160443372136
        ]
      },
      {
        "id": "borelioza-70",
        "municipalityCode": "70",
        "municipalityName": "Maribor",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.566868391230585,
          15.631952095403161
        ]
      },
      {
        "id": "borelioza-84",
        "municipalityCode": "84",
        "municipalityName": "Nova Gorica",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.97092502839293,
          13.721150401050998
        ]
      },
      {
        "id": "borelioza-102",
        "municipalityCode": "102",
        "municipalityName": "Radovljica",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.344957557875674,
          14.197636337189738
        ]
      },
      {
        "id": "borelioza-41",
        "municipalityCode": "41",
        "municipalityName": "Jesenice",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.445948023027015,
          14.066153130492548
        ]
      },
      {
        "id": "borelioza-50",
        "municipalityCode": "50",
        "municipalityName": "Koper",
        "score": 97,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.51729692077614,
          13.845644980214278
        ]
      },
      {
        "id": "borelioza-63",
        "municipalityCode": "63",
        "municipalityName": "Ljutomer",
        "score": 96,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52220953072839,
          16.131317625513894
        ]
      },
      {
        "id": "borelioza-128",
        "municipalityCode": "128",
        "municipalityName": "Tolmin",
        "score": 96,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.14382787419562,
          13.789384629736421
        ]
      },
      {
        "id": "borelioza-85",
        "municipalityCode": "85",
        "municipalityName": "Novo mesto",
        "score": 96,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.78083464918963,
          15.210193521178581
        ]
      },
      {
        "id": "borelioza-136",
        "municipalityCode": "136",
        "municipalityName": "Vipava",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.82132699262401,
          13.980192683772628
        ]
      },
      {
        "id": "borelioza-43",
        "municipalityCode": "43",
        "municipalityName": "Kamnik",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.27507789786611,
          14.625372343893963
        ]
      },
      {
        "id": "borelioza-113",
        "municipalityCode": "113",
        "municipalityName": "Slovenska Bistrica",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.407381712420836,
          15.563642140833664
        ]
      },
      {
        "id": "borelioza-122",
        "municipalityCode": "122",
        "municipalityName": "\u0160kofja Loka",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.16882510512077,
          14.306552332367522
        ]
      },
      {
        "id": "borelioza-96",
        "municipalityCode": "96",
        "municipalityName": "Ptuj",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.441384397919784,
          15.886057811037922
        ]
      },
      {
        "id": "borelioza-140",
        "municipalityCode": "140",
        "municipalityName": "Vrhnika",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94762357863712,
          14.287738246748727
        ]
      },
      {
        "id": "borelioza-90",
        "municipalityCode": "90",
        "municipalityName": "Piran",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.49274890235444,
          13.61379369688393
        ]
      },
      {
        "id": "borelioza-23",
        "municipalityCode": "23",
        "municipalityName": "Dom\u017eale",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.15074721202056,
          14.626624858204789
        ]
      },
      {
        "id": "borelioza-8",
        "municipalityCode": "8",
        "municipalityName": "Brezovica",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94786493630048,
          14.418009047652001
        ]
      },
      {
        "id": "borelioza-94",
        "municipalityCode": "94",
        "municipalityName": "Postojna",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.79035444806679,
          14.157811302015979
        ]
      },
      {
        "id": "borelioza-120",
        "municipalityCode": "120",
        "municipalityName": "\u0160entjur",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.18851791002033,
          15.406013006743873
        ]
      },
      {
        "id": "borelioza-13",
        "municipalityCode": "13",
        "municipalityName": "Cerknica",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.798316218528036,
          14.344880376684069
        ]
      },
      {
        "id": "borelioza-103",
        "municipalityCode": "103",
        "municipalityName": "Ravne na Koro\u0161kem",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.548379514222276,
          14.975105293957746
        ]
      },
      {
        "id": "borelioza-40",
        "municipalityCode": "40",
        "municipalityName": "Izola",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.51045419293274,
          13.659267020509787
        ]
      },
      {
        "id": "borelioza-71",
        "municipalityCode": "71",
        "municipalityName": "Medvode",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.134643179494105,
          14.401236528773666
        ]
      },
      {
        "id": "borelioza-54",
        "municipalityCode": "54",
        "municipalityName": "Kr\u0161ko",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94614748884751,
          15.46067902792008
        ]
      },
      {
        "id": "borelioza-87",
        "municipalityCode": "87",
        "municipalityName": "Ormo\u017e",
        "score": 90,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.43923237384557,
          16.122467447626843
        ]
      },
      {
        "id": "borelioza-46",
        "municipalityCode": "46",
        "municipalityName": "Kobarid",
        "score": 90,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.24302837192627,
          13.546950740104418
        ]
      },
      {
        "id": "borelioza-190",
        "municipalityCode": "190",
        "municipalityName": "\u017dalec",
        "score": 90,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.26111485109752,
          15.156994659796197
        ]
      },
      {
        "id": "borelioza-117",
        "municipalityCode": "117",
        "municipalityName": "\u0160en\u010dur",
        "score": 90,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23942277871478,
          14.419716721996306
        ]
      },
      {
        "id": "borelioza-64",
        "municipalityCode": "64",
        "municipalityName": "Logatec",
        "score": 90,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.9423203388053,
          14.179699694323777
        ]
      },
      {
        "id": "borelioza-192",
        "municipalityCode": "192",
        "municipalityName": "\u017dirovnica",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.406361601715595,
          14.164011004434988
        ]
      },
      {
        "id": "borelioza-12",
        "municipalityCode": "12",
        "municipalityName": "Cerklje na Gorenjskem",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25525345774459,
          14.503642347119424
        ]
      },
      {
        "id": "borelioza-160",
        "municipalityCode": "160",
        "municipalityName": "Ho\u010de-Slivnica",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.490054688189225,
          15.610380143423317
        ]
      },
      {
        "id": "borelioza-11",
        "municipalityCode": "11",
        "municipalityName": "Celje",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25474084428838,
          15.284333781255828
        ]
      },
      {
        "id": "borelioza-21",
        "municipalityCode": "21",
        "municipalityName": "Dobrova-Polhov Gradec",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.059704146138635,
          14.321669412771623
        ]
      },
      {
        "id": "borelioza-129",
        "municipalityCode": "129",
        "municipalityName": "Trbovlje",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.13733695980865,
          15.044375862598683
        ]
      },
      {
        "id": "borelioza-166",
        "municipalityCode": "166",
        "municipalityName": "Kri\u017eevci",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56678423380212,
          16.117607164937617
        ]
      },
      {
        "id": "borelioza-131",
        "municipalityCode": "131",
        "municipalityName": "Tr\u017ei\u010d",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.38054018463163,
          14.332766698876704
        ]
      },
      {
        "id": "borelioza-75",
        "municipalityCode": "75",
        "municipalityName": "Miren-Kostanjevica",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.859821002386994,
          13.64983376393198
        ]
      },
      {
        "id": "borelioza-37",
        "municipalityCode": "37",
        "municipalityName": "Ig",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.93329916174528,
          14.511092954849847
        ]
      },
      {
        "id": "borelioza-27",
        "municipalityCode": "27",
        "municipalityName": "Gorenja vas-Poljane",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.10892470832346,
          14.127270278645835
        ]
      },
      {
        "id": "borelioza-114",
        "municipalityCode": "114",
        "municipalityName": "Slovenske Konjice",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.324744778194386,
          15.449770717290768
        ]
      },
      {
        "id": "borelioza-123",
        "municipalityCode": "123",
        "municipalityName": "\u0160kofljica",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.956574131994586,
          14.578745574374771
        ]
      },
      {
        "id": "borelioza-32",
        "municipalityCode": "32",
        "municipalityName": "Grosuplje",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.944248714331906,
          14.664212172553189
        ]
      },
      {
        "id": "borelioza-80",
        "municipalityCode": "80",
        "municipalityName": "Murska Sobota",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.64944285646449,
          16.180008501955584
        ]
      },
      {
        "id": "borelioza-91",
        "municipalityCode": "91",
        "municipalityName": "Pivka",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.68861836877859,
          14.228707926505304
        ]
      },
      {
        "id": "borelioza-29",
        "municipalityCode": "29",
        "municipalityName": "Gornja Radgona",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.63619990843724,
          15.9666600915219
        ]
      },
      {
        "id": "borelioza-36",
        "municipalityCode": "36",
        "municipalityName": "Idrija",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.98377995176204,
          14.000525261117094
        ]
      },
      {
        "id": "borelioza-17",
        "municipalityCode": "17",
        "municipalityName": "\u010crnomelj",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.52531358153176,
          15.21046961172452
        ]
      },
      {
        "id": "borelioza-59",
        "municipalityCode": "59",
        "municipalityName": "Lendava",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55480322983082,
          16.443293714800866
        ]
      },
      {
        "id": "borelioza-112",
        "municipalityCode": "112",
        "municipalityName": "Slovenj Gradec",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.49232870395046,
          15.090728012234134
        ]
      },
      {
        "id": "borelioza-2",
        "municipalityCode": "2",
        "municipalityName": "Beltinci",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.60790187625657,
          16.23183338966472
        ]
      },
      {
        "id": "borelioza-201",
        "municipalityCode": "201",
        "municipalityName": "Ren\u010de-Vogrsko",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.89501134194833,
          13.677466938393653
        ]
      },
      {
        "id": "borelioza-3",
        "municipalityCode": "3",
        "municipalityName": "Bled",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34851196309823,
          14.069126047452333
        ]
      },
      {
        "id": "borelioza-111",
        "municipalityCode": "111",
        "municipalityName": "Se\u017eana",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.72640766803438,
          13.889808282981946
        ]
      },
      {
        "id": "borelioza-60",
        "municipalityCode": "60",
        "municipalityName": "Litija",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.049658676044096,
          14.991181473283978
        ]
      },
      {
        "id": "borelioza-142",
        "municipalityCode": "142",
        "municipalityName": "Zagorje ob Savi",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.128801067769395,
          14.960344642392293
        ]
      },
      {
        "id": "borelioza-73",
        "municipalityCode": "73",
        "municipalityName": "Metlika",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.650007741795676,
          15.33904423353761
        ]
      },
      {
        "id": "borelioza-119",
        "municipalityCode": "119",
        "municipalityName": "\u0160entjernej",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.82490605624554,
          15.318888102090748
        ]
      },
      {
        "id": "borelioza-57",
        "municipalityCode": "57",
        "municipalityName": "La\u0161ko",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.12804517838802,
          15.269594900971004
        ]
      },
      {
        "id": "borelioza-39",
        "municipalityCode": "39",
        "municipalityName": "Ivan\u010dna Gorica",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.90422389415425,
          14.812022485584954
        ]
      },
      {
        "id": "borelioza-133",
        "municipalityCode": "133",
        "municipalityName": "Velenje",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.37450714272869,
          15.135691606302903
        ]
      },
      {
        "id": "borelioza-183",
        "municipalityCode": "183",
        "municipalityName": "\u0160empeter-Vrtojba",
        "score": 80,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91777884379731,
          13.651647350069668
        ]
      },
      {
        "id": "borelioza-78",
        "municipalityCode": "78",
        "municipalityName": "Moravske Toplice",
        "score": 80,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.71051554569473,
          16.27450061196018
        ]
      },
      {
        "id": "borelioza-146",
        "municipalityCode": "146",
        "municipalityName": "\u017delezniki",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.21826950579093,
          14.12031594808045
        ]
      },
      {
        "id": "borelioza-116",
        "municipalityCode": "116",
        "municipalityName": "Sveti Jurij ob \u0160\u010davnici",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56155714657142,
          16.018594362570987
        ]
      },
      {
        "id": "borelioza-82",
        "municipalityCode": "82",
        "municipalityName": "Naklo",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.287306949547784,
          14.290469335122943
        ]
      },
      {
        "id": "borelioza-38",
        "municipalityCode": "38",
        "municipalityName": "Ilirska Bistrica",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.577291675053395,
          14.297163875431005
        ]
      },
      {
        "id": "borelioza-9",
        "municipalityCode": "9",
        "municipalityName": "Bre\u017eice",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.93758133032827,
          15.632917161397213
        ]
      },
      {
        "id": "borelioza-7",
        "municipalityCode": "7",
        "municipalityName": "Brda",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.016115323055345,
          13.549030517054824
        ]
      },
      {
        "id": "borelioza-106",
        "municipalityCode": "106",
        "municipalityName": "Roga\u0161ka Slatina",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23776175292087,
          15.627106289016217
        ]
      },
      {
        "id": "borelioza-44",
        "municipalityCode": "44",
        "municipalityName": "Kanal",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.08408342299698,
          13.663446283081377
        ]
      },
      {
        "id": "borelioza-109",
        "municipalityCode": "109",
        "municipalityName": "Semi\u010d",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.65247113774323,
          15.1531953913182
        ]
      },
      {
        "id": "borelioza-151",
        "municipalityCode": "151",
        "municipalityName": "Braslov\u010de",
        "score": 77,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.28041457558507,
          15.017620841664286
        ]
      },
      {
        "id": "borelioza-14",
        "municipalityCode": "14",
        "municipalityName": "Cerkno",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.12457099554262,
          13.968090156470707
        ]
      },
      {
        "id": "borelioza-110",
        "municipalityCode": "110",
        "municipalityName": "Sevnica",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.008602808339205,
          15.26233339155699
        ]
      },
      {
        "id": "borelioza-5",
        "municipalityCode": "5",
        "municipalityName": "Borovnica",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91121899380177,
          14.383328935785617
        ]
      },
      {
        "id": "borelioza-169",
        "municipalityCode": "169",
        "municipalityName": "Miklav\u017e na Dravskem polju",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.488367615491015,
          15.701639787840676
        ]
      },
      {
        "id": "borelioza-138",
        "municipalityCode": "138",
        "municipalityName": "Vodice",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.17058318883487,
          14.498940239372367
        ]
      },
      {
        "id": "borelioza-49",
        "municipalityCode": "49",
        "municipalityName": "Komen",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.81922942618834,
          13.790004305936154
        ]
      },
      {
        "id": "borelioza-4",
        "municipalityCode": "4",
        "municipalityName": "Bohinj",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.301987456175965,
          13.909142741851813
        ]
      },
      {
        "id": "borelioza-25",
        "municipalityCode": "25",
        "municipalityName": "Dravograd",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59133509589289,
          15.03824935797488
        ]
      },
      {
        "id": "borelioza-144",
        "municipalityCode": "144",
        "municipalityName": "Zre\u010de",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40664759335575,
          15.367466884038109
        ]
      },
      {
        "id": "borelioza-58",
        "municipalityCode": "58",
        "municipalityName": "Lenart",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55423901495294,
          15.811459649119495
        ]
      },
      {
        "id": "borelioza-100",
        "municipalityCode": "100",
        "municipalityName": "Radenci",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.62037859600561,
          16.04439357897214
        ]
      },
      {
        "id": "borelioza-130",
        "municipalityCode": "130",
        "municipalityName": "Trebnje",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.90849357545599,
          14.992782272237456
        ]
      },
      {
        "id": "borelioza-22",
        "municipalityCode": "22",
        "municipalityName": "Dol pri Ljubljani",
        "score": 71,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.09662447795715,
          14.669814762385363
        ]
      },
      {
        "id": "borelioza-53",
        "municipalityCode": "53",
        "municipalityName": "Kranjska Gora",
        "score": 71,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.45009196707542,
          13.84325717125277
        ]
      },
      {
        "id": "borelioza-134",
        "municipalityCode": "134",
        "municipalityName": "Velike La\u0161\u010de",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.85018769810273,
          14.567558685205018
        ]
      },
      {
        "id": "borelioza-118",
        "municipalityCode": "118",
        "municipalityName": "\u0160entilj",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.66969826173817,
          15.768321280901421
        ]
      },
      {
        "id": "borelioza-98",
        "municipalityCode": "98",
        "municipalityName": "Ra\u010de-Fram",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.44747573498585,
          15.653747732535372
        ]
      },
      {
        "id": "borelioza-126",
        "municipalityCode": "126",
        "municipalityName": "\u0160o\u0161tanj",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.402306510165005,
          15.013088894049641
        ]
      },
      {
        "id": "borelioza-208",
        "municipalityCode": "208",
        "municipalityName": "Log-Dragomer",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.013105345724824,
          14.374037563342622
        ]
      },
      {
        "id": "borelioza-203",
        "municipalityCode": "203",
        "municipalityName": "Stra\u017ea",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.77436787888927,
          15.083138740159075
        ]
      },
      {
        "id": "borelioza-195",
        "municipalityCode": "195",
        "municipalityName": "Apa\u010de",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.69109006341557,
          15.882811316696241
        ]
      },
      {
        "id": "borelioza-104",
        "municipalityCode": "104",
        "municipalityName": "Ribnica",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.72862795229995,
          14.739858938290292
        ]
      },
      {
        "id": "borelioza-97",
        "municipalityCode": "97",
        "municipalityName": "Puconci",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.75514811433649,
          16.121744836334084
        ]
      },
      {
        "id": "borelioza-175",
        "municipalityCode": "175",
        "municipalityName": "Prevalje",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55492923331565,
          14.891455291589576
        ]
      },
      {
        "id": "borelioza-34",
        "municipalityCode": "34",
        "municipalityName": "Hrastnik",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.135056358286974,
          15.117771444387403
        ]
      },
      {
        "id": "borelioza-26",
        "municipalityCode": "26",
        "municipalityName": "Duplek",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.509356548203,
          15.76263380258807
        ]
      },
      {
        "id": "borelioza-213",
        "municipalityCode": "213",
        "municipalityName": "Ankaran",
        "score": 66,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.57669354798641,
          13.746392988670063
        ]
      },
      {
        "id": "borelioza-48",
        "municipalityCode": "48",
        "municipalityName": "Ko\u010devje",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.63074533902795,
          14.868231949702878
        ]
      },
      {
        "id": "borelioza-132",
        "municipalityCode": "132",
        "municipalityName": "Turni\u0161\u010de",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61501974206358,
          16.31982441265675
        ]
      },
      {
        "id": "borelioza-139",
        "municipalityCode": "139",
        "municipalityName": "Vojnik",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.314220054405595,
          15.306250583089616
        ]
      },
      {
        "id": "borelioza-162",
        "municipalityCode": "162",
        "municipalityName": "Horjul",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.019743649157014,
          14.29188782711017
        ]
      },
      {
        "id": "borelioza-55",
        "municipalityCode": "55",
        "municipalityName": "Kungota",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.641384246364524,
          15.596862785540193
        ]
      },
      {
        "id": "borelioza-79",
        "municipalityCode": "79",
        "municipalityName": "Mozirje",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35137174712952,
          14.960271783295871
        ]
      },
      {
        "id": "borelioza-135",
        "municipalityCode": "135",
        "municipalityName": "Videm",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34308610948735,
          15.932125268862329
        ]
      },
      {
        "id": "borelioza-72",
        "municipalityCode": "72",
        "municipalityName": "Menge\u0161",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.16250686369235,
          14.563769150841068
        ]
      },
      {
        "id": "borelioza-89",
        "municipalityCode": "89",
        "municipalityName": "Pesnica",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.6179514074537,
          15.706058386796581
        ]
      },
      {
        "id": "borelioza-68",
        "municipalityCode": "68",
        "municipalityName": "Lukovica",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.175035412974665,
          14.761643241350594
        ]
      },
      {
        "id": "borelioza-173",
        "municipalityCode": "173",
        "municipalityName": "Polzela",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.30285781054242,
          15.08342525086212
        ]
      },
      {
        "id": "borelioza-157",
        "municipalityCode": "157",
        "municipalityName": "Dolenjske Toplice",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.71498204178614,
          15.04208773727281
        ]
      },
      {
        "id": "borelioza-81",
        "municipalityCode": "81",
        "municipalityName": "Muta",
        "score": 62,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.62559353011548,
          15.135985903586487
        ]
      },
      {
        "id": "borelioza-10",
        "municipalityCode": "10",
        "municipalityName": "Ti\u0161ina",
        "score": 61,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65803414605874,
          16.072177305866354
        ]
      },
      {
        "id": "borelioza-65",
        "municipalityCode": "65",
        "municipalityName": "Lo\u0161ka dolina",
        "score": 61,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.66422277149297,
          14.49990413120156
        ]
      },
      {
        "id": "borelioza-15",
        "municipalityCode": "15",
        "municipalityName": "\u010cren\u0161ovci",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56158593403665,
          16.290623071179404
        ]
      },
      {
        "id": "borelioza-186",
        "municipalityCode": "186",
        "municipalityName": "Trzin",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.127701230377085,
          14.544448718129129
        ]
      },
      {
        "id": "borelioza-124",
        "municipalityCode": "124",
        "municipalityName": "\u0160marje pri Jel\u0161ah",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.216960338754866,
          15.517641398331211
        ]
      },
      {
        "id": "borelioza-209",
        "municipalityCode": "209",
        "municipalityName": "Re\u010dica ob Savinji",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.33223713815857,
          14.905911908991984
        ]
      },
      {
        "id": "borelioza-147",
        "municipalityCode": "147",
        "municipalityName": "\u017diri",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.04421436487128,
          14.123721927113818
        ]
      },
      {
        "id": "borelioza-95",
        "municipalityCode": "95",
        "municipalityName": "Preddvor",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 15,
        "trendLabel": "+15 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.324122598611424,
          14.46786238948985
        ]
      },
      {
        "id": "borelioza-108",
        "municipalityCode": "108",
        "municipalityName": "Ru\u0161e",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.519417033285194,
          15.4921020457614
        ]
      },
      {
        "id": "borelioza-194",
        "municipalityCode": "194",
        "municipalityName": "\u0160martno pri Litiji",
        "score": 57,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.017009510792946,
          14.833701734244864
        ]
      },
      {
        "id": "borelioza-206",
        "municipalityCode": "206",
        "municipalityName": "\u0160marje\u0161ke Toplice",
        "score": 57,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.88732010142421,
          15.242354970092155
        ]
      },
      {
        "id": "borelioza-62",
        "municipalityCode": "62",
        "municipalityName": "Ljubno",
        "score": 57,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.366782417214154,
          14.839647523145215
        ]
      },
      {
        "id": "borelioza-176",
        "municipalityCode": "176",
        "municipalityName": "Razkri\u017eje",
        "score": 57,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.518664518553564,
          16.27636328832139
        ]
      },
      {
        "id": "borelioza-20",
        "municipalityCode": "20",
        "municipalityName": "Dobrepolje",
        "score": 56,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.80997115861846,
          14.742435456323129
        ]
      },
      {
        "id": "borelioza-170",
        "municipalityCode": "170",
        "municipalityName": "Mirna Pe\u010d",
        "score": 56,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.854087813451216,
          15.081100461762297
        ]
      },
      {
        "id": "borelioza-148",
        "municipalityCode": "148",
        "municipalityName": "Benedikt",
        "score": 54,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61404004922419,
          15.882097044546224
        ]
      },
      {
        "id": "borelioza-74",
        "municipalityCode": "74",
        "municipalityName": "Me\u017eica",
        "score": 53,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52042865451979,
          14.850018903859208
        ]
      },
      {
        "id": "borelioza-178",
        "municipalityCode": "178",
        "municipalityName": "Selnica ob Dravi",
        "score": 53,
        "level": "Srednje",
        "trendDeltaScore": 16,
        "trendLabel": "+16 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59422111463753,
          15.480872605620965
        ]
      },
      {
        "id": "borelioza-77",
        "municipalityCode": "77",
        "municipalityName": "Morav\u010de",
        "score": 53,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.131781083057874,
          14.758226933043396
        ]
      },
      {
        "id": "borelioza-164",
        "municipalityCode": "164",
        "municipalityName": "Komenda",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": 12,
        "trendLabel": "+12 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.20727962595694,
          14.537713482312848
        ]
      },
      {
        "id": "borelioza-212",
        "municipalityCode": "212",
        "municipalityName": "Mirna",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94624070491869,
          15.057357064230793
        ]
      },
      {
        "id": "borelioza-174",
        "municipalityCode": "174",
        "municipalityName": "Prebold",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.22125645553881,
          15.086674020138176
        ]
      },
      {
        "id": "borelioza-69",
        "municipalityCode": "69",
        "municipalityName": "Maj\u0161perk",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.31567282469143,
          15.747678399772571
        ]
      },
      {
        "id": "borelioza-101",
        "municipalityCode": "101",
        "municipalityName": "Radlje ob Dravi",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59039965121862,
          15.250063017382363
        ]
      },
      {
        "id": "borelioza-199",
        "municipalityCode": "199",
        "municipalityName": "Mokronog-Trebelno",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.92332520079853,
          15.167607176319521
        ]
      },
      {
        "id": "borelioza-107",
        "municipalityCode": "107",
        "municipalityName": "Rogatec",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.237546603387386,
          15.737454290109904
        ]
      },
      {
        "id": "borelioza-202",
        "municipalityCode": "202",
        "municipalityName": "Sredi\u0161\u010de ob Dravi",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 14,
        "trendLabel": "+14 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40893204220943,
          16.2560429590338
        ]
      },
      {
        "id": "borelioza-35",
        "municipalityCode": "35",
        "municipalityName": "Hrpelje-Kozina",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.56287307279571,
          14.012321666704377
        ]
      },
      {
        "id": "borelioza-83",
        "municipalityCode": "83",
        "municipalityName": "Nazarje",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.28623184844571,
          14.920673449654924
        ]
      },
      {
        "id": "borelioza-181",
        "municipalityCode": "181",
        "municipalityName": "Sveta Ana",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65413758124333,
          15.841979457388666
        ]
      },
      {
        "id": "borelioza-19",
        "municipalityCode": "19",
        "municipalityName": "Diva\u010da",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.686769254625176,
          14.012516263347699
        ]
      },
      {
        "id": "borelioza-115",
        "municipalityCode": "115",
        "municipalityName": "Star\u0161e",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.46523002566637,
          15.759499440042012
        ]
      },
      {
        "id": "borelioza-45",
        "municipalityCode": "45",
        "municipalityName": "Kidri\u010devo",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.397804846698875,
          15.753727471957369
        ]
      },
      {
        "id": "borelioza-105",
        "municipalityCode": "105",
        "municipalityName": "Roga\u0161ovci",
        "score": 47,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.797565278402416,
          16.024175797259314
        ]
      },
      {
        "id": "borelioza-193",
        "municipalityCode": "193",
        "municipalityName": "\u017du\u017eemberk",
        "score": 47,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.80718245218927,
          14.96851775759558
        ]
      },
      {
        "id": "borelioza-205",
        "municipalityCode": "205",
        "municipalityName": "Sveti Toma\u017e",
        "score": 46,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.47667884462751,
          16.072191147712203
        ]
      },
      {
        "id": "borelioza-6",
        "municipalityCode": "6",
        "municipalityName": "Bovec",
        "score": 46,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35645232075714,
          13.61522747174282
        ]
      },
      {
        "id": "borelioza-141",
        "municipalityCode": "141",
        "municipalityName": "Vuzenica",
        "score": 46,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.564869359461696,
          15.147089282959382
        ]
      },
      {
        "id": "borelioza-67",
        "municipalityCode": "67",
        "municipalityName": "Lu\u010de",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35680027328705,
          14.713931657979746
        ]
      },
      {
        "id": "borelioza-204",
        "municipalityCode": "204",
        "municipalityName": "Sveta Trojica v Slovenskih goricah",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56688706224247,
          15.882151799957505
        ]
      },
      {
        "id": "borelioza-207",
        "municipalityCode": "207",
        "municipalityName": "Gorje",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.39460739717714,
          13.991652514503876
        ]
      },
      {
        "id": "borelioza-158",
        "municipalityCode": "158",
        "municipalityName": "Grad",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.79466554948839,
          16.095160030316443
        ]
      },
      {
        "id": "borelioza-168",
        "municipalityCode": "168",
        "municipalityName": "Markovci",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.39119478302419,
          15.941073439101038
        ]
      },
      {
        "id": "borelioza-93",
        "municipalityCode": "93",
        "municipalityName": "Podvelka",
        "score": 44,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.5834090776923,
          15.322536682172196
        ]
      },
      {
        "id": "borelioza-121",
        "municipalityCode": "121",
        "municipalityName": "\u0160kocjan",
        "score": 44,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91391777603153,
          15.296370829550806
        ]
      },
      {
        "id": "borelioza-18",
        "municipalityCode": "18",
        "municipalityName": "Destrnik",
        "score": 43,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.47883364411645,
          15.886380524887887
        ]
      },
      {
        "id": "borelioza-211",
        "municipalityCode": "211",
        "municipalityName": "\u0160entrupert",
        "score": 43,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.98466466359292,
          15.081503951661038
        ]
      },
      {
        "id": "borelioza-189",
        "municipalityCode": "189",
        "municipalityName": "Vransko",
        "score": 43,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23384118770266,
          14.937525704838905
        ]
      },
      {
        "id": "borelioza-197",
        "municipalityCode": "197",
        "municipalityName": "Kostanjevica na Krki",
        "score": 43,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.841500599300915,
          15.419015231683833
        ]
      },
      {
        "id": "borelioza-99",
        "municipalityCode": "99",
        "municipalityName": "Rade\u010de",
        "score": 43,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.05947478962034,
          15.135812045899474
        ]
      },
      {
        "id": "borelioza-200",
        "municipalityCode": "200",
        "municipalityName": "Polj\u010dane",
        "score": 42,
        "level": "Srednje",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.30435958138044,
          15.600314348299081
        ]
      },
      {
        "id": "borelioza-187",
        "municipalityCode": "187",
        "municipalityName": "Velika Polana",
        "score": 42,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.57822762617022,
          16.36314075891279
        ]
      },
      {
        "id": "borelioza-196",
        "municipalityCode": "196",
        "municipalityName": "Cirkulane",
        "score": 42,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34497051579654,
          15.996158814158486
        ]
      },
      {
        "id": "borelioza-210",
        "municipalityCode": "210",
        "municipalityName": "Sveti Jurij v Slovenskih goricah",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61298948846985,
          15.797230370143808
        ]
      },
      {
        "id": "borelioza-179",
        "municipalityCode": "179",
        "municipalityName": "Sodra\u017eica",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.75493617784626,
          14.621932090378817
        ]
      },
      {
        "id": "borelioza-153",
        "municipalityCode": "153",
        "municipalityName": "Cerkvenjak",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55976392834934,
          15.93558833891059
        ]
      },
      {
        "id": "borelioza-28",
        "municipalityCode": "28",
        "municipalityName": "Gori\u0161nica",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.404665976735856,
          16.0114230646881
        ]
      },
      {
        "id": "borelioza-24",
        "municipalityCode": "24",
        "municipalityName": "Dornava",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.45422934918125,
          16.005643690430443
        ]
      },
      {
        "id": "borelioza-127",
        "municipalityCode": "127",
        "municipalityName": "\u0160tore",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.198208860154836,
          15.327644837050277
        ]
      },
      {
        "id": "borelioza-76",
        "municipalityCode": "76",
        "municipalityName": "Mislinja",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.44706000299166,
          15.221357122296974
        ]
      },
      {
        "id": "borelioza-184",
        "municipalityCode": "184",
        "municipalityName": "Tabor",
        "score": 40,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.22515498686076,
          15.008445448558128
        ]
      },
      {
        "id": "borelioza-30",
        "municipalityCode": "30",
        "municipalityName": "Gornji Grad",
        "score": 40,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.29609977156301,
          14.795046381065418
        ]
      },
      {
        "id": "borelioza-150",
        "municipalityCode": "150",
        "municipalityName": "Bloke",
        "score": 40,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.787012357357185,
          14.498597677491748
        ]
      },
      {
        "id": "borelioza-42",
        "municipalityCode": "42",
        "municipalityName": "Jur\u0161inci",
        "score": 39,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.48293327291799,
          15.96934235489326
        ]
      },
      {
        "id": "borelioza-137",
        "municipalityCode": "137",
        "municipalityName": "Vitanje",
        "score": 39,
        "level": "Srednje",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40544082853494,
          15.28538211995037
        ]
      },
      {
        "id": "borelioza-56",
        "municipalityCode": "56",
        "municipalityName": "Kuzma",
        "score": 38,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.83994788396974,
          16.092505197420564
        ]
      },
      {
        "id": "borelioza-171",
        "municipalityCode": "171",
        "municipalityName": "Oplotnica",
        "score": 37,
        "level": "Srednje",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.389001813979775,
          15.450919690535954
        ]
      },
      {
        "id": "borelioza-125",
        "municipalityCode": "125",
        "municipalityName": "\u0160martno ob Paki",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.33982074119845,
          15.02966843251847
        ]
      },
      {
        "id": "borelioza-31",
        "municipalityCode": "31",
        "municipalityName": "Gornji Petrovci",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.799282370682974,
          16.222988126949275
        ]
      },
      {
        "id": "borelioza-172",
        "municipalityCode": "172",
        "municipalityName": "Podlehnik",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.315276293961766,
          15.861600612684818
        ]
      },
      {
        "id": "borelioza-16",
        "municipalityCode": "16",
        "municipalityName": "\u010crna na Koro\u0161kem",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 13,
        "trendLabel": "+13 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.46468970620242,
          14.82861013748666
        ]
      },
      {
        "id": "borelioza-33",
        "municipalityCode": "33",
        "municipalityName": "\u0160alovci",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 12,
        "trendLabel": "+12 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.823782651809964,
          16.282020720503965
        ]
      },
      {
        "id": "borelioza-167",
        "municipalityCode": "167",
        "municipalityName": "Lovrenc na Pohorju",
        "score": 35,
        "level": "Srednje",
        "trendDeltaScore": 14,
        "trendLabel": "+14 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52428081527462,
          15.385407317246422
        ]
      },
      {
        "id": "borelioza-159",
        "municipalityCode": "159",
        "municipalityName": "Hajdina",
        "score": 34,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.4199372070635,
          15.823727524400496
        ]
      },
      {
        "id": "borelioza-188",
        "municipalityCode": "188",
        "municipalityName": "Ver\u017eej",
        "score": 34,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.58331042633665,
          16.17395569480889
        ]
      },
      {
        "id": "borelioza-152",
        "municipalityCode": "152",
        "municipalityName": "Cankova",
        "score": 32,
        "level": "Nizko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.732847713896774,
          16.02504267492902
        ]
      },
      {
        "id": "borelioza-177",
        "municipalityCode": "177",
        "municipalityName": "Ribnica na Pohorju",
        "score": 31,
        "level": "Nizko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.527914236925454,
          15.259003227781578
        ]
      },
      {
        "id": "borelioza-143",
        "municipalityCode": "143",
        "municipalityName": "Zavr\u010d",
        "score": 30,
        "level": "Nizko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.363724404629636,
          16.04440479134854
        ]
      },
      {
        "id": "borelioza-92",
        "municipalityCode": "92",
        "municipalityName": "Pod\u010detrtek",
        "score": 28,
        "level": "Nizko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.13618049475401,
          15.568446650547862
        ]
      },
      {
        "id": "borelioza-198",
        "municipalityCode": "198",
        "municipalityName": "Makole",
        "score": 27,
        "level": "Nizko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.312669429468,
          15.678908945065823
        ]
      },
      {
        "id": "borelioza-185",
        "municipalityCode": "185",
        "municipalityName": "Trnovska vas",
        "score": 26,
        "level": "Nizko",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52611418774025,
          15.890388308225477
        ]
      },
      {
        "id": "borelioza-156",
        "municipalityCode": "156",
        "municipalityName": "Dobrovnik",
        "score": 25,
        "level": "Nizko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65103869686774,
          16.347760516536397
        ]
      },
      {
        "id": "borelioza-191",
        "municipalityCode": "191",
        "municipalityName": "\u017detale",
        "score": 25,
        "level": "Nizko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.288241806796265,
          15.795755968346992
        ]
      },
      {
        "id": "borelioza-154",
        "municipalityCode": "154",
        "municipalityName": "Dobje",
        "score": 25,
        "level": "Nizko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.134840909929885,
          15.399986336385783
        ]
      },
      {
        "id": "borelioza-180",
        "municipalityCode": "180",
        "municipalityName": "Sol\u010dava",
        "score": 23,
        "level": "Nizko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40287233027988,
          14.659691125294174
        ]
      },
      {
        "id": "borelioza-51",
        "municipalityCode": "51",
        "municipalityName": "Kozje",
        "score": 20,
        "level": "Nizko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.064888860017504,
          15.556359799680841
        ]
      },
      {
        "id": "borelioza-149",
        "municipalityCode": "149",
        "municipalityName": "Bistrica ob Sotli",
        "score": 18,
        "level": "Nizko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.05922075203121,
          15.653185617048514
        ]
      },
      {
        "id": "borelioza-163",
        "municipalityCode": "163",
        "municipalityName": "Jezersko",
        "score": 15,
        "level": "Nizko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.38632748989521,
          14.487418205717972
        ]
      },
      {
        "id": "borelioza-155",
        "municipalityCode": "155",
        "municipalityName": "Dobrna",
        "score": 15,
        "level": "Nizko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35280085596145,
          15.22787394880007
        ]
      },
      {
        "id": "borelioza-165",
        "municipalityCode": "165",
        "municipalityName": "Kostel",
        "score": 14,
        "level": "Nizko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.49977703287,
          14.855647138605367
        ]
      },
      {
        "id": "borelioza-182",
        "municipalityCode": "182",
        "municipalityName": "Sveti Andra\u017e v Slov. goricah",
        "score": 13,
        "level": "Nizko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.518201223045246,
          15.951098855339616
        ]
      },
      {
        "id": "borelioza-86",
        "municipalityCode": "86",
        "municipalityName": "Odranci",
        "score": 11,
        "level": "Nizko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.58524894185486,
          16.271500112028
        ]
      },
      {
        "id": "borelioza-161",
        "municipalityCode": "161",
        "municipalityName": "Hodo\u0161",
        "score": 9,
        "level": "Nizko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.8317205363355,
          16.329800593473202
        ]
      },
      {
        "id": "borelioza-47",
        "municipalityCode": "47",
        "municipalityName": "Kobilje",
        "score": 9,
        "level": "Nizko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.68129118126244,
          16.3875549735546
        ]
      },
      {
        "id": "borelioza-66",
        "municipalityCode": "66",
        "municipalityName": "Lo\u0161ki Potok",
        "score": 8,
        "level": "Nizko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.66252716495228,
          14.670025526010441
        ]
      },
      {
        "id": "borelioza-88",
        "municipalityCode": "88",
        "municipalityName": "Osilnica",
        "score": 1,
        "level": "Nizko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.55075114447103,
          14.720215036019834
        ]
      }
    ],
    "featuredLocations": [
      {
        "municipalityName": "Kranj",
        "municipalityCode": "52",
        "level": "Visoko",
        "score": 99,
        "id": "borelioza-52"
      },
      {
        "municipalityName": "Ljubljana",
        "municipalityCode": "61",
        "level": "Visoko",
        "score": 99,
        "id": "borelioza-61"
      },
      {
        "municipalityName": "Ajdov\u0161\u010dina",
        "municipalityCode": "1",
        "level": "Visoko",
        "score": 99,
        "id": "borelioza-1"
      },
      {
        "municipalityName": "Maribor",
        "municipalityCode": "70",
        "level": "Visoko",
        "score": 99,
        "id": "borelioza-70"
      },
      {
        "municipalityName": "Nova Gorica",
        "municipalityCode": "84",
        "level": "Visoko",
        "score": 99,
        "id": "borelioza-84"
      },
      {
        "municipalityName": "Radovljica",
        "municipalityCode": "102",
        "level": "Visoko",
        "score": 98,
        "id": "borelioza-102"
      },
      {
        "municipalityName": "Jesenice",
        "municipalityCode": "41",
        "level": "Visoko",
        "score": 98,
        "id": "borelioza-41"
      },
      {
        "municipalityName": "Koper",
        "municipalityCode": "50",
        "level": "Visoko",
        "score": 97,
        "id": "borelioza-50"
      }
    ]
  },
  "kme": {
    "key": "kme",
    "diseaseLabel": "KME",
    "modelId": "catboost_tick_borne_kme_env_v2",
    "legacyResearchModelId": "catboost_tick_borne_kme_env_per100k_v1",
    "asOfDate": "2026-04-22",
    "generatedAt": "2026-04-22T17:20:30",
    "referenceWeekStart": "2026-04-13",
    "referenceWeekEnd": "2026-04-19",
    "snapshotLabel": "zadnji zaklju\u010deni tedenski hackathon snapshot",
    "weatherSource": "Open-Meteo best-match hourly weather",
    "methodologyNote": "Live hackathon demo uporablja Open-Meteo hourly weather za zadnjih 6 tednov, tedensko agregacijo po istem feature kontraktu kot env_v2 in reprezentativno to\u010dko znotraj GURS poligona posamezne ob\u010dine. Score temelji na surovi napovedi env_v2 klasifikacijskega modela in je namenjen primerjavi ob\u010din znotraj iste bolezni. KME model je pri u\u010denju dodatno ute\u017een po velikosti populacije ob\u010dine, da zemljevid ni sistemati\u010dno pristranski do zelo majhnih ob\u010din.",
    "purpose": "Live hackathon relativni ob\u010dinski okoljski indeks za KME.",
    "disclaimer": "To ni diagnoza ali individualna verjetnost bolezni. Gre za relativni ob\u010dinski risk indeks, ki je uporaben predvsem za primerjavo lokacij znotraj iste bolezni.",
    "scoreExplanation": "Score je relativni ob\u010dinski indeks 0-100, izra\u010dunan kot empiri\u010dni percentil surove napovedi modela znotraj holdout distribucije istega env_v2 modela.",
    "topDrivers": [
      "sezonski signal",
      "mesani gozd",
      "urbaniziranost",
      "sezonski signal",
      "kmetijska krajina"
    ],
    "thresholds": {
      "lowUpper": 0.04741043645333333,
      "mediumUpper": 0.19767068223333326
    },
    "locations": [
      {
        "id": "kme-70",
        "municipalityCode": "70",
        "municipalityName": "Maribor",
        "score": 100,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.566868391230585,
          15.631952095403161
        ]
      },
      {
        "id": "kme-61",
        "municipalityCode": "61",
        "municipalityName": "Ljubljana",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.06002832481608,
          14.591227050900212
        ]
      },
      {
        "id": "kme-64",
        "municipalityCode": "64",
        "municipalityName": "Logatec",
        "score": 99,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.9423203388053,
          14.179699694323777
        ]
      },
      {
        "id": "kme-43",
        "municipalityCode": "43",
        "municipalityName": "Kamnik",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.27507789786611,
          14.625372343893963
        ]
      },
      {
        "id": "kme-94",
        "municipalityCode": "94",
        "municipalityName": "Postojna",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.79035444806679,
          14.157811302015979
        ]
      },
      {
        "id": "kme-113",
        "municipalityCode": "113",
        "municipalityName": "Slovenska Bistrica",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.407381712420836,
          15.563642140833664
        ]
      },
      {
        "id": "kme-131",
        "municipalityCode": "131",
        "municipalityName": "Tr\u017ei\u010d",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.38054018463163,
          14.332766698876704
        ]
      },
      {
        "id": "kme-52",
        "municipalityCode": "52",
        "municipalityName": "Kranj",
        "score": 98,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25405493617421,
          14.258306205043977
        ]
      },
      {
        "id": "kme-27",
        "municipalityCode": "27",
        "municipalityName": "Gorenja vas-Poljane",
        "score": 97,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.10892470832346,
          14.127270278645835
        ]
      },
      {
        "id": "kme-122",
        "municipalityCode": "122",
        "municipalityName": "\u0160kofja Loka",
        "score": 97,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.16882510512077,
          14.306552332367522
        ]
      },
      {
        "id": "kme-102",
        "municipalityCode": "102",
        "municipalityName": "Radovljica",
        "score": 96,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.344957557875674,
          14.197636337189738
        ]
      },
      {
        "id": "kme-1",
        "municipalityCode": "1",
        "municipalityName": "Ajdov\u0161\u010dina",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91223397414079,
          13.876160443372136
        ]
      },
      {
        "id": "kme-71",
        "municipalityCode": "71",
        "municipalityName": "Medvode",
        "score": 95,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.134643179494105,
          14.401236528773666
        ]
      },
      {
        "id": "kme-13",
        "municipalityCode": "13",
        "municipalityName": "Cerknica",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.798316218528036,
          14.344880376684069
        ]
      },
      {
        "id": "kme-112",
        "municipalityCode": "112",
        "municipalityName": "Slovenj Gradec",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.49232870395046,
          15.090728012234134
        ]
      },
      {
        "id": "kme-146",
        "municipalityCode": "146",
        "municipalityName": "\u017delezniki",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.21826950579093,
          14.12031594808045
        ]
      },
      {
        "id": "kme-21",
        "municipalityCode": "21",
        "municipalityName": "Dobrova-Polhov Gradec",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.059704146138635,
          14.321669412771623
        ]
      },
      {
        "id": "kme-80",
        "municipalityCode": "80",
        "municipalityName": "Murska Sobota",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.64944285646449,
          16.180008501955584
        ]
      },
      {
        "id": "kme-41",
        "municipalityCode": "41",
        "municipalityName": "Jesenice",
        "score": 94,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.445948023027015,
          14.066153130492548
        ]
      },
      {
        "id": "kme-3",
        "municipalityCode": "3",
        "municipalityName": "Bled",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34851196309823,
          14.069126047452333
        ]
      },
      {
        "id": "kme-14",
        "municipalityCode": "14",
        "municipalityName": "Cerkno",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.12457099554262,
          13.968090156470707
        ]
      },
      {
        "id": "kme-25",
        "municipalityCode": "25",
        "municipalityName": "Dravograd",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59133509589289,
          15.03824935797488
        ]
      },
      {
        "id": "kme-38",
        "municipalityCode": "38",
        "municipalityName": "Ilirska Bistrica",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.577291675053395,
          14.297163875431005
        ]
      },
      {
        "id": "kme-65",
        "municipalityCode": "65",
        "municipalityName": "Lo\u0161ka dolina",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.66422277149297,
          14.49990413120156
        ]
      },
      {
        "id": "kme-140",
        "municipalityCode": "140",
        "municipalityName": "Vrhnika",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94762357863712,
          14.287738246748727
        ]
      },
      {
        "id": "kme-36",
        "municipalityCode": "36",
        "municipalityName": "Idrija",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.98377995176204,
          14.000525261117094
        ]
      },
      {
        "id": "kme-68",
        "municipalityCode": "68",
        "municipalityName": "Lukovica",
        "score": 93,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.175035412974665,
          14.761643241350594
        ]
      },
      {
        "id": "kme-104",
        "municipalityCode": "104",
        "municipalityName": "Ribnica",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.72862795229995,
          14.739858938290292
        ]
      },
      {
        "id": "kme-213",
        "municipalityCode": "213",
        "municipalityName": "Ankaran",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.57669354798641,
          13.746392988670063
        ]
      },
      {
        "id": "kme-103",
        "municipalityCode": "103",
        "municipalityName": "Ravne na Koro\u0161kem",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.548379514222276,
          14.975105293957746
        ]
      },
      {
        "id": "kme-179",
        "municipalityCode": "179",
        "municipalityName": "Sodra\u017eica",
        "score": 92,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.75493617784626,
          14.621932090378817
        ]
      },
      {
        "id": "kme-48",
        "municipalityCode": "48",
        "municipalityName": "Ko\u010devje",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.63074533902795,
          14.868231949702878
        ]
      },
      {
        "id": "kme-63",
        "municipalityCode": "63",
        "municipalityName": "Ljutomer",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52220953072839,
          16.131317625513894
        ]
      },
      {
        "id": "kme-37",
        "municipalityCode": "37",
        "municipalityName": "Ig",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.93329916174528,
          14.511092954849847
        ]
      },
      {
        "id": "kme-136",
        "municipalityCode": "136",
        "municipalityName": "Vipava",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.82132699262401,
          13.980192683772628
        ]
      },
      {
        "id": "kme-23",
        "municipalityCode": "23",
        "municipalityName": "Dom\u017eale",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.15074721202056,
          14.626624858204789
        ]
      },
      {
        "id": "kme-84",
        "municipalityCode": "84",
        "municipalityName": "Nova Gorica",
        "score": 91,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.97092502839293,
          13.721150401050998
        ]
      },
      {
        "id": "kme-5",
        "municipalityCode": "5",
        "municipalityName": "Borovnica",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91121899380177,
          14.383328935785617
        ]
      },
      {
        "id": "kme-126",
        "municipalityCode": "126",
        "municipalityName": "\u0160o\u0161tanj",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.402306510165005,
          15.013088894049641
        ]
      },
      {
        "id": "kme-8",
        "municipalityCode": "8",
        "municipalityName": "Brezovica",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94786493630048,
          14.418009047652001
        ]
      },
      {
        "id": "kme-134",
        "municipalityCode": "134",
        "municipalityName": "Velike La\u0161\u010de",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.85018769810273,
          14.567558685205018
        ]
      },
      {
        "id": "kme-12",
        "municipalityCode": "12",
        "municipalityName": "Cerklje na Gorenjskem",
        "score": 89,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25525345774459,
          14.503642347119424
        ]
      },
      {
        "id": "kme-91",
        "municipalityCode": "91",
        "municipalityName": "Pivka",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.68861836877859,
          14.228707926505304
        ]
      },
      {
        "id": "kme-60",
        "municipalityCode": "60",
        "municipalityName": "Litija",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 15,
        "trendLabel": "+15 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.049658676044096,
          14.991181473283978
        ]
      },
      {
        "id": "kme-169",
        "municipalityCode": "169",
        "municipalityName": "Miklav\u017e na Dravskem polju",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.488367615491015,
          15.701639787840676
        ]
      },
      {
        "id": "kme-144",
        "municipalityCode": "144",
        "municipalityName": "Zre\u010de",
        "score": 88,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40664759335575,
          15.367466884038109
        ]
      },
      {
        "id": "kme-129",
        "municipalityCode": "129",
        "municipalityName": "Trbovlje",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.13733695980865,
          15.044375862598683
        ]
      },
      {
        "id": "kme-11",
        "municipalityCode": "11",
        "municipalityName": "Celje",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.25474084428838,
          15.284333781255828
        ]
      },
      {
        "id": "kme-194",
        "municipalityCode": "194",
        "municipalityName": "\u0160martno pri Litiji",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.017009510792946,
          14.833701734244864
        ]
      },
      {
        "id": "kme-175",
        "municipalityCode": "175",
        "municipalityName": "Prevalje",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55492923331565,
          14.891455291589576
        ]
      },
      {
        "id": "kme-192",
        "municipalityCode": "192",
        "municipalityName": "\u017dirovnica",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.406361601715595,
          14.164011004434988
        ]
      },
      {
        "id": "kme-4",
        "municipalityCode": "4",
        "municipalityName": "Bohinj",
        "score": 87,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.301987456175965,
          13.909142741851813
        ]
      },
      {
        "id": "kme-32",
        "municipalityCode": "32",
        "municipalityName": "Grosuplje",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.944248714331906,
          14.664212172553189
        ]
      },
      {
        "id": "kme-40",
        "municipalityCode": "40",
        "municipalityName": "Izola",
        "score": 86,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.51045419293274,
          13.659267020509787
        ]
      },
      {
        "id": "kme-96",
        "municipalityCode": "96",
        "municipalityName": "Ptuj",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.441384397919784,
          15.886057811037922
        ]
      },
      {
        "id": "kme-100",
        "municipalityCode": "100",
        "municipalityName": "Radenci",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.62037859600561,
          16.04439357897214
        ]
      },
      {
        "id": "kme-162",
        "municipalityCode": "162",
        "municipalityName": "Horjul",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.019743649157014,
          14.29188782711017
        ]
      },
      {
        "id": "kme-76",
        "municipalityCode": "76",
        "municipalityName": "Mislinja",
        "score": 85,
        "level": "Visoko",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.44706000299166,
          15.221357122296974
        ]
      },
      {
        "id": "kme-147",
        "municipalityCode": "147",
        "municipalityName": "\u017diri",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.04421436487128,
          14.123721927113818
        ]
      },
      {
        "id": "kme-83",
        "municipalityCode": "83",
        "municipalityName": "Nazarje",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.28623184844571,
          14.920673449654924
        ]
      },
      {
        "id": "kme-22",
        "municipalityCode": "22",
        "municipalityName": "Dol pri Ljubljani",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.09662447795715,
          14.669814762385363
        ]
      },
      {
        "id": "kme-10",
        "municipalityCode": "10",
        "municipalityName": "Ti\u0161ina",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65803414605874,
          16.072177305866354
        ]
      },
      {
        "id": "kme-209",
        "municipalityCode": "209",
        "municipalityName": "Re\u010dica ob Savinji",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.33223713815857,
          14.905911908991984
        ]
      },
      {
        "id": "kme-20",
        "municipalityCode": "20",
        "municipalityName": "Dobrepolje",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.80997115861846,
          14.742435456323129
        ]
      },
      {
        "id": "kme-98",
        "municipalityCode": "98",
        "municipalityName": "Ra\u010de-Fram",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.44747573498585,
          15.653747732535372
        ]
      },
      {
        "id": "kme-184",
        "municipalityCode": "184",
        "municipalityName": "Tabor",
        "score": 84,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.22515498686076,
          15.008445448558128
        ]
      },
      {
        "id": "kme-123",
        "municipalityCode": "123",
        "municipalityName": "\u0160kofljica",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.956574131994586,
          14.578745574374771
        ]
      },
      {
        "id": "kme-128",
        "municipalityCode": "128",
        "municipalityName": "Tolmin",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.14382787419562,
          13.789384629736421
        ]
      },
      {
        "id": "kme-74",
        "municipalityCode": "74",
        "municipalityName": "Me\u017eica",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52042865451979,
          14.850018903859208
        ]
      },
      {
        "id": "kme-195",
        "municipalityCode": "195",
        "municipalityName": "Apa\u010de",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": -6,
        "trendLabel": "-6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.69109006341557,
          15.882811316696241
        ]
      },
      {
        "id": "kme-186",
        "municipalityCode": "186",
        "municipalityName": "Trzin",
        "score": 83,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.127701230377085,
          14.544448718129129
        ]
      },
      {
        "id": "kme-166",
        "municipalityCode": "166",
        "municipalityName": "Kri\u017eevci",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56678423380212,
          16.117607164937617
        ]
      },
      {
        "id": "kme-137",
        "municipalityCode": "137",
        "municipalityName": "Vitanje",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40544082853494,
          15.28538211995037
        ]
      },
      {
        "id": "kme-87",
        "municipalityCode": "87",
        "municipalityName": "Ormo\u017e",
        "score": 82,
        "level": "Visoko",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.43923237384557,
          16.122467447626843
        ]
      },
      {
        "id": "kme-2",
        "municipalityCode": "2",
        "municipalityName": "Beltinci",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.60790187625657,
          16.23183338966472
        ]
      },
      {
        "id": "kme-108",
        "municipalityCode": "108",
        "municipalityName": "Ru\u0161e",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.519417033285194,
          15.4921020457614
        ]
      },
      {
        "id": "kme-189",
        "municipalityCode": "189",
        "municipalityName": "Vransko",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23384118770266,
          14.937525704838905
        ]
      },
      {
        "id": "kme-120",
        "municipalityCode": "120",
        "municipalityName": "\u0160entjur",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.18851791002033,
          15.406013006743873
        ]
      },
      {
        "id": "kme-133",
        "municipalityCode": "133",
        "municipalityName": "Velenje",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.37450714272869,
          15.135691606302903
        ]
      },
      {
        "id": "kme-110",
        "municipalityCode": "110",
        "municipalityName": "Sevnica",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.008602808339205,
          15.26233339155699
        ]
      },
      {
        "id": "kme-150",
        "municipalityCode": "150",
        "municipalityName": "Bloke",
        "score": 81,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.787012357357185,
          14.498597677491748
        ]
      },
      {
        "id": "kme-109",
        "municipalityCode": "109",
        "municipalityName": "Semi\u010d",
        "score": 80,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.65247113774323,
          15.1531953913182
        ]
      },
      {
        "id": "kme-77",
        "municipalityCode": "77",
        "municipalityName": "Morav\u010de",
        "score": 80,
        "level": "Visoko",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.131781083057874,
          14.758226933043396
        ]
      },
      {
        "id": "kme-30",
        "municipalityCode": "30",
        "municipalityName": "Gornji Grad",
        "score": 80,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.29609977156301,
          14.795046381065418
        ]
      },
      {
        "id": "kme-142",
        "municipalityCode": "142",
        "municipalityName": "Zagorje ob Savi",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.128801067769395,
          14.960344642392293
        ]
      },
      {
        "id": "kme-39",
        "municipalityCode": "39",
        "municipalityName": "Ivan\u010dna Gorica",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.90422389415425,
          14.812022485584954
        ]
      },
      {
        "id": "kme-114",
        "municipalityCode": "114",
        "municipalityName": "Slovenske Konjice",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.324744778194386,
          15.449770717290768
        ]
      },
      {
        "id": "kme-81",
        "municipalityCode": "81",
        "municipalityName": "Muta",
        "score": 79,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.62559353011548,
          15.135985903586487
        ]
      },
      {
        "id": "kme-28",
        "municipalityCode": "28",
        "municipalityName": "Gori\u0161nica",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.404665976735856,
          16.0114230646881
        ]
      },
      {
        "id": "kme-174",
        "municipalityCode": "174",
        "municipalityName": "Prebold",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.22125645553881,
          15.086674020138176
        ]
      },
      {
        "id": "kme-58",
        "municipalityCode": "58",
        "municipalityName": "Lenart",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55423901495294,
          15.811459649119495
        ]
      },
      {
        "id": "kme-57",
        "municipalityCode": "57",
        "municipalityName": "La\u0161ko",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.12804517838802,
          15.269594900971004
        ]
      },
      {
        "id": "kme-171",
        "municipalityCode": "171",
        "municipalityName": "Oplotnica",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.389001813979775,
          15.450919690535954
        ]
      },
      {
        "id": "kme-95",
        "municipalityCode": "95",
        "municipalityName": "Preddvor",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.324122598611424,
          14.46786238948985
        ]
      },
      {
        "id": "kme-66",
        "municipalityCode": "66",
        "municipalityName": "Lo\u0161ki Potok",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.66252716495228,
          14.670025526010441
        ]
      },
      {
        "id": "kme-72",
        "municipalityCode": "72",
        "municipalityName": "Menge\u0161",
        "score": 78,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.16250686369235,
          14.563769150841068
        ]
      },
      {
        "id": "kme-190",
        "municipalityCode": "190",
        "municipalityName": "\u017dalec",
        "score": 77,
        "level": "Visoko",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.26111485109752,
          15.156994659796197
        ]
      },
      {
        "id": "kme-168",
        "municipalityCode": "168",
        "municipalityName": "Markovci",
        "score": 77,
        "level": "Visoko",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.39119478302419,
          15.941073439101038
        ]
      },
      {
        "id": "kme-115",
        "municipalityCode": "115",
        "municipalityName": "Star\u0161e",
        "score": 77,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.46523002566637,
          15.759499440042012
        ]
      },
      {
        "id": "kme-99",
        "municipalityCode": "99",
        "municipalityName": "Rade\u010de",
        "score": 77,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.05947478962034,
          15.135812045899474
        ]
      },
      {
        "id": "kme-163",
        "municipalityCode": "163",
        "municipalityName": "Jezersko",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 14,
        "trendLabel": "+14 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.38632748989521,
          14.487418205717972
        ]
      },
      {
        "id": "kme-79",
        "municipalityCode": "79",
        "municipalityName": "Mozirje",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35137174712952,
          14.960271783295871
        ]
      },
      {
        "id": "kme-67",
        "municipalityCode": "67",
        "municipalityName": "Lu\u010de",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 12,
        "trendLabel": "+12 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35680027328705,
          14.713931657979746
        ]
      },
      {
        "id": "kme-29",
        "municipalityCode": "29",
        "municipalityName": "Gornja Radgona",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.63619990843724,
          15.9666600915219
        ]
      },
      {
        "id": "kme-116",
        "municipalityCode": "116",
        "municipalityName": "Sveti Jurij ob \u0160\u010davnici",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56155714657142,
          16.018594362570987
        ]
      },
      {
        "id": "kme-19",
        "municipalityCode": "19",
        "municipalityName": "Diva\u010da",
        "score": 76,
        "level": "Visoko",
        "trendDeltaScore": 12,
        "trendLabel": "+12 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.686769254625176,
          14.012516263347699
        ]
      },
      {
        "id": "kme-164",
        "municipalityCode": "164",
        "municipalityName": "Komenda",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.20727962595694,
          14.537713482312848
        ]
      },
      {
        "id": "kme-160",
        "municipalityCode": "160",
        "municipalityName": "Ho\u010de-Slivnica",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.490054688189225,
          15.610380143423317
        ]
      },
      {
        "id": "kme-117",
        "municipalityCode": "117",
        "municipalityName": "\u0160en\u010dur",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23942277871478,
          14.419716721996306
        ]
      },
      {
        "id": "kme-151",
        "municipalityCode": "151",
        "municipalityName": "Braslov\u010de",
        "score": 75,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.28041457558507,
          15.017620841664286
        ]
      },
      {
        "id": "kme-211",
        "municipalityCode": "211",
        "municipalityName": "\u0160entrupert",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.98466466359292,
          15.081503951661038
        ]
      },
      {
        "id": "kme-178",
        "municipalityCode": "178",
        "municipalityName": "Selnica ob Dravi",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": 8,
        "trendLabel": "+8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59422111463753,
          15.480872605620965
        ]
      },
      {
        "id": "kme-183",
        "municipalityCode": "183",
        "municipalityName": "\u0160empeter-Vrtojba",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91777884379731,
          13.651647350069668
        ]
      },
      {
        "id": "kme-15",
        "municipalityCode": "15",
        "municipalityName": "\u010cren\u0161ovci",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56158593403665,
          16.290623071179404
        ]
      },
      {
        "id": "kme-88",
        "municipalityCode": "88",
        "municipalityName": "Osilnica",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.55075114447103,
          14.720215036019834
        ]
      },
      {
        "id": "kme-17",
        "municipalityCode": "17",
        "municipalityName": "\u010crnomelj",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": -10,
        "trendLabel": "-10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.52531358153176,
          15.21046961172452
        ]
      },
      {
        "id": "kme-167",
        "municipalityCode": "167",
        "municipalityName": "Lovrenc na Pohorju",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52428081527462,
          15.385407317246422
        ]
      },
      {
        "id": "kme-180",
        "municipalityCode": "180",
        "municipalityName": "Sol\u010dava",
        "score": 74,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40287233027988,
          14.659691125294174
        ]
      },
      {
        "id": "kme-93",
        "municipalityCode": "93",
        "municipalityName": "Podvelka",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.5834090776923,
          15.322536682172196
        ]
      },
      {
        "id": "kme-203",
        "municipalityCode": "203",
        "municipalityName": "Stra\u017ea",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": -8,
        "trendLabel": "-8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.77436787888927,
          15.083138740159075
        ]
      },
      {
        "id": "kme-59",
        "municipalityCode": "59",
        "municipalityName": "Lendava",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": -6,
        "trendLabel": "-6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55480322983082,
          16.443293714800866
        ]
      },
      {
        "id": "kme-139",
        "municipalityCode": "139",
        "municipalityName": "Vojnik",
        "score": 73,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.314220054405595,
          15.306250583089616
        ]
      },
      {
        "id": "kme-62",
        "municipalityCode": "62",
        "municipalityName": "Ljubno",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.366782417214154,
          14.839647523145215
        ]
      },
      {
        "id": "kme-157",
        "municipalityCode": "157",
        "municipalityName": "Dolenjske Toplice",
        "score": 72,
        "level": "Visoko",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.71498204178614,
          15.04208773727281
        ]
      },
      {
        "id": "kme-152",
        "municipalityCode": "152",
        "municipalityName": "Cankova",
        "score": 71,
        "level": "Visoko",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.732847713896774,
          16.02504267492902
        ]
      },
      {
        "id": "kme-176",
        "municipalityCode": "176",
        "municipalityName": "Razkri\u017eje",
        "score": 71,
        "level": "Visoko",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.518664518553564,
          16.27636328832139
        ]
      },
      {
        "id": "kme-138",
        "municipalityCode": "138",
        "municipalityName": "Vodice",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.17058318883487,
          14.498940239372367
        ]
      },
      {
        "id": "kme-50",
        "municipalityCode": "50",
        "municipalityName": "Koper",
        "score": 70,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.51729692077614,
          13.845644980214278
        ]
      },
      {
        "id": "kme-47",
        "municipalityCode": "47",
        "municipalityName": "Kobilje",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.68129118126244,
          16.3875549735546
        ]
      },
      {
        "id": "kme-33",
        "municipalityCode": "33",
        "municipalityName": "\u0160alovci",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.823782651809964,
          16.282020720503965
        ]
      },
      {
        "id": "kme-188",
        "municipalityCode": "188",
        "municipalityName": "Ver\u017eej",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.58331042633665,
          16.17395569480889
        ]
      },
      {
        "id": "kme-78",
        "municipalityCode": "78",
        "municipalityName": "Moravske Toplice",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.71051554569473,
          16.27450061196018
        ]
      },
      {
        "id": "kme-177",
        "municipalityCode": "177",
        "municipalityName": "Ribnica na Pohorju",
        "score": 69,
        "level": "Visoko",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.527914236925454,
          15.259003227781578
        ]
      },
      {
        "id": "kme-97",
        "municipalityCode": "97",
        "municipalityName": "Puconci",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.75514811433649,
          16.121744836334084
        ]
      },
      {
        "id": "kme-165",
        "municipalityCode": "165",
        "municipalityName": "Kostel",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": -8,
        "trendLabel": "-8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.49977703287,
          14.855647138605367
        ]
      },
      {
        "id": "kme-121",
        "municipalityCode": "121",
        "municipalityName": "\u0160kocjan",
        "score": 68,
        "level": "Visoko",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.91391777603153,
          15.296370829550806
        ]
      },
      {
        "id": "kme-26",
        "municipalityCode": "26",
        "municipalityName": "Duplek",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.509356548203,
          15.76263380258807
        ]
      },
      {
        "id": "kme-141",
        "municipalityCode": "141",
        "municipalityName": "Vuzenica",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.564869359461696,
          15.147089282959382
        ]
      },
      {
        "id": "kme-55",
        "municipalityCode": "55",
        "municipalityName": "Kungota",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.641384246364524,
          15.596862785540193
        ]
      },
      {
        "id": "kme-130",
        "municipalityCode": "130",
        "municipalityName": "Trebnje",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.90849357545599,
          14.992782272237456
        ]
      },
      {
        "id": "kme-159",
        "municipalityCode": "159",
        "municipalityName": "Hajdina",
        "score": 67,
        "level": "Visoko",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.4199372070635,
          15.823727524400496
        ]
      },
      {
        "id": "kme-187",
        "municipalityCode": "187",
        "municipalityName": "Velika Polana",
        "score": 66,
        "level": "Srednje",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.57822762617022,
          16.36314075891279
        ]
      },
      {
        "id": "kme-34",
        "municipalityCode": "34",
        "municipalityName": "Hrastnik",
        "score": 66,
        "level": "Srednje",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.135056358286974,
          15.117771444387403
        ]
      },
      {
        "id": "kme-208",
        "municipalityCode": "208",
        "municipalityName": "Log-Dragomer",
        "score": 66,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.013105345724824,
          14.374037563342622
        ]
      },
      {
        "id": "kme-24",
        "municipalityCode": "24",
        "municipalityName": "Dornava",
        "score": 66,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.45422934918125,
          16.005643690430443
        ]
      },
      {
        "id": "kme-202",
        "municipalityCode": "202",
        "municipalityName": "Sredi\u0161\u010de ob Dravi",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": -9,
        "trendLabel": "-9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.40893204220943,
          16.2560429590338
        ]
      },
      {
        "id": "kme-118",
        "municipalityCode": "118",
        "municipalityName": "\u0160entilj",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.66969826173817,
          15.768321280901421
        ]
      },
      {
        "id": "kme-73",
        "municipalityCode": "73",
        "municipalityName": "Metlika",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.650007741795676,
          15.33904423353761
        ]
      },
      {
        "id": "kme-132",
        "municipalityCode": "132",
        "municipalityName": "Turni\u0161\u010de",
        "score": 65,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61501974206358,
          16.31982441265675
        ]
      },
      {
        "id": "kme-156",
        "municipalityCode": "156",
        "municipalityName": "Dobrovnik",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65103869686774,
          16.347760516536397
        ]
      },
      {
        "id": "kme-35",
        "municipalityCode": "35",
        "municipalityName": "Hrpelje-Kozina",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.56287307279571,
          14.012321666704377
        ]
      },
      {
        "id": "kme-124",
        "municipalityCode": "124",
        "municipalityName": "\u0160marje pri Jel\u0161ah",
        "score": 64,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.216960338754866,
          15.517641398331211
        ]
      },
      {
        "id": "kme-45",
        "municipalityCode": "45",
        "municipalityName": "Kidri\u010devo",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.397804846698875,
          15.753727471957369
        ]
      },
      {
        "id": "kme-6",
        "municipalityCode": "6",
        "municipalityName": "Bovec",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 25,
        "trendLabel": "+25 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35645232075714,
          13.61522747174282
        ]
      },
      {
        "id": "kme-85",
        "municipalityCode": "85",
        "municipalityName": "Novo mesto",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": -10,
        "trendLabel": "-10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.78083464918963,
          15.210193521178581
        ]
      },
      {
        "id": "kme-135",
        "municipalityCode": "135",
        "municipalityName": "Videm",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34308610948735,
          15.932125268862329
        ]
      },
      {
        "id": "kme-86",
        "municipalityCode": "86",
        "municipalityName": "Odranci",
        "score": 63,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.58524894185486,
          16.271500112028
        ]
      },
      {
        "id": "kme-212",
        "municipalityCode": "212",
        "municipalityName": "Mirna",
        "score": 62,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94624070491869,
          15.057357064230793
        ]
      },
      {
        "id": "kme-199",
        "municipalityCode": "199",
        "municipalityName": "Mokronog-Trebelno",
        "score": 61,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.92332520079853,
          15.167607176319521
        ]
      },
      {
        "id": "kme-200",
        "municipalityCode": "200",
        "municipalityName": "Polj\u010dane",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.30435958138044,
          15.600314348299081
        ]
      },
      {
        "id": "kme-127",
        "municipalityCode": "127",
        "municipalityName": "\u0160tore",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.198208860154836,
          15.327644837050277
        ]
      },
      {
        "id": "kme-125",
        "municipalityCode": "125",
        "municipalityName": "\u0160martno ob Paki",
        "score": 60,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.33982074119845,
          15.02966843251847
        ]
      },
      {
        "id": "kme-107",
        "municipalityCode": "107",
        "municipalityName": "Rogatec",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.237546603387386,
          15.737454290109904
        ]
      },
      {
        "id": "kme-16",
        "municipalityCode": "16",
        "municipalityName": "\u010crna na Koro\u0161kem",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.46468970620242,
          14.82861013748666
        ]
      },
      {
        "id": "kme-207",
        "municipalityCode": "207",
        "municipalityName": "Gorje",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.39460739717714,
          13.991652514503876
        ]
      },
      {
        "id": "kme-155",
        "municipalityCode": "155",
        "municipalityName": "Dobrna",
        "score": 59,
        "level": "Srednje",
        "trendDeltaScore": 4,
        "trendLabel": "+4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.35280085596145,
          15.22787394880007
        ]
      },
      {
        "id": "kme-31",
        "municipalityCode": "31",
        "municipalityName": "Gornji Petrovci",
        "score": 56,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.799282370682974,
          16.222988126949275
        ]
      },
      {
        "id": "kme-101",
        "municipalityCode": "101",
        "municipalityName": "Radlje ob Dravi",
        "score": 55,
        "level": "Srednje",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.59039965121862,
          15.250063017382363
        ]
      },
      {
        "id": "kme-9",
        "municipalityCode": "9",
        "municipalityName": "Bre\u017eice",
        "score": 55,
        "level": "Srednje",
        "trendDeltaScore": -13,
        "trendLabel": "-13 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.93758133032827,
          15.632917161397213
        ]
      },
      {
        "id": "kme-173",
        "municipalityCode": "173",
        "municipalityName": "Polzela",
        "score": 54,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.30285781054242,
          15.08342525086212
        ]
      },
      {
        "id": "kme-53",
        "municipalityCode": "53",
        "municipalityName": "Kranjska Gora",
        "score": 53,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.45009196707542,
          13.84325717125277
        ]
      },
      {
        "id": "kme-106",
        "municipalityCode": "106",
        "municipalityName": "Roga\u0161ka Slatina",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": -6,
        "trendLabel": "-6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.23776175292087,
          15.627106289016217
        ]
      },
      {
        "id": "kme-111",
        "municipalityCode": "111",
        "municipalityName": "Se\u017eana",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": 12,
        "trendLabel": "+12 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.72640766803438,
          13.889808282981946
        ]
      },
      {
        "id": "kme-82",
        "municipalityCode": "82",
        "municipalityName": "Naklo",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.287306949547784,
          14.290469335122943
        ]
      },
      {
        "id": "kme-205",
        "municipalityCode": "205",
        "municipalityName": "Sveti Toma\u017e",
        "score": 52,
        "level": "Srednje",
        "trendDeltaScore": -6,
        "trendLabel": "-6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.47667884462751,
          16.072191147712203
        ]
      },
      {
        "id": "kme-204",
        "municipalityCode": "204",
        "municipalityName": "Sveta Trojica v Slovenskih goricah",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.56688706224247,
          15.882151799957505
        ]
      },
      {
        "id": "kme-92",
        "municipalityCode": "92",
        "municipalityName": "Pod\u010detrtek",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": -2,
        "trendLabel": "-2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.13618049475401,
          15.568446650547862
        ]
      },
      {
        "id": "kme-89",
        "municipalityCode": "89",
        "municipalityName": "Pesnica",
        "score": 51,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.6179514074537,
          15.706058386796581
        ]
      },
      {
        "id": "kme-153",
        "municipalityCode": "153",
        "municipalityName": "Cerkvenjak",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.55976392834934,
          15.93558833891059
        ]
      },
      {
        "id": "kme-181",
        "municipalityCode": "181",
        "municipalityName": "Sveta Ana",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.65413758124333,
          15.841979457388666
        ]
      },
      {
        "id": "kme-196",
        "municipalityCode": "196",
        "municipalityName": "Cirkulane",
        "score": 50,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.34497051579654,
          15.996158814158486
        ]
      },
      {
        "id": "kme-206",
        "municipalityCode": "206",
        "municipalityName": "\u0160marje\u0161ke Toplice",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": -9,
        "trendLabel": "-9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.88732010142421,
          15.242354970092155
        ]
      },
      {
        "id": "kme-54",
        "municipalityCode": "54",
        "municipalityName": "Kr\u0161ko",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.94614748884751,
          15.46067902792008
        ]
      },
      {
        "id": "kme-119",
        "municipalityCode": "119",
        "municipalityName": "\u0160entjernej",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.82490605624554,
          15.318888102090748
        ]
      },
      {
        "id": "kme-191",
        "municipalityCode": "191",
        "municipalityName": "\u017detale",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": 1,
        "trendLabel": "+1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.288241806796265,
          15.795755968346992
        ]
      },
      {
        "id": "kme-161",
        "municipalityCode": "161",
        "municipalityName": "Hodo\u0161",
        "score": 49,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.8317205363355,
          16.329800593473202
        ]
      },
      {
        "id": "kme-193",
        "municipalityCode": "193",
        "municipalityName": "\u017du\u017eemberk",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": -3,
        "trendLabel": "-3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.80718245218927,
          14.96851775759558
        ]
      },
      {
        "id": "kme-42",
        "municipalityCode": "42",
        "municipalityName": "Jur\u0161inci",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.48293327291799,
          15.96934235489326
        ]
      },
      {
        "id": "kme-90",
        "municipalityCode": "90",
        "municipalityName": "Piran",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.49274890235444,
          13.61379369688393
        ]
      },
      {
        "id": "kme-143",
        "municipalityCode": "143",
        "municipalityName": "Zavr\u010d",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.363724404629636,
          16.04440479134854
        ]
      },
      {
        "id": "kme-154",
        "municipalityCode": "154",
        "municipalityName": "Dobje",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.134840909929885,
          15.399986336385783
        ]
      },
      {
        "id": "kme-49",
        "municipalityCode": "49",
        "municipalityName": "Komen",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": 10,
        "trendLabel": "+10 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.81922942618834,
          13.790004305936154
        ]
      },
      {
        "id": "kme-201",
        "municipalityCode": "201",
        "municipalityName": "Ren\u010de-Vogrsko",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.89501134194833,
          13.677466938393653
        ]
      },
      {
        "id": "kme-172",
        "municipalityCode": "172",
        "municipalityName": "Podlehnik",
        "score": 48,
        "level": "Srednje",
        "trendDeltaScore": -6,
        "trendLabel": "-6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.315276293961766,
          15.861600612684818
        ]
      },
      {
        "id": "kme-69",
        "municipalityCode": "69",
        "municipalityName": "Maj\u0161perk",
        "score": 47,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.31567282469143,
          15.747678399772571
        ]
      },
      {
        "id": "kme-46",
        "municipalityCode": "46",
        "municipalityName": "Kobarid",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.24302837192627,
          13.546950740104418
        ]
      },
      {
        "id": "kme-170",
        "municipalityCode": "170",
        "municipalityName": "Mirna Pe\u010d",
        "score": 45,
        "level": "Srednje",
        "trendDeltaScore": -7,
        "trendLabel": "-7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.854087813451216,
          15.081100461762297
        ]
      },
      {
        "id": "kme-197",
        "municipalityCode": "197",
        "municipalityName": "Kostanjevica na Krki",
        "score": 44,
        "level": "Srednje",
        "trendDeltaScore": -4,
        "trendLabel": "-4 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.841500599300915,
          15.419015231683833
        ]
      },
      {
        "id": "kme-158",
        "municipalityCode": "158",
        "municipalityName": "Grad",
        "score": 44,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.79466554948839,
          16.095160030316443
        ]
      },
      {
        "id": "kme-75",
        "municipalityCode": "75",
        "municipalityName": "Miren-Kostanjevica",
        "score": 42,
        "level": "Srednje",
        "trendDeltaScore": 6,
        "trendLabel": "+6 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          45.859821002386994,
          13.64983376393198
        ]
      },
      {
        "id": "kme-148",
        "municipalityCode": "148",
        "municipalityName": "Benedikt",
        "score": 41,
        "level": "Srednje",
        "trendDeltaScore": -8,
        "trendLabel": "-8 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61404004922419,
          15.882097044546224
        ]
      },
      {
        "id": "kme-51",
        "municipalityCode": "51",
        "municipalityName": "Kozje",
        "score": 40,
        "level": "Srednje",
        "trendDeltaScore": 5,
        "trendLabel": "+5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.064888860017504,
          15.556359799680841
        ]
      },
      {
        "id": "kme-198",
        "municipalityCode": "198",
        "municipalityName": "Makole",
        "score": 39,
        "level": "Srednje",
        "trendDeltaScore": 2,
        "trendLabel": "+2 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.312669429468,
          15.678908945065823
        ]
      },
      {
        "id": "kme-149",
        "municipalityCode": "149",
        "municipalityName": "Bistrica ob Sotli",
        "score": 39,
        "level": "Srednje",
        "trendDeltaScore": -5,
        "trendLabel": "-5 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.05922075203121,
          15.653185617048514
        ]
      },
      {
        "id": "kme-210",
        "municipalityCode": "210",
        "municipalityName": "Sveti Jurij v Slovenskih goricah",
        "score": 38,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.61298948846985,
          15.797230370143808
        ]
      },
      {
        "id": "kme-105",
        "municipalityCode": "105",
        "municipalityName": "Roga\u0161ovci",
        "score": 38,
        "level": "Srednje",
        "trendDeltaScore": 7,
        "trendLabel": "+7 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.797565278402416,
          16.024175797259314
        ]
      },
      {
        "id": "kme-18",
        "municipalityCode": "18",
        "municipalityName": "Destrnik",
        "score": 38,
        "level": "Srednje",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.47883364411645,
          15.886380524887887
        ]
      },
      {
        "id": "kme-44",
        "municipalityCode": "44",
        "municipalityName": "Kanal",
        "score": 38,
        "level": "Srednje",
        "trendDeltaScore": 9,
        "trendLabel": "+9 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.08408342299698,
          13.663446283081377
        ]
      },
      {
        "id": "kme-56",
        "municipalityCode": "56",
        "municipalityName": "Kuzma",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": 3,
        "trendLabel": "+3 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.83994788396974,
          16.092505197420564
        ]
      },
      {
        "id": "kme-182",
        "municipalityCode": "182",
        "municipalityName": "Sveti Andra\u017e v Slov. goricah",
        "score": 36,
        "level": "Srednje",
        "trendDeltaScore": -1,
        "trendLabel": "-1 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.518201223045246,
          15.951098855339616
        ]
      },
      {
        "id": "kme-7",
        "municipalityCode": "7",
        "municipalityName": "Brda",
        "score": 34,
        "level": "Srednje",
        "trendDeltaScore": 11,
        "trendLabel": "+11 to\u010dk glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.016115323055345,
          13.549030517054824
        ]
      },
      {
        "id": "kme-185",
        "municipalityCode": "185",
        "municipalityName": "Trnovska vas",
        "score": 30,
        "level": "Nizko",
        "trendDeltaScore": 0,
        "trendLabel": "brez spremembe glede na prej\u0161nji teden",
        "weekStart": "2026-04-13",
        "weekEnd": "2026-04-19",
        "coordinates": [
          46.52611418774025,
          15.890388308225477
        ]
      }
    ],
    "featuredLocations": [
      {
        "municipalityName": "Maribor",
        "municipalityCode": "70",
        "level": "Visoko",
        "score": 100,
        "id": "kme-70"
      },
      {
        "municipalityName": "Ljubljana",
        "municipalityCode": "61",
        "level": "Visoko",
        "score": 99,
        "id": "kme-61"
      },
      {
        "municipalityName": "Logatec",
        "municipalityCode": "64",
        "level": "Visoko",
        "score": 99,
        "id": "kme-64"
      },
      {
        "municipalityName": "Kamnik",
        "municipalityCode": "43",
        "level": "Visoko",
        "score": 98,
        "id": "kme-43"
      },
      {
        "municipalityName": "Postojna",
        "municipalityCode": "94",
        "level": "Visoko",
        "score": 98,
        "id": "kme-94"
      },
      {
        "municipalityName": "Slovenska Bistrica",
        "municipalityCode": "113",
        "level": "Visoko",
        "score": 98,
        "id": "kme-113"
      },
      {
        "municipalityName": "Tr\u017ei\u010d",
        "municipalityCode": "131",
        "level": "Visoko",
        "score": 98,
        "id": "kme-131"
      },
      {
        "municipalityName": "Kranj",
        "municipalityCode": "52",
        "level": "Visoko",
        "score": 98,
        "id": "kme-52"
      }
    ]
  }
}
