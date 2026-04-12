import { useState, type CSSProperties } from 'react'
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
  heroStats,
  ixodesSections,
  navItems,
  noticeText,
  preventionGroups,
  regionInsight,
  removalSources,
  removalSteps,
  sloveniaSources,
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
  Nizko: '#3b9f76',
  Srednje: '#d49b42',
  Visoko: '#c1543f',
} as const

type SourceLink = {
  label: string
  href?: string
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
  const timeHorizon = buildTimeHorizonLabel(diseaseKey)
  const diseaseObjectLabel = buildDiseaseObjectLabel(diseaseKey)

  if (level === 'Visoko') {
    return `Obcina je v zgornjem delu zgodovinske holdout razvrstitve modela za ${diseaseObjectLabel} in ima povisan obcinski risk indeks na 100k prebivalcev za ${timeHorizon}.`
  }

  if (level === 'Srednje') {
    return `Obcina je v srednjem pasu zgodovinske holdout razvrstitve modela za ${diseaseObjectLabel}, zato je obcinski risk indeks na 100k prebivalcev za ${timeHorizon} zmeren.`
  }

  return `Obcina je v spodnjem delu zgodovinske holdout razvrstitve modela za ${diseaseObjectLabel}, zato je obcinski risk indeks na 100k prebivalcev za ${timeHorizon} nizek.`
}

function buildRecommendation(level: RiskLevel, diseaseKey: DiseaseModelKey) {
  const timeHorizon = buildTimeHorizonLabel(diseaseKey)

  if (level === 'Visoko') {
    return `Za ${timeHorizon} uporabljaj daljsa oblacila, repelent in po obisku narave takoj preveri kozo ter obleko. Rezultat ni diagnoza, je pa signal za vecjo previdnost.`
  }

  if (level === 'Srednje') {
    return `Osnovna preventiva ostaja smiselna: repelent, pregled koze po aktivnosti v naravi in hitra odstranitev klopa. Model za ${timeHorizon} ne kaze izrazitega vrha, vseeno pa signal ni nizek.`
  }

  return `Trenutni okoljski signal za ${timeHorizon} je nizek, vendar to ne pomeni nicelnega tveganja. Ob obisku gozda ali visoke trave se se vedno drzi osnovne zascite.`
}

function buildScoreRingStyle(score: number, level: RiskLevel): CSSProperties {
  const clampedScore = Math.max(0, Math.min(100, score))
  return {
    '--score-angle': `${Math.max(18, Math.round((clampedScore / 100) * 360))}deg`,
    '--score-accent': levelAccentColor[level],
  } as CSSProperties
}

function buildLevelCounts(locations: ReadonlyArray<{ level: RiskLevel }>) {
  return locations.reduce<Record<RiskLevel, number>>(
    (counts, location) => {
      counts[location.level] += 1
      return counts
    },
    {
      Nizko: 0,
      Srednje: 0,
      Visoko: 0,
    },
  )
}

