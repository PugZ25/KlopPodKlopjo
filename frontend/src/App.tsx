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
  diseaseSources,
  ixodesSections,
  noticeText,
  preventionGroups,
  regionInsight,
  removalSources,
  removalSteps,
  sloveniaSources,
  topicNavItems,
  vaccinationHighlights,
  vaccinationSources,
} from './data/siteContent'
import { findMunicipalityByCoordinates } from './utils/municipalityLookup'
import './App.css'

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

const summaryPanelClassName = {
  Nizko: 'summary-panel-low',
  Srednje: 'summary-panel-medium',
  Visoko: 'summary-panel-high',
} as const

type SourceLink = {
  label: string
  href?: string
}

type LightboxImage = {
  src: string
  alt: string
  caption: string
}

type SectionAccordionProps = {
  id: string
  kicker: string
  title: string
  description: string
  defaultOpen?: boolean
  children: ReactNode
}

type InteractiveImageProps = LightboxImage & {
  onOpen: (image: LightboxImage) => void
}

const diseaseTabs: DiseaseModelKey[] = ['borelioza', 'kme']

function formatDisplayDate(value: string) {
  return new Intl.DateTimeFormat('sl-SI', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(`${value}T00:00:00`))
}

function buildTimeHorizonLabel(diseaseKey: DiseaseModelKey) {
  return diseaseKey === 'borelioza' ? 'naslednje 4 tedne' : 'naslednjih 8 tednov'
}

function buildDiseaseObjectLabel(diseaseKey: DiseaseModelKey) {
  return diseaseKey === 'borelioza' ? 'boreliozo' : 'KME'
}

function buildSummary(level: RiskLevel, diseaseKey: DiseaseModelKey) {
  const diseaseObjectLabel = buildDiseaseObjectLabel(diseaseKey)

  if (level === 'Visoko') {
    if (diseaseKey === 'kme') {
      return 'Ocena tveganja za KME je visoka. Tveganje je lahko povečano, zato so zaščitni ukrepi, pregled telesa po obisku narave in cepljenje proti KME posebej pomembni.'
    }

    return 'Ocena tveganja za boreliozo je visoka. Tveganje je lahko povečano, zato so zaščitni ukrepi in pregled telesa po obisku narave posebej pomembni.'
  }

  if (level === 'Srednje') {
    return `Ocena tveganja za ${diseaseObjectLabel} je srednja. Tveganje je lahko zmerno, zato so priporočeni zaščitni ukrepi.`
  }

  return `Ocena tveganja za ${diseaseObjectLabel} je nizka. Tveganje je lahko majhno, vendar še vedno upoštevaj zaščitne ukrepe.`
}

function buildRiskBadgeStyle(level: RiskLevel, score: number): CSSProperties {
  const normalizedScore = Math.max(0, Math.min(score, 100))

  return {
    '--score-accent': levelAccentColor[level],
    '--score-angle': `${(normalizedScore / 100) * 360}deg`,
  } as CSSProperties
}

