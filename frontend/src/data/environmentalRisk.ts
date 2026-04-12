export type RiskLevel = 'Nizko' | 'Srednje' | 'Visoko'

export type DiseaseModelKey = 'borelioza' | 'kme'

export type EnvironmentalRiskLocation = {
  id: string
  municipalityCode: string
  municipalityName: string
  score: number
  level: RiskLevel
  weekStart: string
  coordinates: [number, number]
}

export type EnvironmentalRiskModel = {
  key: DiseaseModelKey
  diseaseLabel: string
  modelId: string
  legacyResearchModelId: string
  snapshotWeekStart: string
  snapshotLabel: string
  purpose: string
  disclaimer: string
  scoreExplanation: string
  topDrivers: string[]
  thresholds: {
    lowUpper: number
    mediumUpper: number
  }
  metricSummary: string
  locations: EnvironmentalRiskLocation[]
  featuredLocations: Array<{
    municipalityName: string
    level: RiskLevel
    score: number
    id: string
  }>
}

export const environmentalRiskModels: Record<DiseaseModelKey, EnvironmentalRiskModel> = {
  "borelioza": {
    "key": "borelioza",
    "diseaseLabel": "Borelioza",
    "modelId": "catboost_tick_borne_lyme_env_v1",
    "legacyResearchModelId": "catboost_tick_borne_lyme_v1",
    "snapshotWeekStart": "2025-11-24",
    "snapshotLabel": "zadnji razpolozljivi holdout teden",
    "purpose": "Okoljski risk model za boreliozo po lokaciji.",
    "disclaimer": "To ni napoved diagnoze ali verjetnosti bolezni pri posamezniku, ampak okoljski risk score, preveden v Nizko, Srednje ali Visoko.",
    "scoreExplanation": "Score temelji na relativni uvrstitvi znotraj holdout napovedi in je namenjen primerjavi lokacij, ne interpretaciji surovega stevila primerov.",
    "topDrivers": [
      "sezona aktivnosti klopov",
      "4-tedensko povprecje temperature zraka",
      "urbaniziranost in robni habitat",
      "razgiban relief",
      "temperaturni zamik iz prejsnjih tednov"
    ],
    "thresholds": {
      "lowUpper": 16.094859,
      "mediumUpper": 21.680672
    },
    "metricSummary": "Test RMSE 29.4, MAE 20.3, R² 0.12.",
    "locations": [
      {
        "id": "borelioza-46",
        "municipalityCode": "46",
        "municipalityName": "Kobarid",
        "score": 64,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.25158,
          13.55544
        ]
      },
      {
        "id": "borelioza-180",
        "municipalityCode": "180",
        "municipalityName": "Solčava",
        "score": 61,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.40504,
          14.65815
        ]
      },
      {
        "id": "borelioza-67",
        "municipalityCode": "67",
        "municipalityName": "Luče",
        "score": 56,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.35567,
          14.72738
        ]
      },
      {
        "id": "borelioza-128",
        "municipalityCode": "128",
        "municipalityName": "Tolmin",
        "score": 48,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.16987,
          13.80884
        ]
      },
      {
        "id": "borelioza-1",
        "municipalityCode": "1",
        "municipalityName": "Ajdovščina",
        "score": 37,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.89933,
          13.90766
        ]
      },
      {
        "id": "borelioza-84",
        "municipalityCode": "84",
        "municipalityName": "Nova Gorica",
        "score": 37,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.98051,
          13.74061
        ]
      },
      {
        "id": "borelioza-136",
        "municipalityCode": "136",
        "municipalityName": "Vipava",
        "score": 35,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.82188,
          13.98485
        ]
      },
      {
        "id": "borelioza-207",
        "municipalityCode": "207",
        "municipalityName": "Gorje",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.39027,
          13.98265
        ]
      },
      {
        "id": "borelioza-163",
        "municipalityCode": "163",
        "municipalityName": "Jezersko",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.38704,
          14.48286
        ]
      },
      {
        "id": "borelioza-4",
        "municipalityCode": "4",
        "municipalityName": "Bohinj",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.2941,
          13.91593
        ]
      },
      {
        "id": "borelioza-53",
        "municipalityCode": "53",
        "municipalityName": "Kranjska Gora",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.46049,
          13.84612
        ]
      },
      {
        "id": "borelioza-192",
        "municipalityCode": "192",
        "municipalityName": "Žirovnica",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.41067,
          14.16884
        ]
      },
      {
        "id": "borelioza-95",
        "municipalityCode": "95",
        "municipalityName": "Preddvor",
        "score": 32,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.32417,
          14.46492
        ]
      },
      {
        "id": "borelioza-6",
        "municipalityCode": "6",
        "municipalityName": "Bovec",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.35558,
          13.62372
        ]
      },
      {
        "id": "borelioza-143",
        "municipalityCode": "143",
        "municipalityName": "Zavrč",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.36155,
          16.0461
        ]
      },
      {
        "id": "borelioza-50",
        "municipalityCode": "50",
        "municipalityName": "Koper",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.50969,
          13.83812
        ]
      },
      {
        "id": "borelioza-196",
        "municipalityCode": "196",
        "municipalityName": "Cirkulane",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.34166,
          15.99535
        ]
      },
      {
        "id": "borelioza-183",
        "municipalityCode": "183",
        "municipalityName": "Šempeter-Vrtojba",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.91542,
          13.64676
        ]
      },
      {
        "id": "borelioza-113",
        "municipalityCode": "113",
        "municipalityName": "Slovenska Bistrica",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.41402,
          15.53371
        ]
      },
      {
        "id": "borelioza-38",
        "municipalityCode": "38",
        "municipalityName": "Ilirska Bistrica",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.56636,
          14.28632
        ]
      },
      {
        "id": "borelioza-102",
        "municipalityCode": "102",
        "municipalityName": "Radovljica",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.33794,
          14.20237
        ]
      },
      {
        "id": "borelioza-43",
        "municipalityCode": "43",
        "municipalityName": "Kamnik",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.25706,
          14.67696
        ]
      },
      {
        "id": "borelioza-75",
        "municipalityCode": "75",
        "municipalityName": "Miren-Kostanjevica",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.85219,
          13.6381
        ]
      },
      {
        "id": "borelioza-42",
        "municipalityCode": "42",
        "municipalityName": "Juršinci",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.48558,
          15.97302
        ]
      },
      {
        "id": "borelioza-182",
        "municipalityCode": "182",
        "municipalityName": "Sveti Andraž v Slov. goricah",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52299,
          15.95229
        ]
      },
      {
        "id": "borelioza-205",
        "municipalityCode": "205",
        "municipalityName": "Sveti Tomaž",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.47974,
          16.06681
        ]
      },
      {
        "id": "borelioza-198",
        "municipalityCode": "198",
        "municipalityName": "Makole",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.31578,
          15.67488
        ]
      },
      {
        "id": "borelioza-41",
        "municipalityCode": "41",
        "municipalityName": "Jesenice",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.44923,
          14.0721
        ]
      },
      {
        "id": "borelioza-191",
        "municipalityCode": "191",
        "municipalityName": "Žetale",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.28253,
          15.8008
        ]
      },
      {
        "id": "borelioza-12",
        "municipalityCode": "12",
        "municipalityName": "Cerklje na Gorenjskem",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.25284,
          14.50003
        ]
      },
      {
        "id": "borelioza-131",
        "municipalityCode": "131",
        "municipalityName": "Tržič",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.38851,
          14.33075
        ]
      },
      {
        "id": "borelioza-161",
        "municipalityCode": "161",
        "municipalityName": "Hodoš",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.82809,
          16.32072
        ]
      },
      {
        "id": "borelioza-49",
        "municipalityCode": "49",
        "municipalityName": "Komen",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.81496,
          13.75433
        ]
      },
      {
        "id": "borelioza-18",
        "municipalityCode": "18",
        "municipalityName": "Destrnik",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.48342,
          15.88047
        ]
      },
      {
        "id": "borelioza-185",
        "municipalityCode": "185",
        "municipalityName": "Trnovska vas",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52278,
          15.88848
        ]
      },
      {
        "id": "borelioza-149",
        "municipalityCode": "149",
        "municipalityName": "Bistrica ob Sotli",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.05861,
          15.64685
        ]
      },
      {
        "id": "borelioza-7",
        "municipalityCode": "7",
        "municipalityName": "Brda",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.0125,
          13.54538
        ]
      },
      {
        "id": "borelioza-210",
        "municipalityCode": "210",
        "municipalityName": "Sveti Jurij v Slovenskih goricah",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.61282,
          15.78816
        ]
      },
      {
        "id": "borelioza-79",
        "municipalityCode": "79",
        "municipalityName": "Mozirje",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.3605,
          14.95542
        ]
      },
      {
        "id": "borelioza-201",
        "municipalityCode": "201",
        "municipalityName": "Renče-Vogrsko",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.89106,
          13.67991
        ]
      },
      {
        "id": "borelioza-16",
        "municipalityCode": "16",
        "municipalityName": "Črna na Koroškem",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.46341,
          14.82871
        ]
      },
      {
        "id": "borelioza-111",
        "municipalityCode": "111",
        "municipalityName": "Sežana",
        "score": 27,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.73622,
          13.88163
        ]
      },
      {
        "id": "borelioza-62",
        "municipalityCode": "62",
        "municipalityName": "Ljubno",
        "score": 27,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.37043,
          14.84401
        ]
      },
      {
        "id": "borelioza-30",
        "municipalityCode": "30",
        "municipalityName": "Gornji Grad",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.28805,
          14.78828
        ]
      },
      {
        "id": "borelioza-160",
        "municipalityCode": "160",
        "municipalityName": "Hoče-Slivnica",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.49112,
          15.62712
        ]
      },
      {
        "id": "borelioza-87",
        "municipalityCode": "87",
        "municipalityName": "Ormož",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.43767,
          16.15146
        ]
      },
      {
        "id": "borelioza-176",
        "municipalityCode": "176",
        "municipalityName": "Razkrižje",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52047,
          16.27405
        ]
      },
      {
        "id": "borelioza-2",
        "municipalityCode": "2",
        "municipalityName": "Beltinci",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.608,
          16.23173
        ]
      },
      {
        "id": "borelioza-28",
        "municipalityCode": "28",
        "municipalityName": "Gorišnica",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.40602,
          16.01072
        ]
      },
      {
        "id": "borelioza-166",
        "municipalityCode": "166",
        "municipalityName": "Križevci",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56403,
          16.11797
        ]
      },
      {
        "id": "borelioza-59",
        "municipalityCode": "59",
        "municipalityName": "Lendava",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.55683,
          16.44489
        ]
      },
      {
        "id": "borelioza-86",
        "municipalityCode": "86",
        "municipalityName": "Odranci",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.58602,
          16.27128
        ]
      },
      {
        "id": "borelioza-132",
        "municipalityCode": "132",
        "municipalityName": "Turnišče",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.61608,
          16.31347
        ]
      },
      {
        "id": "borelioza-188",
        "municipalityCode": "188",
        "municipalityName": "Veržej",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.58257,
          16.16407
        ]
      },
      {
        "id": "borelioza-52",
        "municipalityCode": "52",
        "municipalityName": "Kranj",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.25499,
          14.33409
        ]
      },
      {
        "id": "borelioza-31",
        "municipalityCode": "31",
        "municipalityName": "Gornji Petrovci",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.80727,
          16.20514
        ]
      },
      {
        "id": "borelioza-146",
        "municipalityCode": "146",
        "municipalityName": "Železniki",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.21874,
          14.11034
        ]
      },
      {
        "id": "borelioza-209",
        "municipalityCode": "209",
        "municipalityName": "Rečica ob Savinji",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.32806,
          14.90312
        ]
      },
      {
        "id": "borelioza-168",
        "municipalityCode": "168",
        "municipalityName": "Markovci",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.39064,
          15.9488
        ]
      },
      {
        "id": "borelioza-80",
        "municipalityCode": "80",
        "municipalityName": "Murska Sobota",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.64843,
          16.15475
        ]
      },
      {
        "id": "borelioza-63",
        "municipalityCode": "63",
        "municipalityName": "Ljutomer",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52108,
          16.157
        ]
      },
      {
        "id": "borelioza-181",
        "municipalityCode": "181",
        "municipalityName": "Sveta Ana",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.65241,
          15.83617
        ]
      },
      {
        "id": "borelioza-202",
        "municipalityCode": "202",
        "municipalityName": "Središče ob Dravi",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.40261,
          16.25511
        ]
      },
      {
        "id": "borelioza-109",
        "municipalityCode": "109",
        "municipalityName": "Semič",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.65166,
          15.14432
        ]
      },
      {
        "id": "borelioza-96",
        "municipalityCode": "96",
        "municipalityName": "Ptuj",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.4419,
          15.87417
        ]
      },
      {
        "id": "borelioza-159",
        "municipalityCode": "159",
        "municipalityName": "Hajdina",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.42017,
          15.82577
        ]
      },
      {
        "id": "borelioza-45",
        "municipalityCode": "45",
        "municipalityName": "Kidričevo",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.39512,
          15.74984
        ]
      },
      {
        "id": "borelioza-115",
        "municipalityCode": "115",
        "municipalityName": "Starše",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.45792,
          15.75539
        ]
      },
      {
        "id": "borelioza-25",
        "municipalityCode": "25",
        "municipalityName": "Dravograd",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.59749,
          15.03387
        ]
      },
      {
        "id": "borelioza-135",
        "municipalityCode": "135",
        "municipalityName": "Videm",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.347,
          15.8929
        ]
      },
      {
        "id": "borelioza-172",
        "municipalityCode": "172",
        "municipalityName": "Podlehnik",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.31623,
          15.86533
        ]
      },
      {
        "id": "borelioza-107",
        "municipalityCode": "107",
        "municipalityName": "Rogatec",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.23858,
          15.74206
        ]
      },
      {
        "id": "borelioza-47",
        "municipalityCode": "47",
        "municipalityName": "Kobilje",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.68087,
          16.39098
        ]
      },
      {
        "id": "borelioza-126",
        "municipalityCode": "126",
        "municipalityName": "Šoštanj",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.40613,
          15.00495
        ]
      },
      {
        "id": "borelioza-177",
        "municipalityCode": "177",
        "municipalityName": "Ribnica na Pohorju",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52398,
          15.26008
        ]
      },
      {
        "id": "borelioza-144",
        "municipalityCode": "144",
        "municipalityName": "Zreče",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.40013,
          15.36645
        ]
      },
      {
        "id": "borelioza-156",
        "municipalityCode": "156",
        "municipalityName": "Dobrovnik",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.65096,
          16.34693
        ]
      },
      {
        "id": "borelioza-158",
        "municipalityCode": "158",
        "municipalityName": "Grad",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.79435,
          16.09494
        ]
      },
      {
        "id": "borelioza-56",
        "municipalityCode": "56",
        "municipalityName": "Kuzma",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.84048,
          16.0948
        ]
      },
      {
        "id": "borelioza-10",
        "municipalityCode": "10",
        "municipalityName": "Tišina",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.66104,
          16.07849
        ]
      },
      {
        "id": "borelioza-165",
        "municipalityCode": "165",
        "municipalityName": "Kostel",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.49901,
          14.86189
        ]
      },
      {
        "id": "borelioza-153",
        "municipalityCode": "153",
        "municipalityName": "Cerkvenjak",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56097,
          15.94254
        ]
      },
      {
        "id": "borelioza-29",
        "municipalityCode": "29",
        "municipalityName": "Gornja Radgona",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.63609,
          15.96145
        ]
      },
      {
        "id": "borelioza-78",
        "municipalityCode": "78",
        "municipalityName": "Moravske Toplice",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.70934,
          16.2702
        ]
      },
      {
        "id": "borelioza-100",
        "municipalityCode": "100",
        "municipalityName": "Radenci",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.62,
          16.04424
        ]
      },
      {
        "id": "borelioza-116",
        "municipalityCode": "116",
        "municipalityName": "Sveti Jurij ob Ščavnici",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56482,
          16.02455
        ]
      },
      {
        "id": "borelioza-204",
        "municipalityCode": "204",
        "municipalityName": "Sveta Trojica v Slovenskih goricah",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56983,
          15.88619
        ]
      },
      {
        "id": "borelioza-44",
        "municipalityCode": "44",
        "municipalityName": "Kanal",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.0837,
          13.6523
        ]
      },
      {
        "id": "borelioza-119",
        "municipalityCode": "119",
        "municipalityName": "Šentjernej",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.82652,
          15.33251
        ]
      },
      {
        "id": "borelioza-15",
        "municipalityCode": "15",
        "municipalityName": "Črenšovci",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.55589,
          16.2957
        ]
      },
      {
        "id": "borelioza-169",
        "municipalityCode": "169",
        "municipalityName": "Miklavž na Dravskem polju",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.48871,
          15.70724
        ]
      },
      {
        "id": "borelioza-195",
        "municipalityCode": "195",
        "municipalityName": "Apače",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.69301,
          15.87349
        ]
      },
      {
        "id": "borelioza-26",
        "municipalityCode": "26",
        "municipalityName": "Duplek",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.51166,
          15.7664
        ]
      },
      {
        "id": "borelioza-97",
        "municipalityCode": "97",
        "municipalityName": "Puconci",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.74449,
          16.13383
        ]
      },
      {
        "id": "borelioza-103",
        "municipalityCode": "103",
        "municipalityName": "Ravne na Koroškem",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.54582,
          14.96111
        ]
      },
      {
        "id": "borelioza-3",
        "municipalityCode": "3",
        "municipalityName": "Bled",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.34565,
          14.07874
        ]
      },
      {
        "id": "borelioza-83",
        "municipalityCode": "83",
        "municipalityName": "Nazarje",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.28266,
          14.91303
        ]
      },
      {
        "id": "borelioza-8",
        "municipalityCode": "8",
        "municipalityName": "Brezovica",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.94839,
          14.42447
        ]
      },
      {
        "id": "borelioza-14",
        "municipalityCode": "14",
        "municipalityName": "Cerkno",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.12469,
          13.9724
        ]
      },
      {
        "id": "borelioza-69",
        "municipalityCode": "69",
        "municipalityName": "Majšperk",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.32442,
          15.7395
        ]
      },
      {
        "id": "borelioza-65",
        "municipalityCode": "65",
        "municipalityName": "Loška dolina",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.66842,
          14.48358
        ]
      },
      {
        "id": "borelioza-157",
        "municipalityCode": "157",
        "municipalityName": "Dolenjske Toplice",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.72435,
          15.03304
        ]
      },
      {
        "id": "borelioza-187",
        "municipalityCode": "187",
        "municipalityName": "Velika Polana",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.57878,
          16.35359
        ]
      },
      {
        "id": "borelioza-36",
        "municipalityCode": "36",
        "municipalityName": "Idrija",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.98907,
          14.00447
        ]
      },
      {
        "id": "borelioza-213",
        "municipalityCode": "213",
        "municipalityName": "Ankaran",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.57539,
          13.74243
        ]
      },
      {
        "id": "borelioza-154",
        "municipalityCode": "154",
        "municipalityName": "Dobje",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13254,
          15.39711
        ]
      },
      {
        "id": "borelioza-152",
        "municipalityCode": "152",
        "municipalityName": "Cankova",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.73564,
          16.02503
        ]
      },
      {
        "id": "borelioza-33",
        "municipalityCode": "33",
        "municipalityName": "Šalovci",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.83331,
          16.26175
        ]
      },
      {
        "id": "borelioza-105",
        "municipalityCode": "105",
        "municipalityName": "Rogašovci",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.79958,
          16.02603
        ]
      },
      {
        "id": "borelioza-24",
        "municipalityCode": "24",
        "municipalityName": "Dornava",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.44888,
          15.99036
        ]
      },
      {
        "id": "borelioza-37",
        "municipalityCode": "37",
        "municipalityName": "Ig",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.93321,
          14.51632
        ]
      },
      {
        "id": "borelioza-76",
        "municipalityCode": "76",
        "municipalityName": "Mislinja",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.44695,
          15.21992
        ]
      },
      {
        "id": "borelioza-48",
        "municipalityCode": "48",
        "municipalityName": "Kočevje",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.6184,
          14.90291
        ]
      },
      {
        "id": "borelioza-167",
        "municipalityCode": "167",
        "municipalityName": "Lovrenc na Pohorju",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.52589,
          15.38364
        ]
      },
      {
        "id": "borelioza-117",
        "municipalityCode": "117",
        "municipalityName": "Šenčur",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.23522,
          14.42605
        ]
      },
      {
        "id": "borelioza-22",
        "municipalityCode": "22",
        "municipalityName": "Dol pri Ljubljani",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.09396,
          14.67296
        ]
      },
      {
        "id": "borelioza-70",
        "municipalityCode": "70",
        "municipalityName": "Maribor",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56345,
          15.62729
        ]
      },
      {
        "id": "borelioza-203",
        "municipalityCode": "203",
        "municipalityName": "Straža",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.77723,
          15.09133
        ]
      },
      {
        "id": "borelioza-186",
        "municipalityCode": "186",
        "municipalityName": "Trzin",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.12788,
          14.55234
        ]
      },
      {
        "id": "borelioza-137",
        "municipalityCode": "137",
        "municipalityName": "Vitanje",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.4023,
          15.29348
        ]
      },
      {
        "id": "borelioza-134",
        "municipalityCode": "134",
        "municipalityName": "Velike Lašče",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.84313,
          14.58714
        ]
      },
      {
        "id": "borelioza-162",
        "municipalityCode": "162",
        "municipalityName": "Horjul",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.02255,
          14.28673
        ]
      },
      {
        "id": "borelioza-148",
        "municipalityCode": "148",
        "municipalityName": "Benedikt",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.61731,
          15.89098
        ]
      },
      {
        "id": "borelioza-19",
        "municipalityCode": "19",
        "municipalityName": "Divača",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.68619,
          14.02557
        ]
      },
      {
        "id": "borelioza-35",
        "municipalityCode": "35",
        "municipalityName": "Hrpelje-Kozina",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.5695,
          14.00871
        ]
      },
      {
        "id": "borelioza-112",
        "municipalityCode": "112",
        "municipalityName": "Slovenj Gradec",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.48941,
          15.07872
        ]
      },
      {
        "id": "borelioza-71",
        "municipalityCode": "71",
        "municipalityName": "Medvode",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13101,
          14.40044
        ]
      },
      {
        "id": "borelioza-138",
        "municipalityCode": "138",
        "municipalityName": "Vodice",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.17118,
          14.49313
        ]
      },
      {
        "id": "borelioza-60",
        "municipalityCode": "60",
        "municipalityName": "Litija",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.05632,
          14.91962
        ]
      },
      {
        "id": "borelioza-108",
        "municipalityCode": "108",
        "municipalityName": "Ruše",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.51658,
          15.48714
        ]
      },
      {
        "id": "borelioza-106",
        "municipalityCode": "106",
        "municipalityName": "Rogaška Slatina",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.24785,
          15.62844
        ]
      },
      {
        "id": "borelioza-72",
        "municipalityCode": "72",
        "municipalityName": "Mengeš",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.15963,
          14.55761
        ]
      },
      {
        "id": "borelioza-40",
        "municipalityCode": "40",
        "municipalityName": "Izola",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.51344,
          13.65846
        ]
      },
      {
        "id": "borelioza-88",
        "municipalityCode": "88",
        "municipalityName": "Osilnica",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.54726,
          14.732
        ]
      },
      {
        "id": "borelioza-17",
        "municipalityCode": "17",
        "municipalityName": "Črnomelj",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.52105,
          15.19651
        ]
      },
      {
        "id": "borelioza-73",
        "municipalityCode": "73",
        "municipalityName": "Metlika",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.6562,
          15.29667
        ]
      },
      {
        "id": "borelioza-58",
        "municipalityCode": "58",
        "municipalityName": "Lenart",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.55778,
          15.81873
        ]
      },
      {
        "id": "borelioza-197",
        "municipalityCode": "197",
        "municipalityName": "Kostanjevica na Krki",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.83755,
          15.42073
        ]
      },
      {
        "id": "borelioza-90",
        "municipalityCode": "90",
        "municipalityName": "Piran",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.48784,
          13.63438
        ]
      },
      {
        "id": "borelioza-121",
        "municipalityCode": "121",
        "municipalityName": "Škocjan",
        "score": 14,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.9167,
          15.29834
        ]
      },
      {
        "id": "borelioza-89",
        "municipalityCode": "89",
        "municipalityName": "Pesnica",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.61962,
          15.70986
        ]
      },
      {
        "id": "borelioza-91",
        "municipalityCode": "91",
        "municipalityName": "Pivka",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.68166,
          14.23565
        ]
      },
      {
        "id": "borelioza-141",
        "municipalityCode": "141",
        "municipalityName": "Vuzenica",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.56839,
          15.15986
        ]
      },
      {
        "id": "borelioza-32",
        "municipalityCode": "32",
        "municipalityName": "Grosuplje",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.93954,
          14.66942
        ]
      },
      {
        "id": "borelioza-123",
        "municipalityCode": "123",
        "municipalityName": "Škofljica",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.96578,
          14.57359
        ]
      },
      {
        "id": "borelioza-194",
        "municipalityCode": "194",
        "municipalityName": "Šmartno pri Litiji",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.02285,
          14.84481
        ]
      },
      {
        "id": "borelioza-54",
        "municipalityCode": "54",
        "municipalityName": "Krško",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.95595,
          15.46302
        ]
      },
      {
        "id": "borelioza-155",
        "municipalityCode": "155",
        "municipalityName": "Dobrna",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.3563,
          15.22364
        ]
      },
      {
        "id": "borelioza-212",
        "municipalityCode": "212",
        "municipalityName": "Mirna",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.94518,
          15.05695
        ]
      },
      {
        "id": "borelioza-208",
        "municipalityCode": "208",
        "municipalityName": "Log-Dragomer",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.01438,
          14.37329
        ]
      },
      {
        "id": "borelioza-11",
        "municipalityCode": "11",
        "municipalityName": "Celje",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.24862,
          15.26605
        ]
      },
      {
        "id": "borelioza-55",
        "municipalityCode": "55",
        "municipalityName": "Kungota",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.64536,
          15.6012
        ]
      },
      {
        "id": "borelioza-61",
        "municipalityCode": "61",
        "municipalityName": "Ljubljana",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.05429,
          14.56291
        ]
      },
      {
        "id": "borelioza-173",
        "municipalityCode": "173",
        "municipalityName": "Polzela",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.30303,
          15.08507
        ]
      },
      {
        "id": "borelioza-98",
        "municipalityCode": "98",
        "municipalityName": "Rače-Fram",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.44877,
          15.64562
        ]
      },
      {
        "id": "borelioza-114",
        "municipalityCode": "114",
        "municipalityName": "Slovenske Konjice",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.32267,
          15.46121
        ]
      },
      {
        "id": "borelioza-120",
        "municipalityCode": "120",
        "municipalityName": "Šentjur",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.1897,
          15.42415
        ]
      },
      {
        "id": "borelioza-211",
        "municipalityCode": "211",
        "municipalityName": "Šentrupert",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.98427,
          15.0896
        ]
      },
      {
        "id": "borelioza-190",
        "municipalityCode": "190",
        "municipalityName": "Žalec",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.25909,
          15.16567
        ]
      },
      {
        "id": "borelioza-51",
        "municipalityCode": "51",
        "municipalityName": "Kozje",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.0719,
          15.54951
        ]
      },
      {
        "id": "borelioza-66",
        "municipalityCode": "66",
        "municipalityName": "Loški Potok",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.66375,
          14.64078
        ]
      },
      {
        "id": "borelioza-9",
        "municipalityCode": "9",
        "municipalityName": "Brežice",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.93154,
          15.62089
        ]
      },
      {
        "id": "borelioza-206",
        "municipalityCode": "206",
        "municipalityName": "Šmarješke Toplice",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.88414,
          15.24347
        ]
      },
      {
        "id": "borelioza-193",
        "municipalityCode": "193",
        "municipalityName": "Žužemberk",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.80801,
          14.93106
        ]
      },
      {
        "id": "borelioza-139",
        "municipalityCode": "139",
        "municipalityName": "Vojnik",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.31835,
          15.30826
        ]
      },
      {
        "id": "borelioza-124",
        "municipalityCode": "124",
        "municipalityName": "Šmarje pri Jelšah",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.21493,
          15.51993
        ]
      },
      {
        "id": "borelioza-82",
        "municipalityCode": "82",
        "municipalityName": "Naklo",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.29165,
          14.29642
        ]
      },
      {
        "id": "borelioza-92",
        "municipalityCode": "92",
        "municipalityName": "Podčetrtek",
        "score": 11,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.14332,
          15.58578
        ]
      },
      {
        "id": "borelioza-27",
        "municipalityCode": "27",
        "municipalityName": "Gorenja vas-Poljane",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.11481,
          14.13589
        ]
      },
      {
        "id": "borelioza-118",
        "municipalityCode": "118",
        "municipalityName": "Šentilj",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.67584,
          15.71605
        ]
      },
      {
        "id": "borelioza-5",
        "municipalityCode": "5",
        "municipalityName": "Borovnica",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.91315,
          14.37827
        ]
      },
      {
        "id": "borelioza-104",
        "municipalityCode": "104",
        "municipalityName": "Ribnica",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.73272,
          14.718
        ]
      },
      {
        "id": "borelioza-140",
        "municipalityCode": "140",
        "municipalityName": "Vrhnika",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.95918,
          14.29482
        ]
      },
      {
        "id": "borelioza-150",
        "municipalityCode": "150",
        "municipalityName": "Bloke",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.78389,
          14.51028
        ]
      },
      {
        "id": "borelioza-179",
        "municipalityCode": "179",
        "municipalityName": "Sodražica",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.75754,
          14.61792
        ]
      },
      {
        "id": "borelioza-39",
        "municipalityCode": "39",
        "municipalityName": "Ivančna Gorica",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.91626,
          14.81224
        ]
      },
      {
        "id": "borelioza-174",
        "municipalityCode": "174",
        "municipalityName": "Prebold",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.21776,
          15.08967
        ]
      },
      {
        "id": "borelioza-129",
        "municipalityCode": "129",
        "municipalityName": "Trbovlje",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.14127,
          15.04993
        ]
      },
      {
        "id": "borelioza-20",
        "municipalityCode": "20",
        "municipalityName": "Dobrepolje",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.82204,
          14.7357
        ]
      },
      {
        "id": "borelioza-81",
        "municipalityCode": "81",
        "municipalityName": "Muta",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.62747,
          15.13492
        ]
      },
      {
        "id": "borelioza-130",
        "municipalityCode": "130",
        "municipalityName": "Trebnje",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.90602,
          14.97386
        ]
      },
      {
        "id": "borelioza-151",
        "municipalityCode": "151",
        "municipalityName": "Braslovče",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.28234,
          15.02559
        ]
      },
      {
        "id": "borelioza-23",
        "municipalityCode": "23",
        "municipalityName": "Domžale",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.14511,
          14.62703
        ]
      },
      {
        "id": "borelioza-164",
        "municipalityCode": "164",
        "municipalityName": "Komenda",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.20302,
          14.5415
        ]
      },
      {
        "id": "borelioza-77",
        "municipalityCode": "77",
        "municipalityName": "Moravče",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13447,
          14.75762
        ]
      },
      {
        "id": "borelioza-184",
        "municipalityCode": "184",
        "municipalityName": "Tabor",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.22062,
          15.00921
        ]
      },
      {
        "id": "borelioza-170",
        "municipalityCode": "170",
        "municipalityName": "Mirna Peč",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.85457,
          15.08205
        ]
      },
      {
        "id": "borelioza-199",
        "municipalityCode": "199",
        "municipalityName": "Mokronog-Trebelno",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.91521,
          15.15748
        ]
      },
      {
        "id": "borelioza-200",
        "municipalityCode": "200",
        "municipalityName": "Poljčane",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.30512,
          15.59497
        ]
      },
      {
        "id": "borelioza-125",
        "municipalityCode": "125",
        "municipalityName": "Šmartno ob Paki",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.34032,
          15.0306
        ]
      },
      {
        "id": "borelioza-85",
        "municipalityCode": "85",
        "municipalityName": "Novo mesto",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.78078,
          15.19382
        ]
      },
      {
        "id": "borelioza-110",
        "municipalityCode": "110",
        "municipalityName": "Sevnica",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.01018,
          15.26888
        ]
      },
      {
        "id": "borelioza-127",
        "municipalityCode": "127",
        "municipalityName": "Štore",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.19848,
          15.32283
        ]
      },
      {
        "id": "borelioza-94",
        "municipalityCode": "94",
        "municipalityName": "Postojna",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.78953,
          14.16987
        ]
      },
      {
        "id": "borelioza-142",
        "municipalityCode": "142",
        "municipalityName": "Zagorje ob Savi",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13378,
          14.95157
        ]
      },
      {
        "id": "borelioza-13",
        "municipalityCode": "13",
        "municipalityName": "Cerknica",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.80483,
          14.37801
        ]
      },
      {
        "id": "borelioza-64",
        "municipalityCode": "64",
        "municipalityName": "Logatec",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          45.92882,
          14.19281
        ]
      },
      {
        "id": "borelioza-21",
        "municipalityCode": "21",
        "municipalityName": "Dobrova-Polhov Gradec",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.06175,
          14.31135
        ]
      },
      {
        "id": "borelioza-99",
        "municipalityCode": "99",
        "municipalityName": "Radeče",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.05979,
          15.14419
        ]
      },
      {
        "id": "borelioza-74",
        "municipalityCode": "74",
        "municipalityName": "Mežica",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.51874,
          14.85754
        ]
      },
      {
        "id": "borelioza-34",
        "municipalityCode": "34",
        "municipalityName": "Hrastnik",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13132,
          15.11872
        ]
      },
      {
        "id": "borelioza-57",
        "municipalityCode": "57",
        "municipalityName": "Laško",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.13266,
          15.25792
        ]
      },
      {
        "id": "borelioza-171",
        "municipalityCode": "171",
        "municipalityName": "Oplotnica",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.38567,
          15.44889
        ]
      },
      {
        "id": "borelioza-178",
        "municipalityCode": "178",
        "municipalityName": "Selnica ob Dravi",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.58634,
          15.48333
        ]
      },
      {
        "id": "borelioza-68",
        "municipalityCode": "68",
        "municipalityName": "Lukovica",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.17964,
          14.76749
        ]
      },
      {
        "id": "borelioza-133",
        "municipalityCode": "133",
        "municipalityName": "Velenje",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.369,
          15.13266
        ]
      },
      {
        "id": "borelioza-122",
        "municipalityCode": "122",
        "municipalityName": "Škofja Loka",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.1612,
          14.27624
        ]
      },
      {
        "id": "borelioza-189",
        "municipalityCode": "189",
        "municipalityName": "Vransko",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.23638,
          14.94449
        ]
      },
      {
        "id": "borelioza-147",
        "municipalityCode": "147",
        "municipalityName": "Žiri",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.04639,
          14.11536
        ]
      },
      {
        "id": "borelioza-175",
        "municipalityCode": "175",
        "municipalityName": "Prevalje",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.55244,
          14.89489
        ]
      },
      {
        "id": "borelioza-93",
        "municipalityCode": "93",
        "municipalityName": "Podvelka",
        "score": 3,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.595,
          15.3593
        ]
      },
      {
        "id": "borelioza-101",
        "municipalityCode": "101",
        "municipalityName": "Radlje ob Dravi",
        "score": 3,
        "level": "Nizko",
        "weekStart": "2025-11-24",
        "coordinates": [
          46.60371,
          15.24359
        ]
      }
    ],
    "featuredLocations": [
      {
        "municipalityName": "Kobarid",
        "level": "Srednje",
        "score": 64,
        "id": "borelioza-46"
      },
      {
        "municipalityName": "Solčava",
        "level": "Srednje",
        "score": 61,
        "id": "borelioza-180"
      },
      {
        "municipalityName": "Luče",
        "level": "Srednje",
        "score": 56,
        "id": "borelioza-67"
      },
      {
        "municipalityName": "Tolmin",
        "level": "Srednje",
        "score": 48,
        "id": "borelioza-128"
      },
      {
        "municipalityName": "Ajdovščina",
        "level": "Srednje",
        "score": 37,
        "id": "borelioza-1"
      },
      {
        "municipalityName": "Nova Gorica",
        "level": "Srednje",
        "score": 37,
        "id": "borelioza-84"
      },
      {
        "municipalityName": "Vipava",
        "level": "Srednje",
        "score": 35,
        "id": "borelioza-136"
      },
      {
        "municipalityName": "Gorje",
        "level": "Srednje",
        "score": 34,
        "id": "borelioza-207"
      }
    ]
  },
  "kme": {
    "key": "kme",
    "diseaseLabel": "KME",
    "modelId": "catboost_tick_borne_kme_env_v1",
    "legacyResearchModelId": "catboost_tick_borne_kme_presence_v2",
    "snapshotWeekStart": "2025-10-27",
    "snapshotLabel": "zadnji razpolozljivi holdout teden",
    "purpose": "Okoljski risk model za KME po lokaciji.",
    "disclaimer": "To ni epidemioloska napoved niti kalibrirana verjetnost bolezni, ampak okoljski signal za razvrstitev lokacij.",
    "scoreExplanation": "Score temelji na relativni uvrstitvi znotraj holdout napovedi in je namenjen primerjavi lokacij za okoljski risk ranking.",
    "topDrivers": [
      "mesani gozd",
      "nadmorska visina",
      "listnati gozd",
      "iglasti gozd",
      "sezonski signal"
    ],
    "thresholds": {
      "lowUpper": 0.097983,
      "mediumUpper": 0.364797
    },
    "metricSummary": "Test precision 0.17, recall 0.80, F1 0.28.",
    "locations": [
      {
        "id": "kme-61",
        "municipalityCode": "61",
        "municipalityName": "Ljubljana",
        "score": 91,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.05429,
          14.56291
        ]
      },
      {
        "id": "kme-70",
        "municipalityCode": "70",
        "municipalityName": "Maribor",
        "score": 84,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56345,
          15.62729
        ]
      },
      {
        "id": "kme-64",
        "municipalityCode": "64",
        "municipalityName": "Logatec",
        "score": 83,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.92882,
          14.19281
        ]
      },
      {
        "id": "kme-122",
        "municipalityCode": "122",
        "municipalityName": "Škofja Loka",
        "score": 82,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.1612,
          14.27624
        ]
      },
      {
        "id": "kme-27",
        "municipalityCode": "27",
        "municipalityName": "Gorenja vas-Poljane",
        "score": 81,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.11481,
          14.13589
        ]
      },
      {
        "id": "kme-94",
        "municipalityCode": "94",
        "municipalityName": "Postojna",
        "score": 81,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.78953,
          14.16987
        ]
      },
      {
        "id": "kme-71",
        "municipalityCode": "71",
        "municipalityName": "Medvode",
        "score": 78,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13101,
          14.40044
        ]
      },
      {
        "id": "kme-43",
        "municipalityCode": "43",
        "municipalityName": "Kamnik",
        "score": 78,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.25706,
          14.67696
        ]
      },
      {
        "id": "kme-52",
        "municipalityCode": "52",
        "municipalityName": "Kranj",
        "score": 78,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.25499,
          14.33409
        ]
      },
      {
        "id": "kme-140",
        "municipalityCode": "140",
        "municipalityName": "Vrhnika",
        "score": 74,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.95918,
          14.29482
        ]
      },
      {
        "id": "kme-123",
        "municipalityCode": "123",
        "municipalityName": "Škofljica",
        "score": 74,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.96578,
          14.57359
        ]
      },
      {
        "id": "kme-65",
        "municipalityCode": "65",
        "municipalityName": "Loška dolina",
        "score": 72,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.66842,
          14.48358
        ]
      },
      {
        "id": "kme-21",
        "municipalityCode": "21",
        "municipalityName": "Dobrova-Polhov Gradec",
        "score": 72,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.06175,
          14.31135
        ]
      },
      {
        "id": "kme-91",
        "municipalityCode": "91",
        "municipalityName": "Pivka",
        "score": 72,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.68166,
          14.23565
        ]
      },
      {
        "id": "kme-32",
        "municipalityCode": "32",
        "municipalityName": "Grosuplje",
        "score": 72,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.93954,
          14.66942
        ]
      },
      {
        "id": "kme-190",
        "municipalityCode": "190",
        "municipalityName": "Žalec",
        "score": 71,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.25909,
          15.16567
        ]
      },
      {
        "id": "kme-104",
        "municipalityCode": "104",
        "municipalityName": "Ribnica",
        "score": 70,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.73272,
          14.718
        ]
      },
      {
        "id": "kme-113",
        "municipalityCode": "113",
        "municipalityName": "Slovenska Bistrica",
        "score": 70,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.41402,
          15.53371
        ]
      },
      {
        "id": "kme-13",
        "municipalityCode": "13",
        "municipalityName": "Cerknica",
        "score": 70,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.80483,
          14.37801
        ]
      },
      {
        "id": "kme-1",
        "municipalityCode": "1",
        "municipalityName": "Ajdovščina",
        "score": 68,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.89933,
          13.90766
        ]
      },
      {
        "id": "kme-36",
        "municipalityCode": "36",
        "municipalityName": "Idrija",
        "score": 68,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.98907,
          14.00447
        ]
      },
      {
        "id": "kme-112",
        "municipalityCode": "112",
        "municipalityName": "Slovenj Gradec",
        "score": 68,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.48941,
          15.07872
        ]
      },
      {
        "id": "kme-146",
        "municipalityCode": "146",
        "municipalityName": "Železniki",
        "score": 67,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.21874,
          14.11034
        ]
      },
      {
        "id": "kme-68",
        "municipalityCode": "68",
        "municipalityName": "Lukovica",
        "score": 67,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.17964,
          14.76749
        ]
      },
      {
        "id": "kme-67",
        "municipalityCode": "67",
        "municipalityName": "Luče",
        "score": 67,
        "level": "Visoko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.35567,
          14.72738
        ]
      },
      {
        "id": "kme-48",
        "municipalityCode": "48",
        "municipalityName": "Kočevje",
        "score": 66,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.6184,
          14.90291
        ]
      },
      {
        "id": "kme-147",
        "municipalityCode": "147",
        "municipalityName": "Žiri",
        "score": 65,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.04639,
          14.11536
        ]
      },
      {
        "id": "kme-136",
        "municipalityCode": "136",
        "municipalityName": "Vipava",
        "score": 65,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.82188,
          13.98485
        ]
      },
      {
        "id": "kme-142",
        "municipalityCode": "142",
        "municipalityName": "Zagorje ob Savi",
        "score": 64,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13378,
          14.95157
        ]
      },
      {
        "id": "kme-102",
        "municipalityCode": "102",
        "municipalityName": "Radovljica",
        "score": 64,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.33794,
          14.20237
        ]
      },
      {
        "id": "kme-150",
        "municipalityCode": "150",
        "municipalityName": "Bloke",
        "score": 63,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.78389,
          14.51028
        ]
      },
      {
        "id": "kme-84",
        "municipalityCode": "84",
        "municipalityName": "Nova Gorica",
        "score": 63,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.98051,
          13.74061
        ]
      },
      {
        "id": "kme-8",
        "municipalityCode": "8",
        "municipalityName": "Brezovica",
        "score": 63,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.94839,
          14.42447
        ]
      },
      {
        "id": "kme-129",
        "municipalityCode": "129",
        "municipalityName": "Trbovlje",
        "score": 62,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.14127,
          15.04993
        ]
      },
      {
        "id": "kme-37",
        "municipalityCode": "37",
        "municipalityName": "Ig",
        "score": 62,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.93321,
          14.51632
        ]
      },
      {
        "id": "kme-5",
        "municipalityCode": "5",
        "municipalityName": "Borovnica",
        "score": 62,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.91315,
          14.37827
        ]
      },
      {
        "id": "kme-131",
        "municipalityCode": "131",
        "municipalityName": "Tržič",
        "score": 62,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.38851,
          14.33075
        ]
      },
      {
        "id": "kme-4",
        "municipalityCode": "4",
        "municipalityName": "Bohinj",
        "score": 61,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.2941,
          13.91593
        ]
      },
      {
        "id": "kme-39",
        "municipalityCode": "39",
        "municipalityName": "Ivančna Gorica",
        "score": 60,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.91626,
          14.81224
        ]
      },
      {
        "id": "kme-14",
        "municipalityCode": "14",
        "municipalityName": "Cerkno",
        "score": 60,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.12469,
          13.9724
        ]
      },
      {
        "id": "kme-38",
        "municipalityCode": "38",
        "municipalityName": "Ilirska Bistrica",
        "score": 60,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.56636,
          14.28632
        ]
      },
      {
        "id": "kme-95",
        "municipalityCode": "95",
        "municipalityName": "Preddvor",
        "score": 59,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.32417,
          14.46492
        ]
      },
      {
        "id": "kme-77",
        "municipalityCode": "77",
        "municipalityName": "Moravče",
        "score": 59,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13447,
          14.75762
        ]
      },
      {
        "id": "kme-128",
        "municipalityCode": "128",
        "municipalityName": "Tolmin",
        "score": 58,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.16987,
          13.80884
        ]
      },
      {
        "id": "kme-11",
        "municipalityCode": "11",
        "municipalityName": "Celje",
        "score": 58,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.24862,
          15.26605
        ]
      },
      {
        "id": "kme-66",
        "municipalityCode": "66",
        "municipalityName": "Loški Potok",
        "score": 57,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.66375,
          14.64078
        ]
      },
      {
        "id": "kme-179",
        "municipalityCode": "179",
        "municipalityName": "Sodražica",
        "score": 56,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.75754,
          14.61792
        ]
      },
      {
        "id": "kme-76",
        "municipalityCode": "76",
        "municipalityName": "Mislinja",
        "score": 56,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.44695,
          15.21992
        ]
      },
      {
        "id": "kme-20",
        "municipalityCode": "20",
        "municipalityName": "Dobrepolje",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.82204,
          14.7357
        ]
      },
      {
        "id": "kme-178",
        "municipalityCode": "178",
        "municipalityName": "Selnica ob Dravi",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.58634,
          15.48333
        ]
      },
      {
        "id": "kme-57",
        "municipalityCode": "57",
        "municipalityName": "Laško",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13266,
          15.25792
        ]
      },
      {
        "id": "kme-134",
        "municipalityCode": "134",
        "municipalityName": "Velike Lašče",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.84313,
          14.58714
        ]
      },
      {
        "id": "kme-117",
        "municipalityCode": "117",
        "municipalityName": "Šenčur",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.23522,
          14.42605
        ]
      },
      {
        "id": "kme-3",
        "municipalityCode": "3",
        "municipalityName": "Bled",
        "score": 55,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.34565,
          14.07874
        ]
      },
      {
        "id": "kme-110",
        "municipalityCode": "110",
        "municipalityName": "Sevnica",
        "score": 53,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.01018,
          15.26888
        ]
      },
      {
        "id": "kme-169",
        "municipalityCode": "169",
        "municipalityName": "Miklavž na Dravskem polju",
        "score": 53,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.48871,
          15.70724
        ]
      },
      {
        "id": "kme-12",
        "municipalityCode": "12",
        "municipalityName": "Cerklje na Gorenjskem",
        "score": 53,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.25284,
          14.50003
        ]
      },
      {
        "id": "kme-25",
        "municipalityCode": "25",
        "municipalityName": "Dravograd",
        "score": 53,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.59749,
          15.03387
        ]
      },
      {
        "id": "kme-137",
        "municipalityCode": "137",
        "municipalityName": "Vitanje",
        "score": 52,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.4023,
          15.29348
        ]
      },
      {
        "id": "kme-63",
        "municipalityCode": "63",
        "municipalityName": "Ljutomer",
        "score": 52,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52108,
          16.157
        ]
      },
      {
        "id": "kme-60",
        "municipalityCode": "60",
        "municipalityName": "Litija",
        "score": 52,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.05632,
          14.91962
        ]
      },
      {
        "id": "kme-194",
        "municipalityCode": "194",
        "municipalityName": "Šmartno pri Litiji",
        "score": 52,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.02285,
          14.84481
        ]
      },
      {
        "id": "kme-23",
        "municipalityCode": "23",
        "municipalityName": "Domžale",
        "score": 52,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.14511,
          14.62703
        ]
      },
      {
        "id": "kme-144",
        "municipalityCode": "144",
        "municipalityName": "Zreče",
        "score": 51,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.40013,
          15.36645
        ]
      },
      {
        "id": "kme-103",
        "municipalityCode": "103",
        "municipalityName": "Ravne na Koroškem",
        "score": 51,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.54582,
          14.96111
        ]
      },
      {
        "id": "kme-175",
        "municipalityCode": "175",
        "municipalityName": "Prevalje",
        "score": 50,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.55244,
          14.89489
        ]
      },
      {
        "id": "kme-126",
        "municipalityCode": "126",
        "municipalityName": "Šoštanj",
        "score": 50,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.40613,
          15.00495
        ]
      },
      {
        "id": "kme-133",
        "municipalityCode": "133",
        "municipalityName": "Velenje",
        "score": 50,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.369,
          15.13266
        ]
      },
      {
        "id": "kme-41",
        "municipalityCode": "41",
        "municipalityName": "Jesenice",
        "score": 50,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.44923,
          14.0721
        ]
      },
      {
        "id": "kme-72",
        "municipalityCode": "72",
        "municipalityName": "Mengeš",
        "score": 50,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.15963,
          14.55761
        ]
      },
      {
        "id": "kme-98",
        "municipalityCode": "98",
        "municipalityName": "Rače-Fram",
        "score": 48,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.44877,
          15.64562
        ]
      },
      {
        "id": "kme-174",
        "municipalityCode": "174",
        "municipalityName": "Prebold",
        "score": 48,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.21776,
          15.08967
        ]
      },
      {
        "id": "kme-81",
        "municipalityCode": "81",
        "municipalityName": "Muta",
        "score": 48,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.62747,
          15.13492
        ]
      },
      {
        "id": "kme-138",
        "municipalityCode": "138",
        "municipalityName": "Vodice",
        "score": 47,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.17118,
          14.49313
        ]
      },
      {
        "id": "kme-209",
        "municipalityCode": "209",
        "municipalityName": "Rečica ob Savinji",
        "score": 47,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.32806,
          14.90312
        ]
      },
      {
        "id": "kme-159",
        "municipalityCode": "159",
        "municipalityName": "Hajdina",
        "score": 46,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.42017,
          15.82577
        ]
      },
      {
        "id": "kme-168",
        "municipalityCode": "168",
        "municipalityName": "Markovci",
        "score": 46,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.39064,
          15.9488
        ]
      },
      {
        "id": "kme-114",
        "municipalityCode": "114",
        "municipalityName": "Slovenske Konjice",
        "score": 45,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.32267,
          15.46121
        ]
      },
      {
        "id": "kme-160",
        "municipalityCode": "160",
        "municipalityName": "Hoče-Slivnica",
        "score": 45,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.49112,
          15.62712
        ]
      },
      {
        "id": "kme-184",
        "municipalityCode": "184",
        "municipalityName": "Tabor",
        "score": 44,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.22062,
          15.00921
        ]
      },
      {
        "id": "kme-100",
        "municipalityCode": "100",
        "municipalityName": "Radenci",
        "score": 44,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.62,
          16.04424
        ]
      },
      {
        "id": "kme-93",
        "municipalityCode": "93",
        "municipalityName": "Podvelka",
        "score": 44,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.595,
          15.3593
        ]
      },
      {
        "id": "kme-139",
        "municipalityCode": "139",
        "municipalityName": "Vojnik",
        "score": 43,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.31835,
          15.30826
        ]
      },
      {
        "id": "kme-80",
        "municipalityCode": "80",
        "municipalityName": "Murska Sobota",
        "score": 43,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.64843,
          16.15475
        ]
      },
      {
        "id": "kme-130",
        "municipalityCode": "130",
        "municipalityName": "Trebnje",
        "score": 43,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.90602,
          14.97386
        ]
      },
      {
        "id": "kme-171",
        "municipalityCode": "171",
        "municipalityName": "Oplotnica",
        "score": 43,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.38567,
          15.44889
        ]
      },
      {
        "id": "kme-120",
        "municipalityCode": "120",
        "municipalityName": "Šentjur",
        "score": 42,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.1897,
          15.42415
        ]
      },
      {
        "id": "kme-166",
        "municipalityCode": "166",
        "municipalityName": "Križevci",
        "score": 42,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56403,
          16.11797
        ]
      },
      {
        "id": "kme-167",
        "municipalityCode": "167",
        "municipalityName": "Lovrenc na Pohorju",
        "score": 42,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52589,
          15.38364
        ]
      },
      {
        "id": "kme-162",
        "municipalityCode": "162",
        "municipalityName": "Horjul",
        "score": 40,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.02255,
          14.28673
        ]
      },
      {
        "id": "kme-101",
        "municipalityCode": "101",
        "municipalityName": "Radlje ob Dravi",
        "score": 40,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.60371,
          15.24359
        ]
      },
      {
        "id": "kme-199",
        "municipalityCode": "199",
        "municipalityName": "Mokronog-Trebelno",
        "score": 39,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.91521,
          15.15748
        ]
      },
      {
        "id": "kme-79",
        "municipalityCode": "79",
        "municipalityName": "Mozirje",
        "score": 37,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.3605,
          14.95542
        ]
      },
      {
        "id": "kme-151",
        "municipalityCode": "151",
        "municipalityName": "Braslovče",
        "score": 37,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.28234,
          15.02559
        ]
      },
      {
        "id": "kme-83",
        "municipalityCode": "83",
        "municipalityName": "Nazarje",
        "score": 36,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.28266,
          14.91303
        ]
      },
      {
        "id": "kme-17",
        "municipalityCode": "17",
        "municipalityName": "Črnomelj",
        "score": 36,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.52105,
          15.19651
        ]
      },
      {
        "id": "kme-74",
        "municipalityCode": "74",
        "municipalityName": "Mežica",
        "score": 35,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.51874,
          14.85754
        ]
      },
      {
        "id": "kme-85",
        "municipalityCode": "85",
        "municipalityName": "Novo mesto",
        "score": 35,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.78078,
          15.19382
        ]
      },
      {
        "id": "kme-195",
        "municipalityCode": "195",
        "municipalityName": "Apače",
        "score": 35,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.69301,
          15.87349
        ]
      },
      {
        "id": "kme-40",
        "municipalityCode": "40",
        "municipalityName": "Izola",
        "score": 34,
        "level": "Srednje",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.51344,
          13.65846
        ]
      },
      {
        "id": "kme-115",
        "municipalityCode": "115",
        "municipalityName": "Starše",
        "score": 33,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.45792,
          15.75539
        ]
      },
      {
        "id": "kme-127",
        "municipalityCode": "127",
        "municipalityName": "Štore",
        "score": 33,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.19848,
          15.32283
        ]
      },
      {
        "id": "kme-87",
        "municipalityCode": "87",
        "municipalityName": "Ormož",
        "score": 33,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.43767,
          16.15146
        ]
      },
      {
        "id": "kme-181",
        "municipalityCode": "181",
        "municipalityName": "Sveta Ana",
        "score": 33,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.65241,
          15.83617
        ]
      },
      {
        "id": "kme-189",
        "municipalityCode": "189",
        "municipalityName": "Vransko",
        "score": 32,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.23638,
          14.94449
        ]
      },
      {
        "id": "kme-6",
        "municipalityCode": "6",
        "municipalityName": "Bovec",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.35558,
          13.62372
        ]
      },
      {
        "id": "kme-55",
        "municipalityCode": "55",
        "municipalityName": "Kungota",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.64536,
          15.6012
        ]
      },
      {
        "id": "kme-96",
        "municipalityCode": "96",
        "municipalityName": "Ptuj",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.4419,
          15.87417
        ]
      },
      {
        "id": "kme-88",
        "municipalityCode": "88",
        "municipalityName": "Osilnica",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.54726,
          14.732
        ]
      },
      {
        "id": "kme-108",
        "municipalityCode": "108",
        "municipalityName": "Ruše",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.51658,
          15.48714
        ]
      },
      {
        "id": "kme-22",
        "municipalityCode": "22",
        "municipalityName": "Dol pri Ljubljani",
        "score": 31,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.09396,
          14.67296
        ]
      },
      {
        "id": "kme-10",
        "municipalityCode": "10",
        "municipalityName": "Tišina",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.66104,
          16.07849
        ]
      },
      {
        "id": "kme-29",
        "municipalityCode": "29",
        "municipalityName": "Gornja Radgona",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.63609,
          15.96145
        ]
      },
      {
        "id": "kme-124",
        "municipalityCode": "124",
        "municipalityName": "Šmarje pri Jelšah",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.21493,
          15.51993
        ]
      },
      {
        "id": "kme-50",
        "municipalityCode": "50",
        "municipalityName": "Koper",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.50969,
          13.83812
        ]
      },
      {
        "id": "kme-58",
        "municipalityCode": "58",
        "municipalityName": "Lenart",
        "score": 30,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.55778,
          15.81873
        ]
      },
      {
        "id": "kme-157",
        "municipalityCode": "157",
        "municipalityName": "Dolenjske Toplice",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.72435,
          15.03304
        ]
      },
      {
        "id": "kme-210",
        "municipalityCode": "210",
        "municipalityName": "Sveti Jurij v Slovenskih goricah",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.61282,
          15.78816
        ]
      },
      {
        "id": "kme-99",
        "municipalityCode": "99",
        "municipalityName": "Radeče",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.05979,
          15.14419
        ]
      },
      {
        "id": "kme-28",
        "municipalityCode": "28",
        "municipalityName": "Gorišnica",
        "score": 29,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.40602,
          16.01072
        ]
      },
      {
        "id": "kme-26",
        "municipalityCode": "26",
        "municipalityName": "Duplek",
        "score": 28,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.51166,
          15.7664
        ]
      },
      {
        "id": "kme-30",
        "municipalityCode": "30",
        "municipalityName": "Gornji Grad",
        "score": 27,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.28805,
          14.78828
        ]
      },
      {
        "id": "kme-73",
        "municipalityCode": "73",
        "municipalityName": "Metlika",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.6562,
          15.29667
        ]
      },
      {
        "id": "kme-164",
        "municipalityCode": "164",
        "municipalityName": "Komenda",
        "score": 26,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.20302,
          14.5415
        ]
      },
      {
        "id": "kme-192",
        "municipalityCode": "192",
        "municipalityName": "Žirovnica",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.41067,
          14.16884
        ]
      },
      {
        "id": "kme-141",
        "municipalityCode": "141",
        "municipalityName": "Vuzenica",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56839,
          15.15986
        ]
      },
      {
        "id": "kme-45",
        "municipalityCode": "45",
        "municipalityName": "Kidričevo",
        "score": 25,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.39512,
          15.74984
        ]
      },
      {
        "id": "kme-200",
        "municipalityCode": "200",
        "municipalityName": "Poljčane",
        "score": 24,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.30512,
          15.59497
        ]
      },
      {
        "id": "kme-148",
        "municipalityCode": "148",
        "municipalityName": "Benedikt",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.61731,
          15.89098
        ]
      },
      {
        "id": "kme-59",
        "municipalityCode": "59",
        "municipalityName": "Lendava",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.55683,
          16.44489
        ]
      },
      {
        "id": "kme-186",
        "municipalityCode": "186",
        "municipalityName": "Trzin",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.12788,
          14.55234
        ]
      },
      {
        "id": "kme-177",
        "municipalityCode": "177",
        "municipalityName": "Ribnica na Pohorju",
        "score": 23,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52398,
          15.26008
        ]
      },
      {
        "id": "kme-207",
        "municipalityCode": "207",
        "municipalityName": "Gorje",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.39027,
          13.98265
        ]
      },
      {
        "id": "kme-15",
        "municipalityCode": "15",
        "municipalityName": "Črenšovci",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.55589,
          16.2957
        ]
      },
      {
        "id": "kme-121",
        "municipalityCode": "121",
        "municipalityName": "Škocjan",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.9167,
          15.29834
        ]
      },
      {
        "id": "kme-119",
        "municipalityCode": "119",
        "municipalityName": "Šentjernej",
        "score": 22,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.82652,
          15.33251
        ]
      },
      {
        "id": "kme-170",
        "municipalityCode": "170",
        "municipalityName": "Mirna Peč",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.85457,
          15.08205
        ]
      },
      {
        "id": "kme-16",
        "municipalityCode": "16",
        "municipalityName": "Črna na Koroškem",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.46341,
          14.82871
        ]
      },
      {
        "id": "kme-205",
        "municipalityCode": "205",
        "municipalityName": "Sveti Tomaž",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.47974,
          16.06681
        ]
      },
      {
        "id": "kme-211",
        "municipalityCode": "211",
        "municipalityName": "Šentrupert",
        "score": 21,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.98427,
          15.0896
        ]
      },
      {
        "id": "kme-202",
        "municipalityCode": "202",
        "municipalityName": "Središče ob Dravi",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.40261,
          16.25511
        ]
      },
      {
        "id": "kme-92",
        "municipalityCode": "92",
        "municipalityName": "Podčetrtek",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.14332,
          15.58578
        ]
      },
      {
        "id": "kme-180",
        "municipalityCode": "180",
        "municipalityName": "Solčava",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.40504,
          14.65815
        ]
      },
      {
        "id": "kme-153",
        "municipalityCode": "153",
        "municipalityName": "Cerkvenjak",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56097,
          15.94254
        ]
      },
      {
        "id": "kme-116",
        "municipalityCode": "116",
        "municipalityName": "Sveti Jurij ob Ščavnici",
        "score": 20,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56482,
          16.02455
        ]
      },
      {
        "id": "kme-118",
        "municipalityCode": "118",
        "municipalityName": "Šentilj",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.67584,
          15.71605
        ]
      },
      {
        "id": "kme-53",
        "municipalityCode": "53",
        "municipalityName": "Kranjska Gora",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.46049,
          13.84612
        ]
      },
      {
        "id": "kme-2",
        "municipalityCode": "2",
        "municipalityName": "Beltinci",
        "score": 19,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.608,
          16.23173
        ]
      },
      {
        "id": "kme-105",
        "municipalityCode": "105",
        "municipalityName": "Rogašovci",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.79958,
          16.02603
        ]
      },
      {
        "id": "kme-34",
        "municipalityCode": "34",
        "municipalityName": "Hrastnik",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13132,
          15.11872
        ]
      },
      {
        "id": "kme-125",
        "municipalityCode": "125",
        "municipalityName": "Šmartno ob Paki",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.34032,
          15.0306
        ]
      },
      {
        "id": "kme-154",
        "municipalityCode": "154",
        "municipalityName": "Dobje",
        "score": 18,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.13254,
          15.39711
        ]
      },
      {
        "id": "kme-42",
        "municipalityCode": "42",
        "municipalityName": "Juršinci",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.48558,
          15.97302
        ]
      },
      {
        "id": "kme-89",
        "municipalityCode": "89",
        "municipalityName": "Pesnica",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.61962,
          15.70986
        ]
      },
      {
        "id": "kme-31",
        "municipalityCode": "31",
        "municipalityName": "Gornji Petrovci",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.80727,
          16.20514
        ]
      },
      {
        "id": "kme-163",
        "municipalityCode": "163",
        "municipalityName": "Jezersko",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.38704,
          14.48286
        ]
      },
      {
        "id": "kme-204",
        "municipalityCode": "204",
        "municipalityName": "Sveta Trojica v Slovenskih goricah",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.56983,
          15.88619
        ]
      },
      {
        "id": "kme-9",
        "municipalityCode": "9",
        "municipalityName": "Brežice",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.93154,
          15.62089
        ]
      },
      {
        "id": "kme-165",
        "municipalityCode": "165",
        "municipalityName": "Kostel",
        "score": 17,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.49901,
          14.86189
        ]
      },
      {
        "id": "kme-111",
        "municipalityCode": "111",
        "municipalityName": "Sežana",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.73622,
          13.88163
        ]
      },
      {
        "id": "kme-109",
        "municipalityCode": "109",
        "municipalityName": "Semič",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.65166,
          15.14432
        ]
      },
      {
        "id": "kme-183",
        "municipalityCode": "183",
        "municipalityName": "Šempeter-Vrtojba",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.91542,
          13.64676
        ]
      },
      {
        "id": "kme-62",
        "municipalityCode": "62",
        "municipalityName": "Ljubno",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.37043,
          14.84401
        ]
      },
      {
        "id": "kme-82",
        "municipalityCode": "82",
        "municipalityName": "Naklo",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.29165,
          14.29642
        ]
      },
      {
        "id": "kme-173",
        "municipalityCode": "173",
        "municipalityName": "Polzela",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.30303,
          15.08507
        ]
      },
      {
        "id": "kme-212",
        "municipalityCode": "212",
        "municipalityName": "Mirna",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.94518,
          15.05695
        ]
      },
      {
        "id": "kme-206",
        "municipalityCode": "206",
        "municipalityName": "Šmarješke Toplice",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.88414,
          15.24347
        ]
      },
      {
        "id": "kme-152",
        "municipalityCode": "152",
        "municipalityName": "Cankova",
        "score": 16,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.73564,
          16.02503
        ]
      },
      {
        "id": "kme-19",
        "municipalityCode": "19",
        "municipalityName": "Divača",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.68619,
          14.02557
        ]
      },
      {
        "id": "kme-106",
        "municipalityCode": "106",
        "municipalityName": "Rogaška Slatina",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.24785,
          15.62844
        ]
      },
      {
        "id": "kme-143",
        "municipalityCode": "143",
        "municipalityName": "Zavrč",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.36155,
          16.0461
        ]
      },
      {
        "id": "kme-69",
        "municipalityCode": "69",
        "municipalityName": "Majšperk",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.32442,
          15.7395
        ]
      },
      {
        "id": "kme-208",
        "municipalityCode": "208",
        "municipalityName": "Log-Dragomer",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.01438,
          14.37329
        ]
      },
      {
        "id": "kme-135",
        "municipalityCode": "135",
        "municipalityName": "Videm",
        "score": 15,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.347,
          15.8929
        ]
      },
      {
        "id": "kme-35",
        "municipalityCode": "35",
        "municipalityName": "Hrpelje-Kozina",
        "score": 14,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.5695,
          14.00871
        ]
      },
      {
        "id": "kme-97",
        "municipalityCode": "97",
        "municipalityName": "Puconci",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.74449,
          16.13383
        ]
      },
      {
        "id": "kme-132",
        "municipalityCode": "132",
        "municipalityName": "Turnišče",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.61608,
          16.31347
        ]
      },
      {
        "id": "kme-24",
        "municipalityCode": "24",
        "municipalityName": "Dornava",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.44888,
          15.99036
        ]
      },
      {
        "id": "kme-187",
        "municipalityCode": "187",
        "municipalityName": "Velika Polana",
        "score": 13,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.57878,
          16.35359
        ]
      },
      {
        "id": "kme-196",
        "municipalityCode": "196",
        "municipalityName": "Cirkulane",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.34166,
          15.99535
        ]
      },
      {
        "id": "kme-49",
        "municipalityCode": "49",
        "municipalityName": "Komen",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.81496,
          13.75433
        ]
      },
      {
        "id": "kme-188",
        "municipalityCode": "188",
        "municipalityName": "Veržej",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.58257,
          16.16407
        ]
      },
      {
        "id": "kme-33",
        "municipalityCode": "33",
        "municipalityName": "Šalovci",
        "score": 12,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.83331,
          16.26175
        ]
      },
      {
        "id": "kme-75",
        "municipalityCode": "75",
        "municipalityName": "Miren-Kostanjevica",
        "score": 11,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.85219,
          13.6381
        ]
      },
      {
        "id": "kme-176",
        "municipalityCode": "176",
        "municipalityName": "Razkrižje",
        "score": 11,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52047,
          16.27405
        ]
      },
      {
        "id": "kme-185",
        "municipalityCode": "185",
        "municipalityName": "Trnovska vas",
        "score": 10,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52278,
          15.88848
        ]
      },
      {
        "id": "kme-155",
        "municipalityCode": "155",
        "municipalityName": "Dobrna",
        "score": 9,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.3563,
          15.22364
        ]
      },
      {
        "id": "kme-54",
        "municipalityCode": "54",
        "municipalityName": "Krško",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.95595,
          15.46302
        ]
      },
      {
        "id": "kme-203",
        "municipalityCode": "203",
        "municipalityName": "Straža",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.77723,
          15.09133
        ]
      },
      {
        "id": "kme-56",
        "municipalityCode": "56",
        "municipalityName": "Kuzma",
        "score": 8,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.84048,
          16.0948
        ]
      },
      {
        "id": "kme-18",
        "municipalityCode": "18",
        "municipalityName": "Destrnik",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.48342,
          15.88047
        ]
      },
      {
        "id": "kme-86",
        "municipalityCode": "86",
        "municipalityName": "Odranci",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.58602,
          16.27128
        ]
      },
      {
        "id": "kme-182",
        "municipalityCode": "182",
        "municipalityName": "Sveti Andraž v Slov. goricah",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.52299,
          15.95229
        ]
      },
      {
        "id": "kme-156",
        "municipalityCode": "156",
        "municipalityName": "Dobrovnik",
        "score": 7,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.65096,
          16.34693
        ]
      },
      {
        "id": "kme-149",
        "municipalityCode": "149",
        "municipalityName": "Bistrica ob Sotli",
        "score": 6,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.05861,
          15.64685
        ]
      },
      {
        "id": "kme-201",
        "municipalityCode": "201",
        "municipalityName": "Renče-Vogrsko",
        "score": 6,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.89106,
          13.67991
        ]
      },
      {
        "id": "kme-193",
        "municipalityCode": "193",
        "municipalityName": "Žužemberk",
        "score": 6,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.80801,
          14.93106
        ]
      },
      {
        "id": "kme-78",
        "municipalityCode": "78",
        "municipalityName": "Moravske Toplice",
        "score": 6,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.70934,
          16.2702
        ]
      },
      {
        "id": "kme-172",
        "municipalityCode": "172",
        "municipalityName": "Podlehnik",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.31623,
          15.86533
        ]
      },
      {
        "id": "kme-191",
        "municipalityCode": "191",
        "municipalityName": "Žetale",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.28253,
          15.8008
        ]
      },
      {
        "id": "kme-198",
        "municipalityCode": "198",
        "municipalityName": "Makole",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.31578,
          15.67488
        ]
      },
      {
        "id": "kme-161",
        "municipalityCode": "161",
        "municipalityName": "Hodoš",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.82809,
          16.32072
        ]
      },
      {
        "id": "kme-46",
        "municipalityCode": "46",
        "municipalityName": "Kobarid",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.25158,
          13.55544
        ]
      },
      {
        "id": "kme-158",
        "municipalityCode": "158",
        "municipalityName": "Grad",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.79435,
          16.09494
        ]
      },
      {
        "id": "kme-7",
        "municipalityCode": "7",
        "municipalityName": "Brda",
        "score": 5,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.0125,
          13.54538
        ]
      },
      {
        "id": "kme-197",
        "municipalityCode": "197",
        "municipalityName": "Kostanjevica na Krki",
        "score": 4,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.83755,
          15.42073
        ]
      },
      {
        "id": "kme-90",
        "municipalityCode": "90",
        "municipalityName": "Piran",
        "score": 4,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.48784,
          13.63438
        ]
      },
      {
        "id": "kme-51",
        "municipalityCode": "51",
        "municipalityName": "Kozje",
        "score": 4,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.0719,
          15.54951
        ]
      },
      {
        "id": "kme-44",
        "municipalityCode": "44",
        "municipalityName": "Kanal",
        "score": 4,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.0837,
          13.6523
        ]
      },
      {
        "id": "kme-213",
        "municipalityCode": "213",
        "municipalityName": "Ankaran",
        "score": 4,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          45.57539,
          13.74243
        ]
      },
      {
        "id": "kme-107",
        "municipalityCode": "107",
        "municipalityName": "Rogatec",
        "score": 3,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.23858,
          15.74206
        ]
      },
      {
        "id": "kme-47",
        "municipalityCode": "47",
        "municipalityName": "Kobilje",
        "score": 2,
        "level": "Nizko",
        "weekStart": "2025-10-27",
        "coordinates": [
          46.68087,
          16.39098
        ]
      }
    ],
    "featuredLocations": [
      {
        "municipalityName": "Ljubljana",
        "level": "Visoko",
        "score": 91,
        "id": "kme-61"
      },
      {
        "municipalityName": "Maribor",
        "level": "Visoko",
        "score": 84,
        "id": "kme-70"
      },
      {
        "municipalityName": "Logatec",
        "level": "Visoko",
        "score": 83,
        "id": "kme-64"
      },
      {
        "municipalityName": "Škofja Loka",
        "level": "Visoko",
        "score": 82,
        "id": "kme-122"
      },
      {
        "municipalityName": "Gorenja vas-Poljane",
        "level": "Visoko",
        "score": 81,
        "id": "kme-27"
      },
      {
        "municipalityName": "Postojna",
        "level": "Visoko",
        "score": 81,
        "id": "kme-94"
      },
      {
        "municipalityName": "Medvode",
        "level": "Visoko",
        "score": 78,
        "id": "kme-71"
      },
      {
        "municipalityName": "Kamnik",
        "level": "Visoko",
        "score": 78,
        "id": "kme-43"
      }
    ]
  }
}