function formatGeolocationError(error: GeolocationPositionError) {
  if (error.code === error.PERMISSION_DENIED) {
    return 'Dostop do lokacije je bil zavrnjen.'
  }

  if (error.code === error.POSITION_UNAVAILABLE) {
    return 'Lokacije trenutno ni mogoce dolociti.'
  }

  if (error.code === error.TIMEOUT) {
    return 'Iskanje lokacije je poteklo.'
  }

  return 'Pri pridobivanju lokacije je prislo do napake.'
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

function App() {
  const [selectedDiseaseKey, setSelectedDiseaseKey] =
    useState<DiseaseModelKey>('borelioza')
  const [selectedMunicipalityCode, setSelectedMunicipalityCode] = useState(
    liveMunicipalityRiskModels.borelioza.featuredLocations[0]?.municipalityCode ??
      liveMunicipalityRiskModels.borelioza.locations[0]?.municipalityCode ??
      '',
  )
  const [locationMessage, setLocationMessage] = useState('')
  const [isLocating, setIsLocating] = useState(false)

  const activeModel = liveMunicipalityRiskModels[selectedDiseaseKey]
  const selectedLocation =
    activeModel.locations.find(
      (location) => location.municipalityCode === selectedMunicipalityCode,
    ) ?? activeModel.locations[0]

  const quickLocations = [
    selectedLocation,
    ...activeModel.featuredLocations
      .map((featuredLocation) =>
        activeModel.locations.find(
          (location) => location.id === featuredLocation.id,
        ),
      )
      .filter((location): location is (typeof activeModel.locations)[number] =>
        Boolean(location),
      ),
  ].filter(
    (location, index, locations) =>
      locations.findIndex((candidate) => candidate.id === location.id) === index,
  )

  const mapLocations = activeModel.locations.map((location) => ({
    id: location.id,
    municipalityCode: location.municipalityCode,
    name: location.municipalityName,
    score: location.score,
    level: location.level,
    coordinates: location.coordinates,
  }))
  const levelCounts = buildLevelCounts(activeModel.locations)
  const locationCount = activeModel.locations.length
  const scoreRingStyle = buildScoreRingStyle(
    selectedLocation.score,
    selectedLocation.level,
  )
  const timeHorizon = buildTimeHorizonLabel(selectedDiseaseKey)

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
    setLocationMessage('Lociram tvojo obcino ...')

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const municipality = await findMunicipalityByCoordinates(
            position.coords.latitude,
            position.coords.longitude,
          )

          if (!municipality) {
            setLocationMessage(
              'Lokacija ni bila prepoznana znotraj podprtih obcin Slovenije.',
            )
            return
          }

          setSelectedMunicipalityCode(municipality.code)
          setLocationMessage(`Lokacija prepoznana: ${municipality.name}.`)
        } catch (error) {
          setLocationMessage(
            error instanceof Error ? error.message : 'Lookup obcine ni uspel.',
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
      <header className="site-header">
        <div className="brand-lockup">
          <span className="eyebrow">Klop pod klopjo</span>
          <strong>Vodnik po zaščiti pred klopi v Sloveniji</strong>
        </div>

        <nav className="site-nav" aria-label="Glavna navigacija">
          {navItems.map((item) => (
            <a key={item.href} className="site-nav-link" href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
      </header>

      <div className="notice-bar" role="status" aria-live="polite">
        <div className="notice-track">
          <span>{noticeText}</span>
          <span aria-hidden="true">{noticeText}</span>
        </div>
      </div>

      <main className="app-shell">
        <section className="hero-panel">
          <div className="hero-layout">
            <div>
              <span className="eyebrow">Informativni vodič</span>
              <h1>Klop pod klopjo</h1>
              <p className="hero-copy">
                <em>Ixodes ricinus</em>, navadni gozdni klop, je v Sloveniji eden
                najpomembnejših prenašalcev lymske borelioze in klopnega
                meningoencefalitisa. Stran združuje osnovne informacije o klopu,
                klopnih boleznih, cepljenju, preventivi in pravilni odstranitvi
                klopa.
              </p>

              <div className="hero-actions">
                <a className="hero-link" href="#klopne-bolezni">
                  Preberi več o klopnih boleznih
                </a>
                <a className="hero-link hero-link-secondary" href="#cepljenje">
                  Preveri možnosti cepljenja
                </a>
              </div>
            </div>

            <aside className="hero-aside">
              <span className="section-kicker">Hitri povzetek</span>
              <p>
                Slovenija je endemično območje za lymsko boreliozo in KME, zato
                sta zgodnje odstranjevanje klopa in dosledna preventiva ključna.
              </p>
              <p>
                Cepivo ščiti pred KME, ne pa tudi pred lymsko boreliozo, zato
                previdnost v naravi ostaja pomembna tudi pri cepljenih osebah.
              </p>
              <a className="inline-link" href="#posebnosti-slovenije">
                Posebnosti Slovenije
              </a>
            </aside>
          </div>

          <div className="hero-metrics">
            {heroStats.map((stat) => (
              <article key={stat.label} className="metric-card">
                <span className="metric-label">{stat.label}</span>
                <strong>{stat.value}</strong>
                <p>{stat.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="content-grid prediction-grid">
          <article className="selection-card">
            <div className="section-header">
              <span className="section-kicker">Interaktivni del</span>
              <h2>Live demo po občinah</h2>
              <p>
                Zemljevid uporablja zadnji zaključeni tedenski snapshot,
                Open-Meteo weather history in nova per-100k env modela, da za
                vsako občino izračuna rangirani obcinski risk indeks.
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
                <span className="metric-label">Referencni teden</span>
                <strong>
                  {formatDisplayDate(activeModel.referenceWeekStart)} -{' '}
                  {formatDisplayDate(activeModel.referenceWeekEnd)}
                </strong>
                <p>
                  Posodobitev {formatDisplayDate(activeModel.asOfDate)}. Vreme:{' '}
                  {activeModel.weatherSource}.
                </p>
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
              selectedLocation={mapLocations.find((location) => location.id === selectedLocation.id) ?? mapLocations[0]}
              levelCounts={levelCounts}
              locationCount={locationCount}
              timeHorizon={timeHorizon}
            />

            <p className="card-note">
              Klikni na obcinski poligon na zemljevidu ali uporabi lokacijo za
              fokus na svoji obcini. Pragovi Nizko / Srednje / Visoko ostanejo
              vezani na holdout distribucije modela.
            </p>

            <div className="region-list" role="list">
              <div className="region-list-header">
                <span className="section-kicker">Hitri skoki</span>
                <p>Najmocnejsi signali v trenutnem tedenskem snapshotu.</p>
              </div>
              {quickLocations.map((location) => (
                <button
                  key={location.id}
                  type="button"
                  className={`region-button${
                    location.id === selectedLocation.id
                      ? ' region-button-active'
                      : ''
                  }`}
                  onClick={() => setSelectedMunicipalityCode(location.municipalityCode)}
                >
                  <span>{location.municipalityName}</span>
                  <span className="region-button-meta">
                    <span className="region-score">{location.score}/100</span>
                    <span className={`risk-pill ${levelClassName[location.level]}`}>
                      {location.level}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </article>

          <article className="insight-card">
            <div className="section-header">
              <span className="section-kicker">Relativni indeks</span>
              <h2>
                {activeModel.diseaseLabel} v občini {selectedLocation.municipalityName}:{' '}
                {selectedLocation.level.toLowerCase()}
              </h2>
            </div>

            <div className="score-row">
              <div className="score-ring" style={scoreRingStyle}>
                <span>{selectedLocation.score}</span>
              </div>
              <div>
                <span className="metric-label">Obcinski risk indeks na 100k</span>
                <span
                  className={`risk-pill ${levelClassName[selectedLocation.level]}`}
                >
                  {selectedLocation.level}
                </span>
                <p className="summary">
                  {buildSummary(
                    selectedLocation.level,
                    selectedDiseaseKey,
                  )}
                </p>
              </div>
            </div>

            <div className="factor-grid">
              {activeModel.topDrivers.map((factor) => (
                <div key={factor} className="factor-chip">
                  {factor}
                </div>
              ))}
            </div>

            <div className="recommendation-box">
              <span className="section-kicker">Kako brati rezultat</span>
              <p>{buildRecommendation(selectedLocation.level, selectedDiseaseKey)}</p>
            </div>

            <div className="trend-card">
              <span className="metric-label">Tedenski premik</span>
              <strong>{selectedLocation.trendLabel}</strong>
              <p className="trend-copy">
                {activeModel.methodologyNote} {activeModel.disclaimer}
              </p>
            </div>
          </article>
        </section>

        <section id="ixodes-ricinus" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Ixodes ricinus</span>
            <h2>Navadni gozdni klop</h2>
            <p>
              <em>Ixodes ricinus</em>, znan kot navadni gozdni klop, je
              najpogostejša vrsta klopa v Evropi in tudi v Sloveniji ter
              predstavlja enega najpomembnejših prenašalcev nalezljivih bolezni
              pri ljudeh.
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
        </section>

        <section id="klopne-bolezni" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Klopne bolezni</span>
            <h2>Lymska borelioza in klopni meningoencefalitis</h2>
            <p>
              Klopi v Sloveniji najpogosteje prenašajo lymsko boreliozo in
              klopni meningoencefalitis. Bolezni se razlikujeta po povzročitelju
              in načinu zdravljenja, skupna pa jima je potreba po hitrem
              ukrepanju in dosledni zaščiti.
            </p>
          </div>

          <div className="disease-grid">
            <article className="disease-card">
              <h3>Lymska borelioza</h3>
              <div className="copy-flow">
                <p>
                  V Sloveniji je borelioza najpogostejša nalezljiva bolezen, ki
                  jo prenašajo klopi. Pojavlja se po celi državi in letno
                  beležimo okoli 5.000 do 7.000 zbolelih. Tveganje za okužbo je
                  največje od februarja do novembra, blage zime in vlažne
                  pomladi pa spodbujajo pojavnost klopov.
                </p>
                <p>
                  Lymsko boreliozo povzročajo bakterije iz rodu <em>Borrelia</em>.
                  Klop se z bakterijo okuži med sesanjem krvi okužene živali,
                  najpogosteje malih gozdnih sesalcev in ptic, lahko pa tudi
                  večjih sesalcev, kot so srne.
                </p>
                <p>
                  Ko okužen klop ugrizne človeka, lahko bakterijo prenese preko
                  sline v kožo. Bakterija se mora po začetku hranjenja najprej
                  aktivirati in premakniti v klopove žleze slinavke, kar običajno
                  traja 24 do 36 ur, zato zgodnja odstranitev klopa izrazito
                  zmanjša tveganje za okužbo.
                </p>
                <p>
                  Borelioza običajno poteka v treh fazah. V prvi fazi bolezni,
                  3 do 32 dni po ugrizu okuženega klopa, se lahko pojavi
                  značilna neboleča rdečina, ki se počasi širi po koži, na
                  sredini bledi in dobi obliko kolobarja. Kasneje se lahko
                  pokaže prizadetost kože, živčevja, sklepov, mišic, oči in
                  srca.
                </p>
                <p>
                  Boreliozo zdravimo z antibiotiki. Pomembna je zgodnja
                  prepoznava bolezni, saj je zdravljenje v prvi fazi praviloma
                  zelo učinkovito. Predhodna okužba ne pušča zaščite pred
                  boleznijo.
                </p>
              </div>
            </article>

            <article className="disease-card">
              <h3>Klopni meningoencefalitis</h3>
              <div className="copy-flow">
                <p>
                  Klopni meningoencefalitis (KME) je virusna bolezen osrednjega
                  živčevja, ki je v Sloveniji endemična. Letno zanj zboli okoli
                  150 ljudi.
                </p>
                <p>
                  KME povzroča virus klopnega meningoencefalitisa iz družine
                  flavivirusov. Virus se nahaja v slini okuženega klopa in se
                  lahko že v nekaj minutah po ugrizu prenese na človeka. Z
                  virusom se lahko okužimo tudi z uživanjem nepasteriziranega
                  mleka ali mlečnih izdelkov, narejenih iz mleka okužene živine.
                </p>
                <p>
                  Prvi simptomi bolezni se običajno pojavijo v 7 do 14 dneh po
                  ugrizu. Začetni simptomi so podobni gripi, nato sledi obdobje
                  brez simptomov, druga faza pa se začne s ponovnim dvigom
                  temperature in vnetjem možganskih ovojnic ter možganovine.
                </p>
                <p>
                  Pri 20 do 30 odstotkih obolelih se stanje razvije v
                  meningoencefalitis. Pri otrocih in mladostnikih ima bolezen
                  običajno lažji potek, pri starejših bolnikih pa se pogosteje
                  pojavlja resen potek bolezni s trajnimi posledicami.
                </p>
                <p>
                  Za KME nimamo zdravila, zaščitimo pa se lahko s{' '}
                  <a className="inline-link" href="#cepljenje">
                    cepljenjem
                  </a>
                  . Na voljo je podporno zdravljenje, smrtnost pa je med 0,5 in
                  2 odstotka.
                </p>
              </div>
            </article>

            <figure className="image-card">
              <img
                src={tbeMapImage}
                alt="Zemljevid razširjenosti klopnega meningoencefalitisa v Evropi in Aziji."
              />
              <figcaption>
                Razširjenost virusa klopnega meningoencefalitisa poudarja, da je
                Slovenija del širšega endemičnega prostora.
              </figcaption>
            </figure>
          </div>

          <SourceBlock sources={diseaseSources} />
        </section>

        <section id="cepljenje" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Cepljenje</span>
            <h2>Zaščita pred KME</h2>
            <p>
              KME najučinkoviteje preprečujemo s cepljenjem. V Evropi sta
              registrirani dve inaktivirani cepivi proti KME, obe varni in zelo
              učinkoviti.
            </p>
          </div>

          <div className="vaccination-grid">
            <div className="story-card">
              <div className="copy-flow">
                <p>
                  Obolevnost za klopnim meningoencefalitisom je v Sloveniji med
                  najvišjimi v Evropi, letno zboli v povprečju okrog 150 oseb,
                  delež cepljenih oseb pa je zelo nizek.
                </p>
                <p>
                  Otrok se lahko prvič cepi proti KME po dopolnjenem 1. letu
                  starosti. V letu 2026 je cepljenje brezplačno za otroke,
                  rojene leta 2016 ali kasneje, ter za odrasle, rojene med
                  letoma 1970 in 1983, ki še niso prejeli treh odmerkov cepiva.
                </p>
                <p>
                  Pri cepljenju otrok najprej sledi prvi odmerek, nato drugi čez
                  1 do 3 mesece in tretji čez 5 do 12 mesecev po drugem.
                </p>
                <p>
                  Prva revakcinacija se opravi tri leta po tretjem odmerku,
                  naslednje pa na pet let. Po 60. letu se priporoča poživitveni
                  odmerek na vsaka tri leta. Poživitveni odmerki so samoplačniški,
                  cena pa se giblje okrog 30 evrov.
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

            <figure className="image-card">
              <img
                src={vaccinationScheduleImage}
                alt="Shema cepljenja FSME-IMMUN za osnovno serijo in poživitvene odmerke."
              />
              <figcaption>
                Osnovna serija vsebuje tri odmerke, po njej pa sledijo
                revakcinacije glede na starost.
              </figcaption>
            </figure>
          </div>

          <SourceBlock sources={vaccinationSources} />
        </section>

        <section id="preventiva" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Preventiva</span>
            <h2>Kako zmanjšaš možnost ugriza</h2>
            <p>
              Kljub{' '}
              <a className="inline-link" href="#cepljenje">
                cepljenju
              </a>{' '}
              vas cepivo ščiti le pred KME, medtem ko cepivo za lymsko
              boreliozo še ne obstaja. Zato velja previdnost ob pohodu,
              kampiranju ali raziskovanju bližnjega gozda.
            </p>
          </div>

          <div className="copy-flow intro-copy">
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
        </section>

        <section id="odstranitev-klopa" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Odstranitev klopa</span>
            <h2>Postopek odstranitve</h2>
            <p>
              Če pri pregledu telesa opazimo klopa, ga čim prej previdno
              odstranimo. Pomembno je, da ga ne mažemo z oljem, kremami,
              petrolejem ali drugimi mazili.
            </p>
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
              <span className="section-kicker">Pomembno</span>
              <p>
                Klopa zavijemo v lepilni trak, ga splaknemo v školjki ali pa ga
                potopimo v alkohol oziroma razkužilo. Ne zmečkamo ga s prsti.
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
        </section>

        <section id="posebnosti-slovenije" className="content-section">
          <div className="section-header">
            <span className="section-kicker">Posebnosti Slovenije</span>
            <h2>Zakaj je tema pri nas posebej pomembna</h2>
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
        </section>
      </main>
    </div>
  )
}

export default App