function buildMovementLabel(deltaScore: number) {
  if (deltaScore >= 8) {
    return 'Tveganje se povečuje.'
  }

  if (deltaScore <= -8) {
    return 'Tveganje se zmanjšuje.'
  }

  return 'Tveganje ostaja podobno.'
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

function SectionAccordion({
  id,
  kicker,
  title,
  description,
  defaultOpen = false,
  children,
}: SectionAccordionProps) {
  return (
    <details id={id} className="accordion-card" open={defaultOpen}>
      <summary className="accordion-summary">
        <span className="accordion-summary-copy">
          <span className="section-kicker">{kicker}</span>
          <span className="accordion-title">{title}</span>
          <span className="accordion-description">{description}</span>
        </span>
        <span className="accordion-indicator" aria-hidden="true">
          +
        </span>
      </summary>

      <div className="accordion-body">{children}</div>
    </details>
  )
}

function InteractiveImage({ src, alt, caption, onOpen }: InteractiveImageProps) {
  return (
    <figure className="image-card">
      <button
        type="button"
        className="image-card-button"
        onClick={() => onOpen({ src, alt, caption })}
        aria-label="Povečaj sliko"
      >
        <img src={src} alt={alt} />
        <span className="image-card-hint" aria-hidden="true">
          Povečaj
        </span>
      </button>
      <figcaption>{caption}</figcaption>
    </figure>
  )
}

function App() {
  const [selectedDiseaseKey, setSelectedDiseaseKey] =
    useState<DiseaseModelKey>('borelioza')
  const [selectedMunicipalityCode, setSelectedMunicipalityCode] = useState(
    liveMunicipalityRiskModels.borelioza.featuredLocations[0]?.municipalityCode ??
      liveMunicipalityRiskModels.borelioza.locations[0]?.municipalityCode ??
      '',
  )
  const [expandedImage, setExpandedImage] = useState<LightboxImage | null>(null)
  const [locationMessage, setLocationMessage] = useState('')
  const [isLocating, setIsLocating] = useState(false)

  useEffect(() => {
    if (!expandedImage) {
      return
    }

    const previousOverflow = document.body.style.overflow

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setExpandedImage(null)
      }
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [expandedImage])

  const activeModel = liveMunicipalityRiskModels[selectedDiseaseKey]
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

  const riskBadgeStyle = buildRiskBadgeStyle(
    selectedLocation.level,
    selectedLocation.score,
  )
  const timeHorizon = buildTimeHorizonLabel(selectedDiseaseKey)
  const referenceRangeLabel = `${formatDisplayDate(
    activeModel.referenceWeekStart,
  )} - ${formatDisplayDate(activeModel.referenceWeekEnd)}`
  const riskActionLinks =
    selectedDiseaseKey === 'kme'
      ? [
          { label: 'Cepljenje', href: '#cepljenje' },
          { label: 'Preventiva', href: '#preventiva' },
          { label: 'Odstranitev klopa', href: '#odstranitev-klopa' },
        ]
      : [
          { label: 'Preventiva', href: '#preventiva' },
          { label: 'Odstranitev klopa', href: '#odstranitev-klopa' },
          { label: 'Klopne bolezni', href: '#klopne-bolezni' },
        ]

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
      <div className="notice-bar" role="status" aria-live="polite">
        <div className="notice-track">
          <span>{noticeText}</span>
        </div>
      </div>

      <main className="app-shell">
        <section className="hero-panel">
          <div className="hero-layout">
            <div className="hero-copy-block">
              <div className="hero-brand-lockup">
                <div className="hero-logo-badge" aria-hidden="true">
                  <img className="hero-logo-image" src={brandLogo} alt="" />
                </div>

                <div className="hero-title-stack">
                  <h1>Klop pod klopjo</h1>
                </div>
              </div>
            </div>
          </div>
        </section>

        <nav className="jump-rail" aria-label="Hitri skoki po vsebini">
          {topicNavItems.map((item) => (
            <a key={item.href} className="jump-pill" href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        <section id="preverjanje-tveganja" className="content-section risk-stage">
          <div className="section-header">
            <span className="section-kicker">Osrednje orodje</span>
            <h2>Preverjanje tveganja po občinah</h2>
            <p>
              {activeModel.methodologyNote} Namenjena je hitri orientaciji, ne
              medicinski diagnozi.
            </p>
          </div>

          <div className="content-grid prediction-grid">
            <article className="selection-card">
              <div className="section-header">
                <span className="section-kicker">Interaktivni del</span>
                <h2>Izberi bolezen in občino</h2>
                <p>
                  Pregledaj zemljevid, klikni občino ali uporabi svojo lokacijo.
                  Fokus strani je prav lokalna ocena tveganja in hiter prehod do
                  ustreznih ukrepov.
                </p>
              </div>

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

              <div className="live-toolbar">
                <button
                  type="button"
                  className="hero-link location-button"
                  onClick={handleUseLocation}
                  disabled={isLocating}
                >
                  {isLocating ? 'Lociram ...' : 'Uporabi mojo lokacijo'}
                </button>

                <div className="live-meta">
                  <span className="metric-label">Referenčni teden</span>
                  <strong>{referenceRangeLabel}</strong>
                  <p>Vremenski vir: Open-Meteo. Podatki so prikazani po občinah.</p>
                </div>
              </div>

              {locationMessage ? (
                <p className="live-status" role="status">
                  {locationMessage}
                </p>
              ) : null}

              <MapView
                locations={mapLocations}
                selectedLocationId={selectedLocation.id}
                onSelectLocation={handleSelectLocation}
                diseaseLabel={activeModel.diseaseLabel}
                selectedLocation={selectedMapLocation}
              />

              <p className="card-note">
                Klikni na občinski poligon ali uporabi svojo lokacijo. Rezultat
                se prikaže samo kot nizko, srednje ali visoko tveganje.
              </p>

              <div className="map-summary-bar">
                <div className="map-summary-card">
                  <span className="section-kicker">Izbrana občina</span>
                  <div className="map-summary-headline">
                    <strong>{selectedLocation.municipalityName}</strong>
                    <span className={`risk-pill ${levelClassName[selectedLocation.level]}`}>
                      {selectedLocation.level}
                    </span>
                  </div>
                  <p>
                    Ocena za {buildDiseaseObjectLabel(selectedDiseaseKey)} za{' '}
                    {timeHorizon}.
                    Izberi občino na zemljevidu ali uporabi svojo lokacijo.
                  </p>
                </div>

                <div className="map-legend-bar" aria-hidden="true">
                  <span className="map-legend-chip">
                    <span className="map-legend-dot map-legend-dot-low" />
                    Nizko
                  </span>
                  <span className="map-legend-chip">
                    <span className="map-legend-dot map-legend-dot-medium" />
                    Srednje
                  </span>
                  <span className="map-legend-chip">
                    <span className="map-legend-dot map-legend-dot-high" />
                    Visoko
                  </span>
                </div>
              </div>
            </article>

            <article className="insight-card">
              <div className="section-header">
                <span className="section-kicker">Ocena tveganja</span>
                <h2>
                  {activeModel.diseaseLabel} v občini {selectedLocation.municipalityName}
                </h2>
              </div>

              <div className="score-row">
                <div className="score-ring" style={riskBadgeStyle}>
                  <span>{selectedLocation.level}</span>
                </div>
                <div>
                  <span className="metric-label">Občinsko tveganje</span>
                  <span
                    className={`risk-pill ${levelClassName[selectedLocation.level]}`}
                  >
                    {selectedLocation.level}
                  </span>
                  <div
                    className={`summary-panel ${summaryPanelClassName[selectedLocation.level]}`}
                  >
                    <span className="summary-kicker">Pomembno</span>
                    <p className="summary">
                      {buildSummary(selectedLocation.level, selectedDiseaseKey)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="trend-card">
                <span className="metric-label">Tedenski premik</span>
                <strong>{buildMovementLabel(selectedLocation.trendDeltaScore)}</strong>
              </div>

              <div className="action-links-panel">
                <span className="metric-label">Kam naprej</span>
                <div className="action-links">
                  {riskActionLinks.map((link) => (
                    <a key={link.href} className="action-link" href={link.href}>
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            </article>
          </div>
        </section>

        <section id="zascita" className="content-section knowledge-section">
          <div className="section-header">
            <span className="section-kicker">Preventiva</span>
            <h2>Kako ukrepati?</h2>
          </div>

          <nav className="subtopic-rail" aria-label="Skoki po preventivnih vsebinah">
            <a className="subtopic-link" href="#cepljenje">
              Cepljenje
            </a>
            <a className="subtopic-link" href="#preventiva">
              Preventiva
            </a>
            <a className="subtopic-link" href="#odstranitev-klopa">
              Odstranitev klopa
            </a>
          </nav>

          <div className="accordion-grid">
            <SectionAccordion
              id="cepljenje"
              kicker="Cepljenje"
              title="Preventiva proti KME"
              description="Kdo se lahko cepi, kako poteka shema in kam se naročiš."
              defaultOpen
            >
              <div className="vaccination-grid">
                <div className="story-card">
                  <div className="copy-flow">
                    <p>
                      Obolevnost za klopnim meningoencefalitisom je v Sloveniji
                      med najvišjimi v Evropi, letno zboli v povprečju okrog 150
                      oseb, delež cepljenih oseb pa je zelo nizek.
                    </p>
                    <p>
                      Otrok se lahko prvič cepi proti KME po dopolnjenem 1. letu
                      starosti. V letu 2026 je cepljenje brezplačno za otroke,
                      rojene leta 2016 ali kasneje, ter za odrasle, rojene med
                      letoma 1970 in 1983, ki še niso prejeli treh odmerkov
                      cepiva.
                    </p>
                    <p>
                      Pri cepljenju otrok najprej sledi prvi odmerek, nato drugi
                      čez 1 do 3 mesece in tretji čez 5 do 12 mesecev po drugem.
                    </p>
                    <p>
                      Prva revakcinacija se opravi tri leta po tretjem odmerku,
                      naslednje pa na pet let. Po 60. letu se priporoča
                      poživitveni odmerek na vsaka tri leta. Poživitveni odmerki
                      so samoplačniški, cena pa se giblje okrog 30 evrov.
                    </p>
                    <p>
                      Osebe, ki so laboratorijsko dokazano prebolele KME, so
                      zaščitene proti bolezni in ne potrebujejo cepljenja.
                    </p>
                  </div>

                  <div className="highlight-grid">
                    {vaccinationHighlights.map((item) => (
                      <article key={item.title} className="highlight-card">
                        <span className="metric-label">{item.title}</span>
                        <p>{item.text}</p>
                      </article>
                    ))}
                  </div>

                  <a
                    className="hero-link hero-link-secondary"
                    href="https://nijz.si/nalezljive-bolezni/cepljenje/cepljenje-proti-klopnemu-meningoencefalitisu/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Več o cepljenju na strani NIJZ
                  </a>
                </div>

                <InteractiveImage
                  src={vaccinationScheduleImage}
                  alt="Shema cepljenja FSME-IMMUN za osnovno serijo in poživitvene odmerke."
                  caption="Osnovna serija vsebuje tri odmerke, po njej pa sledijo revakcinacije glede na starost."
                  onOpen={setExpandedImage}
                />
              </div>

              <SourceBlock sources={vaccinationSources} />
            </SectionAccordion>

            <SectionAccordion
              id="preventiva"
              kicker="Preventiva"
              title="Kako zmanjšaš možnost ugriza"
              description="Kaj obleči, česa se izogibati in kaj pregledati po vrnitvi domov."
            >
              <div className="copy-flow intro-copy">
                <p>
                  Kljub{' '}
                  <a className="inline-link" href="#cepljenje">
                    cepljenju
                  </a>{' '}
                  vas cepivo ščiti le pred KME, medtem ko cepivo za lymsko
                  boreliozo še ne obstaja. Zato velja previdnost ob pohodu,
                  kampiranju ali raziskovanju bližnjega gozda.
                </p>
                <p>
                  Tako priporočamo, da kar se da dosledno upoštevaš naslednje
                  ukrepe:
                </p>
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

                    {group.title === 'Po vrnitvi domov' ? (
                      <p className="section-note">
                        Če opaziš klopa, ga čim prej odstrani.{' '}
                        <a className="inline-link" href="#odstranitev-klopa">
                          Kako odstraniti klopa
                        </a>
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            </SectionAccordion>

            <SectionAccordion
              id="odstranitev-klopa"
              kicker="Odstranitev klopa"
              title="Postopek odstranitve"
              description="Kratek postopek, brez olja, krem in nepotrebnega sukanja."
            >
              <div className="removal-layout">
                <article className="story-card">
                  <ol className="step-list">
                    {removalSteps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </article>

                <aside className="story-card callout-card">
                  <span className="section-kicker">Pomembno</span>
                  <p>
                    Klopa zavijemo v lepilni trak, ga splaknemo v školjki ali pa
                    ga potopimo v alkohol oziroma razkužilo. Ne zmečkamo ga s
                    prsti.
                  </p>
                  <a
                    className="hero-link"
                    href="https://www.youtube.com/watch?v=27McsguL2Og"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Video prikaz odstranitve
                  </a>
                </aside>
              </div>

              <SourceBlock sources={removalSources} />
            </SectionAccordion>
          </div>
        </section>

        <section id="znanje" className="content-section knowledge-section">
          <div className="section-header">
            <span className="section-kicker">Informacije</span>
            <h2>Kaj je dobro vedeti</h2>
          </div>

          <nav className="subtopic-rail" aria-label="Skoki po informacijskih vsebinah">
            <a className="subtopic-link" href="#ixodes-ricinus">
              Ixodes ricinus
            </a>
            <a className="subtopic-link" href="#klopne-bolezni">
              Klopne bolezni
            </a>
            <a className="subtopic-link" href="#posebnosti-slovenije">
              Posebnosti Slovenije
            </a>
          </nav>

          <div className="accordion-grid">
            <SectionAccordion
              id="ixodes-ricinus"
              kicker="Ixodes ricinus"
              title="Navadni gozdni klop"
              description="Habitat, življenjski cikel in kako klop najde gostitelja."
              defaultOpen
            >
              <div className="copy-flow intro-copy">
                <p>
                  <em>Ixodes ricinus</em>, znan kot navadni gozdni klop, je
                  najpogostejša vrsta klopa v Evropi in tudi v Sloveniji ter
                  predstavlja enega najpomembnejših prenašalcev nalezljivih
                  bolezni pri ljudeh.
                </p>
              </div>

              <div className="story-grid">
                {ixodesSections.map((section) => (
                  <article key={section.title} className="story-card">
                    <h3>{section.title}</h3>
                    <div className="copy-flow">
                      {section.paragraphs.map((paragraph) => (
                        <p key={paragraph}>{paragraph}</p>
                      ))}
                    </div>
                  </article>
                ))}
              </div>

              <SourceBlock sources={regionInsight.ixodesSources} />
            </SectionAccordion>

            <SectionAccordion
              id="klopne-bolezni"
              kicker="Klopne bolezni"
              title="Lymska borelioza in klopni meningoencefalitis"
              description="Razlike med boreliozo in KME ter zakaj je hitra reakcija pomembna."
            >
              <div className="disease-grid">
                <article className="disease-card">
                  <h3>Lymska borelioza</h3>
                  <div className="copy-flow">
                    <p>
                      V Sloveniji je borelioza najpogostejša nalezljiva bolezen,
                      ki jo prenašajo klopi. Pojavlja se po celi državi in letno
                      beležimo okoli 5.000 do 7.000 zbolelih. Tveganje za okužbo
                      je največje od februarja do novembra, blage zime in vlažne
                      pomladi pa spodbujajo pojavnost klopov.
                    </p>
                    <p>
                      Lymsko boreliozo povzročajo bakterije iz rodu{' '}
                      <em>Borrelia</em>. Klop se z bakterijo okuži med sesanjem
                      krvi okužene živali, najpogosteje malih gozdnih sesalcev in
                      ptic, lahko pa tudi večjih sesalcev, kot so srne.
                    </p>
                    <p>
                      Ko okužen klop ugrizne človeka, lahko bakterijo prenese
                      preko sline v kožo. Bakterija se mora po začetku hranjenja
                      najprej aktivirati in premakniti v klopove žleze
                      slinavke, kar običajno traja 24 do 36 ur, zato zgodnja
                      odstranitev klopa izrazito zmanjša tveganje za okužbo.
                    </p>
                    <p>
                      Borelioza običajno poteka v treh fazah. V prvi fazi
                      bolezni, 3 do 32 dni po ugrizu okuženega klopa, se lahko
                      pojavi značilna neboleča rdečina, ki se počasi širi po
                      koži, na sredini bledi in dobi obliko kolobarja. Kasneje
                      se lahko pokaže prizadetost kože, živčevja, sklepov, mišic,
                      oči in srca.
                    </p>
                    <p>
                      Boreliozo zdravimo z antibiotiki. Pomembna je zgodnja
                      prepoznava bolezni, saj je zdravljenje v prvi fazi
                      praviloma zelo učinkovito. Predhodna okužba ne pušča
                      zaščite pred boleznijo.
                    </p>
                  </div>
                </article>

                <article className="disease-card">
                  <h3>Klopni meningoencefalitis</h3>
                  <div className="copy-flow">
                    <p>
                      Klopni meningoencefalitis (KME) je virusna bolezen
                      osrednjega živčevja, ki je v Sloveniji endemična. Letno
                      zanj zboli okoli 150 ljudi.
                    </p>
                    <p>
                      KME povzroča virus klopnega meningoencefalitisa iz družine
                      flavivirusov. Virus se nahaja v slini okuženega klopa in se
                      lahko že v nekaj minutah po ugrizu prenese na človeka. Z
                      virusom se lahko okužimo tudi z uživanjem
                      nepasteriziranega mleka ali mlečnih izdelkov, narejenih iz
                      mleka okužene živine.
                    </p>
                    <p>
                      Prvi simptomi bolezni se običajno pojavijo v 7 do 14 dneh
                      po ugrizu. Začetni simptomi so podobni gripi, nato sledi
                      obdobje brez simptomov, druga faza pa se začne s ponovnim
                      dvigom temperature in vnetjem možganskih ovojnic ter
                      možganovine.
                    </p>
                    <p>
                      Pri 20 do 30 odstotkih obolelih se stanje razvije v
                      meningoencefalitis. Pri otrocih in mladostnikih ima bolezen
                      običajno lažji potek, pri starejših bolnikih pa se
                      pogosteje pojavlja resen potek bolezni s trajnimi
                      posledicami.
                    </p>
                    <p>
                      Za KME nimamo zdravila, zaščitimo pa se lahko s{' '}
                      <a className="inline-link" href="#cepljenje">
                        cepljenjem
                      </a>
                      . Na voljo je podporno zdravljenje, smrtnost pa je med 0,5
                      in 2 odstotka.
                    </p>
                  </div>
                </article>

                <InteractiveImage
                  src={tbeMapImage}
                  alt="Zemljevid razširjenosti klopnega meningoencefalitisa v Evropi in Aziji."
                  caption="Razširjenost virusa klopnega meningoencefalitisa poudarja, da je Slovenija del širšega endemičnega prostora."
                  onOpen={setExpandedImage}
                />
              </div>

              <SourceBlock sources={diseaseSources} />
            </SectionAccordion>

            <SectionAccordion
              id="posebnosti-slovenije"
              kicker="Posebnosti Slovenije"
              title="Zakaj je tema pri nas posebej pomembna"
              description="Zakaj je Slovenija izrazito izpostavljeno območje in kaj to pomeni v praksi."
            >
              <div className="copy-flow intro-copy">
                <p>{regionInsight.sloveniaIntro}</p>
              </div>

              <div className="highlight-grid">
                {regionInsight.sloveniaHighlights.map((item) => (
                  <article key={item.title} className="highlight-card">
                    <span className="metric-label">{item.title}</span>
                    <strong>{item.value}</strong>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>

              <SourceBlock sources={sloveniaSources} />
            </SectionAccordion>
          </div>
        </section>
      </main>

      {expandedImage ? (
        <div className="image-lightbox" onClick={() => setExpandedImage(null)}>
          <div
            className="image-lightbox-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Povečana slika"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="image-lightbox-close"
              onClick={() => setExpandedImage(null)}
              aria-label="Zapri povečano sliko"
              autoFocus
            >
              Zapri
            </button>

            <img
              className="image-lightbox-image"
              src={expandedImage.src}
              alt={expandedImage.alt}
            />
            <p className="image-lightbox-caption">{expandedImage.caption}</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default App
