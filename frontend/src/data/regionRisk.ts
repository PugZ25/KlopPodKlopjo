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
    summary: 'Toplo vreme in vlazna tla povecujejo aktivnost klopov v gozdnih obmocjih.',
    factors: ['visja vlaga', 'gost gozdni rob', 'blage temperature'],
    recommendation: 'Za pohod uporabi dolga oblacila, repelent in pregled telesa v eni uri po vrnitvi.',
    coordinates: [46.361, 14.156],
  },
  {
    id: 'ljubljana',
    name: 'Osrednjeslovenska',
    score: 56,
    level: 'Srednje',
    trend: '+4 % glede na prejsnji teden',
    summary: 'Tveganje je zmerno, vendar ostaja povisano ob rekreativnih poteh z visoko travo.',
    factors: ['mestni gozdovi', 'obcasna vlaga', 'pogosta izpostavljenost ljudi'],
    recommendation: 'Za krajse izlete zadostuje repelent in pregled nog, pasa ter vratu po aktivnosti.',
    coordinates: [46.0569, 14.5058],
  },
  {
    id: 'primorska',
    name: 'Primorska',
    score: 34,
    level: 'Nizko',
    trend: '-8 % glede na prejsnji teden',
    summary: 'Bolj suho obdobje zmanjsuje aktivnost klopov, tveganje pa ni nicelno.',
    factors: ['suho obdobje', 'manj vlage v tleh', 'nizja aktivnost klopov'],
    recommendation: 'Osnovna zascita je se vedno smiselna, posebej v sencnih in zarascenih delih.',
    coordinates: [45.5469, 13.7294],
  },
]
