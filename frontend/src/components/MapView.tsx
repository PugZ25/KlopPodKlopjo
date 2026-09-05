import { useEffect, useMemo, useState } from 'react'
import { MapContainer, Polygon, Tooltip, useMap, ZoomControl } from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import type { MunicipalityBoundary } from '../utils/municipalityLookup'
import { loadMunicipalityBoundaries } from '../utils/municipalityLookup'
import 'leaflet/dist/leaflet.css'

export type MapRiskLocation = {
  id: string
  municipalityCode: string
  name: string
  score: number
  level: 'Nizko' | 'Srednje' | 'Visoko'
  coordinates: [number, number]
  regionName: string
}

export type MapViewProps = {
  locations: MapRiskLocation[]
  selectedLocationId: string
  onSelectLocation: (locationId: string) => void
  diseaseLabel: string
  selectedLocation: MapRiskLocation
  spatialScope: 'municipality' | 'statistical_region'
}

type PreparedBoundary = Pick<MunicipalityBoundary, 'code' | 'name'> & {
  positions: LatLngExpression[][] | LatLngExpression[][][]
}

type ChoroplethBoundary = PreparedBoundary & {
  locationId: string
  level: MapRiskLocation['level']
  regionName: string
}

const levelColors: Record<MapRiskLocation['level'], string> = {
  Nizko: '#4a9c70',
  Srednje: '#d49b42',
  Visoko: '#c1543f',
}

// The selected outline is a darkened version of its own level colour, so the
// selection still reads as low/medium/high instead of turning into a black blob.
const selectedStrokeColors: Record<MapRiskLocation['level'], string> = {
  Nizko: '#1d5c3e',
  Srednje: '#8a5a12',
  Visoko: '#7d2c1c',
}

const signalLevelLabel: Record<MapRiskLocation['level'], string> = {
  Nizko: 'Nizek',
  Srednje: 'Srednji',
  Visoko: 'Visok',
}

const SLOVENIA_BOUNDS: [[number, number], [number, number]] = [
  [45.2, 13.2],
  [47.1, 16.8],
]

// Extent of the fixed 2026 GURS asset in public/municipality-boundaries.json.
const SLOVENIA_VIEW_BOUNDS: [[number, number], [number, number]] = [
  [45.42145, 13.37548],
  [46.87666, 16.59669],
]

const SLOVENIA_CENTER: [number, number] = [46.15, 14.95]
let preparedBoundaryPromise: Promise<PreparedBoundary[]> | null = null

function buildDiseaseObjectLabel(diseaseLabel: string) {
  return diseaseLabel === 'Borelioza' ? 'boreliozo' : diseaseLabel.toLowerCase()
}

function buildPolygonPositions(
  boundary: MunicipalityBoundary,
): PreparedBoundary['positions'] {
  const positions = boundary.polygons.map((polygon) =>
    polygon.map((ring) =>
      ring.map(([longitude, latitude]) => [latitude, longitude] as [number, number]),
    ),
  )

  return positions.length === 1 ? positions[0] : positions
}

function loadPreparedBoundaries() {
  if (!preparedBoundaryPromise) {
    preparedBoundaryPromise = loadMunicipalityBoundaries().then((boundaries) =>
      boundaries.map((boundary) => ({
        code: boundary.code,
        name: boundary.name,
        positions: buildPolygonPositions(boundary),
      })),
    )
  }

  return preparedBoundaryPromise
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
    map.setMinZoom(isTouchMap ? 6 : 7)
    map.invalidateSize({ pan: false })

    if (isTouchMap) {
      map.fitBounds(SLOVENIA_VIEW_BOUNDS, {
        animate: false,
        padding: [6, 6],
        maxZoom: 7,
      })
    }
  }, [isTouchMap, map])

  useEffect(() => {
    if (isTouchMap) {
      return
    }

    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches

    map.flyTo(coordinates, map.getZoom(), {
      animate: !prefersReducedMotion,
      duration: prefersReducedMotion ? 0 : 0.9,
    })
  }, [coordinates, isTouchMap, map])

  useEffect(() => {
    if (!('ResizeObserver' in window)) {
      return
    }

    let frameId = 0
    const observer = new ResizeObserver(() => {
      window.cancelAnimationFrame(frameId)
      frameId = window.requestAnimationFrame(() => {
        map.invalidateSize({ pan: false })
      })
    })

    observer.observe(map.getContainer())

    return () => {
      observer.disconnect()
      window.cancelAnimationFrame(frameId)
    }
  }, [map])

  return null
}

function detectTouchMap() {
  if (typeof window === 'undefined') {
    return false
  }

  return (
    window.matchMedia('(max-width: 760px)').matches ||
    window.matchMedia('(hover: none), (pointer: coarse)').matches
  )
}

