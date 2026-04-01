export type RegionRisk = {
  id: string
  name: string
  score: number
  level: 'Nizko' | 'Srednje' | 'Visoko'
  trend: string
  summary: string
  factors: string[]
  recommendation: string
  coordinates: [number, number]
}

export const regions: RegionRisk[] = [
  {
    id: 'gorenjska',
    name: 'Gorenjska',
    score: 78,
    level: 'Visoko',
    trend: '+12 % glede na prejsnji teden',
    summary: 'Kombinacija vlage, temperature in izpostavljenosti v naravi nakazuje povisano tveganje za boreliozo ali KME.',
    factors: ['visja vlaga', 'gost gozdni rob', 'blage temperature'],
    recommendation: 'Za pohod uporabi dolga oblacila, repelent in po vrnitvi hitro preveri morebiten ugriz ter spremljaj simptome.',
    coordinates: [46.361, 14.156],
  },
  {
    id: 'ljubljana',
    name: 'Osrednjeslovenska',
    score: 56,
    level: 'Srednje',
    trend: '+4 % glede na prejsnji teden',
    summary: 'Tveganje je zmerno, vendar ostaja povisano v obmocjih s pogosto izpostavljenostjo in ugodnimi okoljskimi razmerami.',
    factors: ['mestni gozdovi', 'obcasna vlaga', 'pogosta izpostavljenost ljudi'],
    recommendation: 'Za krajse izlete uporabi repelent in po aktivnosti preveri noge, pas ter vrat zaradi zgodnjega odkritja ugriza.',
    coordinates: [46.0569, 14.5058],
  },
  {
    id: 'primorska',
    name: 'Primorska',
    score: 34,
    level: 'Nizko',
    trend: '-8 % glede na prejsnji teden',
    summary: 'Bolj suho obdobje trenutno znizuje verjetnost okoljskih pogojev, povezanih z boreliozo ali KME, tveganje pa ni nicelno.',
    factors: ['suho obdobje', 'manj vlage v tleh', 'nizja okoljska ogrozenost'],
    recommendation: 'Osnovna zascita je se vedno smiselna, posebej v sencnih in zarascenih delih ter ob daljsem zadrzevanju v naravi.',
    coordinates: [45.5469, 13.7294],
  },
]
