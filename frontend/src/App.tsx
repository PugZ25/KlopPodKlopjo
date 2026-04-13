import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import brandLogo from '../logo.png'
import tbeMapImage from '../navodila/images/image1.png'
import vaccinationScheduleImage from '../navodila/images/image2.png'
import { MapView } from './components/MapView'
import {
  liveMunicipalityRiskModels,
  type DiseaseModelKey,
  type RiskLevel,
} from './data/liveMunicipalityRisk'
import {
  diseaseCards,
  diseaseSources,
  ixodesIntro,
  ixodesSections,
  preventionGroups,
  preventionIntroParagraphs,
  regionInsight,
  removalImportantParagraphs,
  removalIntro,
  removalSources,
  removalSteps,
  sloveniaSources,
  topicNavItems,
  type SourceLink,
  vaccinationHighlights,
  vaccinationParagraphs,
  vaccinationSources,
} from './data/siteContent'
import { findMunicipalityByCoordinates } from './utils/municipalityLookup'
import './App.css'

const diseaseTabs: DiseaseModelKey[] = ['borelioza', 'kme']

const levelClassName = {
  Nizko: 'level-low',
  Srednje: 'level-medium',
  Visoko: 'level-high',
} as const

const levelAccentColor = {
  Nizko: '#4a9c70',
  Srednje: '#d49b42',
  Visoko: '#c1543f',
} as const

const levelAngle = {
  Nizko: '120deg',
  Srednje: '240deg',
  Visoko: '360deg',
} as const

type SectionCardProps = {
  id: string
  title: string
  subtitle?: string
  children: ReactNode
}

function buildRiskRingStyle(level: RiskLevel): CSSProperties {
  return {
    '--score-accent': levelAccentColor[level],
    '--score-angle': levelAngle[level],
  } as CSSProperties
}

function buildRiskHeading(diseaseKey: DiseaseModelKey, municipalityName: string) {
  return diseaseKey === 'borelioza'
    ? `Borelioza v občini ${municipalityName}`
    : `KME v občini ${municipalityName}`
}

function buildRiskExplanation(level: RiskLevel) {
  if (level === 'Visoko') {
    return 'Tveganje za okužbo s KME ali borelizozo je visoko. Zaščitni ukrepi, telesni pregled in cepljenje proti KME so ključni.'
  }

  if (level === 'Srednje') {
    return 'Tveganje za okužbo s KME ali boreliozo je zmerno. Priporočeni so zaščitni ukrepi.'
  }

  return 'Tveganje za okužbo s KME ali boreliozo je majhno, vendar sledi zaščitnim ukrepom.'
}

function formatGeolocationError(error: GeolocationPositionError) {
  if (error.code === error.PERMISSION_DENIED) {
    return 'Dostop do lokacije je bil zavrnjen.'
  }

  if (error.code === error.POSITION_UNAVAILABLE) {
    return 'Lokacije trenutno ni mogoče določiti.'
  }

  if (error.code === error.TIMEOUT) {
    return 'Iskanje lokacije je poteklo.'
  }

  return 'Pri pridobivanju lokacije je prišlo do napake.'
}