export function MapView({
  locations,
  selectedLocationId,
  onSelectLocation,
  diseaseLabel,
  selectedLocation,
  spatialScope,
}: MapViewProps) {
  const [preparedBoundaries, setPreparedBoundaries] = useState<PreparedBoundary[]>([])
  const [isTouchMap, setIsTouchMap] = useState(detectTouchMap)

  useEffect(() => {
    const updateTouchMode = () => {
      setIsTouchMap(detectTouchMap())
    }

    updateTouchMode()

    const viewportQuery = window.matchMedia('(max-width: 760px)')
    const pointerQuery = window.matchMedia('(hover: none), (pointer: coarse)')
    viewportQuery.addEventListener?.('change', updateTouchMode)
    pointerQuery.addEventListener?.('change', updateTouchMode)

    return () => {
      viewportQuery.removeEventListener?.('change', updateTouchMode)
      pointerQuery.removeEventListener?.('change', updateTouchMode)
    }
  }, [])

  useEffect(() => {
    let isActive = true

    loadPreparedBoundaries()
      .then((payload) => {
        if (!isActive) {
          return
        }

        setPreparedBoundaries(payload)
      })
      .catch(() => {
        if (isActive) {
          setPreparedBoundaries([])
        }
      })

    return () => {
      isActive = false
    }
  }, [])

  const boundaries = useMemo(() => {
    const locationByCode = new Map(
      locations.map((location) => [location.municipalityCode, location]),
    )

    return preparedBoundaries
      .map((boundary) => {
        const location = locationByCode.get(boundary.code)
        if (!location) {
          return null
        }

        return {
          ...boundary,
          locationId: location.id,
          level: location.level,
          regionName: location.regionName,
        }
      })
      .filter((boundary): boundary is ChoroplethBoundary => Boolean(boundary))
  }, [locations, preparedBoundaries])

  // Leaflet paints in insertion order and strokes are centred on the path, so a
  // selected polygon drawn mid-list gets its outline half-covered by whichever
  // neighbours come after it. Split it out and draw it last instead.
  const selectedBoundary = boundaries.find(
    (boundary) => boundary.locationId === selectedLocationId,
  )
  const otherBoundaries = useMemo(
    () =>
      boundaries.filter(
        (boundary) => boundary.locationId !== selectedLocationId,
      ),
    [boundaries, selectedLocationId],
  )

  function renderBoundary(boundary: ChoroplethBoundary, isSelected: boolean) {
    return (
      <Polygon
        key={boundary.code}
        positions={boundary.positions}
        smoothFactor={isSelected ? 0.4 : isTouchMap ? 1.5 : 1}
        pathOptions={{
          className: isSelected ? 'boundary-selected' : undefined,
          color: isSelected
            ? selectedStrokeColors[boundary.level]
            : levelColors[boundary.level],
          fillColor: levelColors[boundary.level],
          fillOpacity: isSelected ? 0.88 : isTouchMap ? 0.54 : 0.42,
          weight: isSelected ? (isTouchMap ? 2.2 : 2.4) : isTouchMap ? 1.1 : 1.05,
          lineJoin: 'round',
          lineCap: 'round',
        }}
        eventHandlers={{
          click: () => onSelectLocation(boundary.locationId),
        }}
      >
        {!isTouchMap ? (
          <Tooltip sticky>
            <strong>{boundary.name}</strong>
            <br />
            {signalLevelLabel[boundary.level]} signal za{' '}
            {buildDiseaseObjectLabel(diseaseLabel)}
            {spatialScope === 'statistical_region' ? (
              <>
                <br />
                Statistična regija: {boundary.regionName}
              </>
            ) : null}
          </Tooltip>
        ) : null}
      </Polygon>
    )
  }

  const focusedLocation =
    locations.find((location) => location.id === selectedLocationId) ?? selectedLocation
  const mapCenter = isTouchMap ? SLOVENIA_CENTER : focusedLocation.coordinates
  const mapZoom = isTouchMap ? 7 : 8

  return (
    <div className="map-shell">
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        minZoom={isTouchMap ? 6 : 7}
        maxZoom={11}
        maxBounds={SLOVENIA_BOUNDS}
        maxBoundsViscosity={isTouchMap ? 0.85 : 1}
        scrollWheelZoom={!isTouchMap}
        dragging
        touchZoom
        doubleClickZoom={!isTouchMap}
        zoomSnap={0.5}
        zoomDelta={0.5}
        zoomControl={false}
        attributionControl={false}
        preferCanvas={isTouchMap}
        className="map-canvas"
      >
        <MapFocus coordinates={focusedLocation.coordinates} isTouchMap={isTouchMap} />
        <ZoomControl position={isTouchMap ? 'bottomright' : 'topright'} />

        {otherBoundaries.map((boundary) => renderBoundary(boundary, false))}

        {selectedBoundary ? (
          <Polygon
            key={`casing-${selectedBoundary.code}`}
            positions={selectedBoundary.positions}
            smoothFactor={0.4}
            interactive={false}
            pathOptions={{
              className: 'boundary-casing',
              color: '#fdfefc',
              weight: isTouchMap ? 5.5 : 6,
              opacity: 0.95,
              fill: false,
              lineJoin: 'round',
              lineCap: 'round',
            }}
          />
        ) : null}

        {selectedBoundary ? renderBoundary(selectedBoundary, true) : null}

      </MapContainer>
    </div>
  )
}
