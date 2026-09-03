import precautionSnapshot from './precautionSnapshot.json'

export type RiskLevel = 'Nizko' | 'Srednje' | 'Visoko'

export type DiseaseModelKey = 'borelioza' | 'kme'

export type WeatherContext = {
  periodStart: string
  periodEnd: string
  airTemperatureC7dMean: number
  precipitationMm7dTotal: number
  soilTemperatureC7dMean: number
  soilMoistureM3M3_7dMean: number
  source: string
  dataStatus: 'recent_operational_model_history_not_station_observations'
  spatialMethod: 'frozen_grid_samples_weighted_by_municipality_polygon_intersections'
  usedInLymeScore: true
  usedInKmeScore: false
}

export type LiveMunicipalityRiskLocation = {
  id: string
  municipalityCode: string
  municipalityName: string
  regionCode: string
  regionName: string
  score: number
  level: RiskLevel
  trendDeltaScore: number
  trendLabel: string
  weekStart: string
  weekEnd: string
  coordinates: [number, number]
  weatherContext: WeatherContext
}

export type LiveMunicipalityRiskModel = {
  key: DiseaseModelKey
  diseaseLabel: string
  modelId: string
  asOfDate: string
  generatedAt: string
  referenceWeekStart: string
  referenceWeekEnd: string
  signalWeekStart: string
  signalWeekEnd: string
  snapshotLabel: string
  weatherSource: string
  weatherModel: 'icon_seamless'
  weatherUsedInScore: boolean
  spatialScope: 'municipality' | 'statistical_region'
  scopeLabel: string
  dataStatus: string
  methodologyNote: string
  purpose: string
  disclaimer: string
  scoreExplanation: string
  modelTarget: string
  inputWindow: string
  validationSummary: string
  limitations: string[]
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

type PrecautionSnapshot = {
  schemaVersion: 3
  generatedAt: string
  runtimeCaseInputsUsed: false
  weatherUsedInAiScores: true
  weatherUsedByDisease: {
    borelioza: true
    kme: false
  }
  weatherContext: {
    periodStart: string
    periodEnd: string
    expectedRefreshCadenceHours: 24
    maximumDisplayAgeHours: 36
  }
  models: Record<DiseaseModelKey, LiveMunicipalityRiskModel>
}

const snapshot = precautionSnapshot as unknown as PrecautionSnapshot

if (
  snapshot.schemaVersion !== 3 ||
  snapshot.runtimeCaseInputsUsed ||
  !snapshot.weatherUsedInAiScores ||
  !snapshot.weatherUsedByDisease?.borelioza ||
  snapshot.weatherUsedByDisease?.kme
) {
  throw new Error('Preventivni snapshot krši pogodbo bolezni in vremena.')
}
if (
  !Number.isFinite(Date.parse(snapshot.generatedAt)) ||
  snapshot.weatherContext?.expectedRefreshCadenceHours !== 24 ||
  snapshot.weatherContext?.maximumDisplayAgeHours !== 36
) {
  throw new Error('Preventivni snapshot krši pogodbo svežine vremenskih podatkov.')
}

export const liveMunicipalityRiskModels = snapshot.models
export const precautionSnapshotMetadata = {
  generatedAt: snapshot.generatedAt,
  weatherPeriodStart: snapshot.weatherContext.periodStart,
  weatherPeriodEnd: snapshot.weatherContext.periodEnd,
  expectedRefreshCadenceHours:
    snapshot.weatherContext.expectedRefreshCadenceHours,
  maximumDisplayAgeHours: snapshot.weatherContext.maximumDisplayAgeHours,
}
