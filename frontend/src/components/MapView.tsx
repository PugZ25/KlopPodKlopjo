import { useEffect, useState } from 'react'
import { MapContainer, Polygon, Tooltip, useMap, ZoomControl } from 'react-leaflet'
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
}

type ChoroplethBoundary = MunicipalityBoundary & {
  locationId: string
  level: MapRiskLocation['level']
}

const levelColors: Record<MapRiskLocation['level'], string> = {
  Nizko: '#3b9f76',
  Srednje: '#d49b42',
  Visoko: '#c1543f',
}

const SLOVENIA_BOUNDS: [[number, number], [number, number]] = [
  [45.2, 13.2],
  [47.1, 16.8],
]

const SLOVENIA_CENTER: [number, number] = [46.15, 14.95]

function buildDiseaseObjectLabel(diseaseLabel: string) {
  return diseaseLabel === 'Borelioza' ? 'boreliozo' : diseaseLabel.toLowerCase()
}

function buildPolygonPositions(boundary: MunicipalityBoundary) {
  const positions = boundary.polygons.map((polygon) =>
    polygon.map((ring) =>
      ring.map(([longitude, latitude]) => [latitude, longitude] as [number, number]),
    ),
  )

  return positions.length === 1 ? positions[0] : positions
}

function MapFocus({
  coordinates,
  isTouchMap,
}: {
  coordinates: [number, number]
  isTouchMap: boolean
}) {
  const map = useMap()

  useEffect(() => {
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    map.invalidateSize()

    if (isTouchMap) {
      map.fitBounds(SLOVENIA_BOUNDS, {
        animate: !prefersReducedMotion,
        duration: prefersReducedMotion ? 0 : 0.9,
        padding: [18, 18],
        maxZoom: 7,
      })
    } else {
      map.flyTo(coordinates, map.getZoom(), {
        animate: !prefersReducedMotion,
        duration: prefersReducedMotion ? 0 : 0.9,
      })
    }

    const timeoutId = window.setTimeout(() => {
      map.invalidateSize()
    }, 60)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [coordinates, isTouchMap, map])

  return null
}

function detectTouchMap() {
  if (typeof window === 'undefined') {
    return false
  }

  return (
    window.innerWidth <= 760 ||
    window.matchMedia('(hover: none), (pointer: coarse)').matches
  )
}

export function MapView({
  locations,
  selectedLocationId,
  onSelectLocation,
  diseaseLabel,
  selectedLocation,
}: MapViewProps) {
  const [boundaries, setBoundaries] = useState<ChoroplethBoundary[]>([])
  const [isTouchMap, setIsTouchMap] = useState(detectTouchMap)

  useEffect(() => {
    const updateTouchMode = () => {
      setIsTouchMap(detectTouchMap())
    }

    updateTouchMode()

    const coarsePointerQuery = window.matchMedia('(hover: none), (pointer: coarse)')
    coarsePointerQuery.addEventListener?.('change', updateTouchMode)
    window.addEventListener('resize', updateTouchMode)

    return () => {
      coarsePointerQuery.removeEventListener?.('change', updateTouchMode)
      window.removeEventListener('resize', updateTouchMode)
    }
  }, [])

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

        setBoundaries(
          payload
            .map((boundary) => {
              const location = locationByCode.get(boundary.code)
              if (!location) {
                return null
              }

              return {
                ...boundary,
                locationId: location.id,
                level: location.level,
              }
            })
            .filter(
              (boundary): boundary is ChoroplethBoundary => Boolean(boundary),
            ),
        )
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
  const mapCenter = isTouchMap ? SLOVENIA_CENTER : focusedLocation.coordinates
  const mapZoom = isTouchMap ? 7 : 8

  return (
    <div className="map-shell">
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        minZoom={7}
        maxZoom={11}
        maxBounds={SLOVENIA_BOUNDS}
        maxBoundsViscosity={isTouchMap ? 0.85 : 1}
        scrollWheelZoom={!isTouchMap}
        dragging
        touchZoom={isTouchMap ? 'center' : true}
        doubleClickZoom={!isTouchMap}
        zoomSnap={0.5}
        zoomDelta={0.5}
        zoomControl={false}
        attributionControl={false}
        className="map-canvas"
      >
        <MapFocus coordinates={focusedLocation.coordinates} isTouchMap={isTouchMap} />
        <ZoomControl position={isTouchMap ? 'bottomright' : 'topright'} />

        {boundaries.map((boundary) => {
          const isSelected = boundary.locationId === selectedLocationId

          return (
            <Polygon
              key={boundary.code}
              positions={buildPolygonPositions(boundary)}
              pathOptions={{
                color: isSelected ? '#14231a' : levelColors[boundary.level],
                fillColor: levelColors[boundary.level],
                fillOpacity: isSelected ? 0.86 : isTouchMap ? 0.54 : 0.42,
                weight: isSelected ? (isTouchMap ? 3.5 : 3.1) : isTouchMap ? 1.4 : 1.05,
              }}
              eventHandlers={{
                click: (event) => {
                  event.target.bringToFront()
                  onSelectLocation(boundary.locationId)
                },
              }}
            >
              {!isTouchMap ? (
                <Tooltip sticky>
                  <strong>{boundary.name}</strong>
                  <br />
                  {boundary.level} občinsko tveganje za{' '}
                  {buildDiseaseObjectLabel(diseaseLabel)}
                </Tooltip>
              ) : null}
            </Polygon>
          )
        })}
      </MapContainer>
    </div>
  )
}
