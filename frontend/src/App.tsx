import { useState } from 'react'
import { MapView } from './components/MapView'
import { regions } from './data/regionRisk'
import './App.css'

const levelClassName = {
  Nizko: 'level-low',
  Srednje: 'level-medium',
  Visoko: 'level-high',
} as const

function App() {
  const [selectedRegionId, setSelectedRegionId] = useState(regions[0].id)
  const selectedRegion =
    regions.find((region) => region.id === selectedRegionId) ?? regions[0]

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="eyebrow">AI napoved tveganja za boreliozo in KME</div>
        <h1>Klop pod klopjo</h1>
        <p className="hero-copy">
          Prototip prikazuje, kako lahko model iz vremenskih, okoljskih in
          prostorskih podatkov oceni regionalno tveganje za boreliozo oziroma
          KME.
        </p>

        <div className="hero-metrics">
          <article className="metric-card">
            <span className="metric-label">Trenutno izbrana regija</span>
            <strong>{selectedRegion.name}</strong>
          </article>
          <article className="metric-card">
            <span className="metric-label">AI ocena zdravstvenega tveganja</span>
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
            <span className="section-kicker">Zemljevid Slovenije</span>
            <h2>Demo geografski prikaz</h2>
          </div>

          <MapView
            regions={regions}
            selectedRegionId={selectedRegion.id}
            onSelectRegion={setSelectedRegionId}
          />

          <p className="card-note">
            Klik na oznako na zemljevidu ali na regijo spodaj spremeni fokus in
            podrobnosti napovedi.
          </p>

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
        </article>

        <article className="insight-card">
          <div className="section-header">
            <span className="section-kicker">Napoved</span>
            <h2>Zakaj je tveganje za boreliozo ali KME {selectedRegion.level.toLowerCase()}</h2>
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
