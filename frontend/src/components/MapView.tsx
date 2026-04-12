import { useEffect, useState } from 'react'
import { MapContainer, Polygon, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { MunicipalityBoundary } from '../utils/municipalityLookup'
import { loadMunicipalityBoundaries } from '../utils/municipalityLookup'

export type MapRiskLocation = {
  id: string
  municipalityCode: string
  name: string
  score: number
  level: 'Nizko' | 'Srednje' | 'Visoko'
  coordinates: [number, number]
}

type MapViewProps = {
  locations: MapRiskLocation[]
  selectedLocationId: string
  onSelectLocation: (locationId: string) => void
  diseaseLabel: string
  selectedLocation: MapRiskLocation
  levelCounts: Record<MapRiskLocation['level'], number>
  locationCount: number
  timeHorizon: string
}

type ChoroplethBoundary = MunicipalityBoundary & {
  locationId: string
  score: number
  level: MapRiskLocation['level']
}

const levelColors: Record<MapRiskLocation['level'], string> = {
  Nizko: '#3b9f76',
  Srednje: '#d49b42',
  Visoko: '#c1543f',
}

const levelClassNames: Record<MapRiskLocation['level'], string> = {
  Nizko: 'level-low',
  Srednje: 'level-medium',
  Visoko: 'level-high',
}

function buildPolygonPositions(boundary: MunicipalityBoundary) {
  const positions = boundary.polygons.map((polygon) =>
    polygon.map((ring) =>
      ring.map(([longitude, latitude]) => [latitude, longitude] as [number, number]),
    ),
  )

  return positions.length === 1 ? positions[0] : positions
}

function MapFocus({ coordinates }: { coordinates: [number, number] }) {
  const map = useMap()

  useEffect(() => {
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    map.flyTo(coordinates, 8, {
      animate: !prefersReducedMotion,
      duration: prefersReducedMotion ? 0 : 0.9,
    })
  }, [coordinates, map])

  return null
}

export function MapView({
  locations,
  selectedLocationId,
  onSelectLocation,
  diseaseLabel,
  selectedLocation,
  levelCounts,
  locationCount,
  timeHorizon,
}: MapViewProps) {
  const [boundaries, setBoundaries] = useState<ChoroplethBoundary[]>([])
  const [hoveredLocationId, setHoveredLocationId] = useState<string | null>(null)

  useEffect(() => {
    let isActive = true

    loadMunicipalityBoundaries()
      .then((payload) => {
        if (!isActive) {
          return
        }

        const locationByCode = new Map(
          locations.map((location) => [location.municipalityCode, location]),
        )
        const nextBoundaries = payload
          .map((boundary) => {
            const location = locationByCode.get(boundary.code)
            if (!location) {
              return null
            }

            return {
              ...boundary,
              locationId: location.id,
              score: location.score,
              level: location.level,
            }
          })
          .filter(
            (boundary): boundary is ChoroplethBoundary => Boolean(boundary),
          )

        setBoundaries(nextBoundaries)
      })
      .catch(() => {
        if (isActive) {
          setBoundaries([])
        }
      })

    return () => {
      isActive = false
    }
  }, [locations])

  const focusedLocation =
    locations.find((location) => location.id === selectedLocationId) ?? selectedLocation
  const previewLocation =
    locations.find((location) => location.id === hoveredLocationId) ?? focusedLocation
  const previewingHover =
    hoveredLocationId !== null && hoveredLocationId !== focusedLocation.id
  const highSignalShare = Math.round(
    (100 * levelCounts.Visoko) / Math.max(1, locationCount),
  )

  return (
    <div className="map-shell">
      <div className="map-overlay map-overlay-focus" aria-hidden="true">
        <span className="map-overlay-kicker">
          {previewingHover ? 'Preview obcine' : 'Izbrana obcina'}
        </span>
        <strong>{previewLocation.name}</strong>
        <div className="map-overlay-row">
          <span
            className={`risk-pill risk-pill-compact ${
              levelClassNames[previewLocation.level]
            }`}
          >
            {previewLocation.level}
          </span>
          <span className="map-overlay-score">{previewLocation.score}/100</span>
        </div>
        <p>
          {previewingHover
            ? 'Klikni poligon, ce zelis zakleniti fokus na tej obcini.'
            : `Signal za ${diseaseLabel.toLowerCase()} za ${timeHorizon}.`}
        </p>
      </div>

      <div className="map-overlay map-overlay-legend" aria-hidden="true">
        <span className="map-overlay-kicker">Porazdelitev</span>
        <div className="map-legend-list">
          <div className="map-legend-item">
            <span className="map-legend-dot map-legend-dot-low" />
            <span>Nizko</span>
            <strong>{levelCounts.Nizko}</strong>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-dot map-legend-dot-medium" />
            <span>Srednje</span>
            <strong>{levelCounts.Srednje}</strong>
          </div>
          <div className="map-legend-item">
            <span className="map-legend-dot map-legend-dot-high" />
            <span>Visoko</span>
            <strong>{levelCounts.Visoko}</strong>
          </div>
        </div>
        <p>{highSignalShare}% vseh obcin je trenutno v visokem pasu.</p>
      </div>

      <div className="map-overlay map-overlay-hint" aria-hidden="true">
        Hover za preview. Klik za fokus.
      </div>

      <MapContainer
        center={focusedLocation.coordinates}
        zoom={8}
        minZoom={7}
        maxZoom={10}
        maxBounds={[
          [45.2, 13.2],
          [47.1, 16.8],
        ]}
        maxBoundsViscosity={1}
        scrollWheelZoom={false}
        className="map-canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <MapFocus coordinates={focusedLocation.coordinates} />

        {boundaries.map((boundary) => {
          const isSelected = boundary.locationId === selectedLocationId
          const isHovered = boundary.locationId === hoveredLocationId
          return (
            <Polygon
              key={boundary.code}
              positions={buildPolygonPositions(boundary)}
              pathOptions={{
                color: isSelected
                  ? '#14231a'
                  : isHovered
                    ? '#22352a'
                    : levelColors[boundary.level],
                fillColor: levelColors[boundary.level],
                fillOpacity: isSelected ? 0.82 : isHovered ? 0.7 : 0.42,
                weight: isSelected ? 3.2 : isHovered ? 2.2 : 1.05,
              }}
              eventHandlers={{
                click: (event) => {
                  setHoveredLocationId(null)
                  event.target.bringToFront()
                  onSelectLocation(boundary.locationId)
                },
                mouseover: (event) => {
                  setHoveredLocationId(boundary.locationId)
                  event.target.bringToFront()
                },
                mouseout: () => {
                  setHoveredLocationId((current) =>
                    current === boundary.locationId ? null : current,
                  )
                },
              }}
            >
              <Tooltip sticky>
                <strong>{boundary.name}</strong>
                <br />
                {boundary.level} obcinski risk za {diseaseLabel.toLowerCase()}
                <br />
                Score: {boundary.score}/100
              </Tooltip>
            </Polygon>
          )
        })}
      </MapContainer>
    </div>
  )
}