function SourceBlock({
  sources,
  summary = 'Viri',
}: {
  sources: readonly SourceLink[]
  summary?: string
}) {
  return (
    <details className="source-block">
      <summary>{summary}</summary>
      <ul className="source-list">
        {sources.map((source) => (
          <li key={source.label}>
            {source.href ? (
              <a href={source.href} target="_blank" rel="noreferrer">
                {source.label}
              </a>
            ) : (
              <span>{source.label}</span>
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}

function SectionCard({ id, title, subtitle, children }: SectionCardProps) {
  return (
    <section id={id} className="cloud-section">
      <div className="section-heading">
        <h2>{title}</h2>
        {subtitle ? <p className="section-subtitle">{subtitle}</p> : null}
      </div>
      <div className="section-body">{children}</div>
    </section>
  )
}

function App() {
  const [selectedDiseaseKey, setSelectedDiseaseKey] =
    useState<DiseaseModelKey>('borelioza')
  const [selectedMunicipalityCode, setSelectedMunicipalityCode] = useState(
    liveMunicipalityRiskModels.borelioza.locations[0]?.municipalityCode ?? '',
  )
  const [locationMessage, setLocationMessage] = useState('')
  const [isLocating, setIsLocating] = useState(false)

  const activeModel = liveMunicipalityRiskModels[selectedDiseaseKey]

  useEffect(() => {
    const hasSelectedMunicipality = activeModel.locations.some(
      (location) => location.municipalityCode === selectedMunicipalityCode,
    )

    if (!hasSelectedMunicipality) {
      setSelectedMunicipalityCode(activeModel.locations[0]?.municipalityCode ?? '')
    }
  }, [activeModel, selectedMunicipalityCode])

  const fallbackLocation = activeModel.locations[0]
  const selectedLocation =
    activeModel.locations.find(
      (location) => location.municipalityCode === selectedMunicipalityCode,
    ) ?? fallbackLocation

  if (!selectedLocation) {
    return null
  }

  const mapLocations = activeModel.locations.map((location) => ({
    id: location.id,
    municipalityCode: location.municipalityCode,
    name: location.municipalityName,
    score: location.score,
    level: location.level,
    coordinates: location.coordinates,
  }))

  const selectedMapLocation =
    mapLocations.find((location) => location.id === selectedLocation.id) ??
    mapLocations[0]

  if (!selectedMapLocation) {
    return null
  }

  const riskRingStyle = buildRiskRingStyle(selectedLocation.level)

  function handleSelectLocation(locationId: string) {
    const nextLocation = activeModel.locations.find(
      (location) => location.id === locationId,
    )

    if (!nextLocation) {
      return
    }

    setSelectedMunicipalityCode(nextLocation.municipalityCode)
  }

  function handleUseLocation() {
    if (!navigator.geolocation) {
      setLocationMessage('Brskalnik ne podpira geolokacije.')
      return
    }

    setIsLocating(true)
    setLocationMessage('Lociram tvojo občino ...')

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const municipality = await findMunicipalityByCoordinates(
            position.coords.latitude,
            position.coords.longitude,
          )

          if (!municipality) {
            setLocationMessage(
              'Lokacija ni bila prepoznana znotraj podprtih občin Slovenije.',
            )
            return
          }

          setSelectedMunicipalityCode(municipality.code)
          setLocationMessage(`Lokacija prepoznana: ${municipality.name}.`)
        } catch (error) {
          setLocationMessage(
            error instanceof Error ? error.message : 'Iskanje občine ni uspelo.',
          )
        } finally {
          setIsLocating(false)
        }
      },
      (error) => {
        setIsLocating(false)
        setLocationMessage(formatGeolocationError(error))
      },
      {
        enableHighAccuracy: true,
        maximumAge: 300000,
        timeout: 15000,
      },
    )
  }

  return (
    <div className="site-page">
      <div className="site-frame">
        <header className="top-bubble">
          <div className="brand-lockup">
            <img className="brand-logo" src={brandLogo} alt="Logotip Klop pod klopjo" />
            <div className="brand-copy">
              <h1>KLOP POD KLOPJO</h1>
            </div>
          </div>
        </header>

        <nav className="toolbar-bubble" aria-label="Orodna vrstica">
          {topicNavItems.map((item) => (
            <a key={item.href} className="toolbar-link" href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <main className="content-stack">
          <SectionCard
            id="preverjanje-tveganja"
            title="Preverjanje tveganja"
            subtitle="Preveri trenutno tveganje za KME in boreliozo."
          >
            <div className="risk-support-grid">
              <article className="panel-card">
                <span className="panel-label">Izbira</span>
                <div className="disease-toggle" role="tablist" aria-label="Izbira bolezni">
                  {diseaseTabs.map((diseaseKey) => (
                    <button
                      key={diseaseKey}
                      type="button"
                      role="tab"
                      aria-selected={selectedDiseaseKey === diseaseKey}
                      className={`disease-tab${
                        selectedDiseaseKey === diseaseKey ? ' disease-tab-active' : ''
                      }`}
                      onClick={() => setSelectedDiseaseKey(diseaseKey)}
                    >
                      {liveMunicipalityRiskModels[diseaseKey].diseaseLabel}
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  className="button-pill location-button"
                  onClick={handleUseLocation}
                  disabled={isLocating}
                >
                  {isLocating ? 'Lociram ...' : 'Uporabi mojo lokacijo'}
                </button>

                {locationMessage ? (
                  <p className="live-status" role="status">
                    {locationMessage}
                  </p>
                ) : null}
              </article>

              <article className="panel-card legend-card">
                <span className="panel-label">Legenda</span>
                <div className="legend-list">
                  <span className="legend-chip">
                    <span className="legend-swatch legend-low" />
                    Zelena - nizko tveganje
                  </span>
                  <span className="legend-chip">
                    <span className="legend-swatch legend-medium" />
                    Rumena - srednje tveganje
                  </span>
                  <span className="legend-chip">
                    <span className="legend-swatch legend-high" />
                    Rdeča - visoko tveganje
                  </span>
                </div>
                <p className="panel-copy">
                  Barvna lestvica prikazuje občinsko tveganje od nizkega do visokega.
                </p>
              </article>
            </div>

            <article className="panel-card map-panel">
              <div className="map-panel-heading">
                <h3>Interaktivni zemljevid Slovenije z občinami</h3>
                <p>Klikni občino na zemljevidu ali uporabi svojo lokacijo.</p>
              </div>

              <MapView
                locations={mapLocations}
                selectedLocationId={selectedLocation.id}
                onSelectLocation={handleSelectLocation}
                diseaseLabel={activeModel.diseaseLabel}
                selectedLocation={selectedMapLocation}
              />
            </article>

            <article className="panel-card risk-evaluation-card">
              <span className="panel-label">Ocena tveganja</span>
              <h3>{buildRiskHeading(selectedDiseaseKey, selectedLocation.municipalityName)}</h3>

              <div className="risk-evaluation-layout">
                <div className="score-ring" style={riskRingStyle}>
                  <span>{selectedLocation.level}</span>
                </div>

                <div className="risk-evaluation-copy">
                  <span className={`level-pill ${levelClassName[selectedLocation.level]}`}>
                    {selectedLocation.level}
                  </span>
                  <p>{buildRiskExplanation(selectedLocation.level)}</p>
                </div>
              </div>
            </article>
          </SectionCard>

          <SectionCard id="ixodes-ricinus" title="Ixodes ricinus">
            <div className="copy-flow intro-copy">
              <p>
                <em>Ixodes ricinus</em>
                {ixodesIntro.slice('Ixodes ricinus'.length)}
              </p>
            </div>

            <div className="story-grid">
              {ixodesSections.map((section) => (
                <article key={section.title} className="story-card">
                  <h3>{section.title}</h3>
                  <div className="copy-flow">
                    {section.paragraphs.map((paragraph, index) => (
                      <p key={`${section.title}-${index}`}>{paragraph}</p>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <SourceBlock sources={regionInsight.ixodesSources} />
          </SectionCard>

          <SectionCard id="klopne-bolezni" title="Klopne bolezni">
            <div className="disease-grid">
              {diseaseCards.map((card) => (
                <article key={card.title} className="disease-card">
                  <h3>{card.title}</h3>
                  <div className="copy-flow">
                    {card.paragraphs.map((paragraph, index) => (
                      <p key={`${card.title}-${index}`}>{paragraph}</p>
                    ))}
                  </div>
                </article>
              ))}

              <figure className="image-card">
                <img
                  src={tbeMapImage}
                  alt="Zemljevid razširjenosti klopnega meningoencefalitisa v Evropi in Aziji."
                />
              </figure>
            </div>

            <SourceBlock sources={diseaseSources} />
          </SectionCard>

          <SectionCard id="cepljenje" title="Cepljenje">
            <div className="vaccination-grid">
              <div className="story-card">
                <div className="copy-flow">
                  {vaccinationParagraphs.map((paragraph, index) => (
                    <p key={`vaccination-${index}`}>{paragraph}</p>
                  ))}
                </div>

                <div className="highlight-grid">
                  {vaccinationHighlights.map((item) => (
                    <article key={item.title} className="highlight-card">
                      <span className="panel-label">{item.title}</span>
                      <p>{item.text}</p>
                    </article>
                  ))}
                </div>

                <a
                  className="button-pill button-pill-secondary"
                  href="https://nijz.si/nalezljive-bolezni/cepljenje/cepljenje-proti-klopnemu-meningoencefalitisu/"
                  target="_blank"
                  rel="noreferrer"
                >
                  Več o cepljenju si lahko preberete tukaj
                </a>
              </div>

              <figure className="image-card">
                <img
                  src={vaccinationScheduleImage}
                  alt="Shema cepljenja FSME-IMMUN za osnovno serijo in poživitvene odmerke."
                />
                <figcaption>
                  Osnovna serija vsebuje tri odmerke, po njej pa sledijo revakcinacije
                  glede na starost.
                </figcaption>
              </figure>
            </div>

            <SourceBlock sources={vaccinationSources} />
          </SectionCard>

          <SectionCard id="preventiva" title="Preventiva">
            <div className="copy-flow intro-copy">
              {preventionIntroParagraphs.map((paragraph, index) => (
                <p key={`prevention-intro-${index}`}>{paragraph}</p>
              ))}
            </div>

            <div className="prevention-grid">
              {preventionGroups.map((group) => (
                <article key={group.title} className="story-card prevention-card">
                  <h3>{group.title}</h3>
                  <ul className="check-list">
                    {group.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </SectionCard>

          <SectionCard id="odstranitev-klopa" title="Odstranitev klopa">
            <div className="copy-flow intro-copy">
              <p>{removalIntro}</p>
            </div>

            <div className="removal-layout">
              <article className="story-card">
                <ol className="step-list">
                  {removalSteps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </article>

              <aside className="story-card callout-card">
                <span className="panel-label">Korak 5</span>
                {removalImportantParagraphs.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
                <a
                  className="button-pill"
                  href="https://www.youtube.com/watch?v=27McsguL2Og"
                  target="_blank"
                  rel="noreferrer"
                >
                  Video prikaz odstranitve
                </a>
              </aside>
            </div>

            <SourceBlock sources={removalSources} />
          </SectionCard>

          <SectionCard id="posebnosti-slovenije" title="Posebnosti Slovenije">
            <div className="copy-flow intro-copy">
              <p>{regionInsight.sloveniaIntro}</p>
            </div>

            <div className="highlight-grid">
              {regionInsight.sloveniaHighlights.map((item) => (
                <article key={item.title} className="highlight-card">
                  <span className="panel-label">{item.title}</span>
                  <strong>{item.value}</strong>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>

            <SourceBlock sources={sloveniaSources} />
          </SectionCard>
        </main>
      </div>
    </div>
  )
}

export default App
