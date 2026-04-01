import { useState } from 'react'
import './App.css'

type RegionRisk = {
  id: string
  name: string
  score: number
  level: 'Nizko' | 'Srednje' | 'Visoko'
  trend: string
  summary: string
  factors: string[]
  recommendation: string
}

const regions: RegionRisk[] = [
  {
    id: 'gorenjska',
    name: 'Gorenjska',
    score: 78,
    level: 'Visoko',
    trend: '+12 % glede na prejsnji teden',
    summary: 'Toplo vreme in vlazna tla povecujejo aktivnost klopov v gozdnih obmocjih.',
    factors: ['visja vlaga', 'gost gozdni rob', 'blage temperature'],
    recommendation: 'Za pohod uporabi dolga oblacila, repelent in pregled telesa v eni uri po vrnitvi.',
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
  },
  {
    id: 'primorska',
    name: 'Primorska',
    score: 34,
    level: 'Nizko',
    trend: '-8 % glede na prejsnji teden',
    summary: 'Bolj suho obdobje zmanjsuje aktivnost klopov, tveganje pa ni nicelno.',
    factors: ['suho obdobje', 'manj vlage v tleh', 'nizja aktivnost klopov'],
    recommendation: 'Osnovna zascita je se vedno smiselna, posebej v senčnih in zarascenih delih.',
  },
]

const levelClassName: Record<RegionRisk['level'], string> = {
  Nizko: 'level-low',
  Srednje: 'level-medium',
  Visoko: 'level-high',
}

function App() {
  const [selectedRegionId, setSelectedRegionId] = useState(regions[0].id)
  const selectedRegion =
    regions.find((region) => region.id === selectedRegionId) ?? regions[0]

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="eyebrow">AI napoved tveganja za klope</div>
        <h1>Klop pod klopjo</h1>
        <p className="hero-copy">
          Prototip prikazuje, kako lahko model iz vremenskih in okoljskih
          podatkov oceni verjetnost povecane aktivnosti klopov po regijah.
        </p>

        <div className="hero-metrics">
          <article className="metric-card">
            <span className="metric-label">Trenutno izbrana regija</span>
            <strong>{selectedRegion.name}</strong>
          </article>
          <article className="metric-card">
            <span className="metric-label">AI ocena tveganja</span>
            <strong>{selectedRegion.score}/100</strong>
          </article>
          <article className="metric-card">
            <span className="metric-label">Tedenski trend</span>
            <strong>{selectedRegion.trend}</strong>
          </article>
        </div>
      </section>

      <section className="content-grid">
        <article className="selection-card">
          <div className="section-header">
            <span className="section-kicker">Izberi regijo</span>
            <h2>Demo vhodni podatki</h2>
          </div>

          <div className="region-list" role="list">
            {regions.map((region) => (
              <button
                key={region.id}
                type="button"
                className={`region-button${
                  region.id === selectedRegion.id ? ' region-button-active' : ''
                }`}
                onClick={() => setSelectedRegionId(region.id)}
              >
                <span>{region.name}</span>
                <span className={`risk-pill ${levelClassName[region.level]}`}>
                  {region.level}
                </span>
              </button>
            ))}
          </div>

          <p className="card-note">
            Naslednji korak je, da te mock podatke zamenjate z dejanskim API
            odgovorom iz modela.
          </p>
        </article>

        <article className="insight-card">
          <div className="section-header">
            <span className="section-kicker">Napoved</span>
            <h2>Zakaj je tveganje {selectedRegion.level.toLowerCase()}</h2>
          </div>

          <div className="score-row">
            <div className="score-ring">
              <span>{selectedRegion.score}</span>
            </div>
            <div>
              <span className={`risk-pill ${levelClassName[selectedRegion.level]}`}>
                {selectedRegion.level}
              </span>
              <p className="summary">{selectedRegion.summary}</p>
            </div>
          </div>

          <div className="factor-grid">
            {selectedRegion.factors.map((factor) => (
              <div key={factor} className="factor-chip">
                {factor}
              </div>
            ))}
          </div>

          <div className="recommendation-box">
            <span className="section-kicker">Priporocilo za uporabnika</span>
            <p>{selectedRegion.recommendation}</p>
          </div>
        </article>
      </section>
    </main>
  )
}

export default App
