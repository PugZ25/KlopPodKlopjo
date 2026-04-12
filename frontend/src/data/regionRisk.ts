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
    trend: '+12 % glede na prejšnji teden',
    summary:
      'Kombinacija vlage, temperature in izpostavljenosti v naravi nakazuje povišano tveganje za boreliozo ali KME.',
    factors: ['višja vlaga', 'gost gozdni rob', 'blage temperature'],
    recommendation:
      'Za pohod uporabi dolga oblačila, repelent in po vrnitvi hitro preveri morebiten ugriz ter spremljaj simptome.',
    coordinates: [46.361, 14.156],
  },
  {
    id: 'ljubljana',
    name: 'Osrednjeslovenska',
    score: 56,
    level: 'Srednje',
    trend: '+4 % glede na prejšnji teden',
    summary:
      'Tveganje je zmerno, vendar ostaja povišano v območjih s pogosto izpostavljenostjo in ugodnimi okoljskimi razmerami.',
    factors: ['mestni gozdovi', 'občasna vlaga', 'pogosta izpostavljenost ljudi'],
    recommendation:
      'Za krajše izlete uporabi repelent in po aktivnosti preveri noge, pas ter vrat zaradi zgodnjega odkritja ugriza.',
    coordinates: [46.0569, 14.5058],
  },
  {
    id: 'primorska',
    name: 'Primorska',
    score: 34,
    level: 'Nizko',
    trend: '-8 % glede na prejšnji teden',
    summary:
      'Bolj suho obdobje trenutno znižuje verjetnost okoljskih pogojev, povezanih z boreliozo ali KME, tveganje pa ni ničelno.',
    factors: ['suho obdobje', 'manj vlage v tleh', 'nižja okoljska ogroženost'],
    recommendation:
      'Osnovna zaščita je še vedno smiselna, posebej v senčnih in zaraščenih delih ter ob daljšem zadrževanju v naravi.',
    coordinates: [45.5469, 13.7294],
  },
]
