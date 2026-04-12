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
}: MapViewProps) {
  const [boundaries, setBoundaries] = useState<ChoroplethBoundary[]>([])

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

  const selectedLocation =
    locations.find((location) => location.id === selectedLocationId) ?? locations[0]

  return (
    <div className="map-shell">
      <MapContainer
        center={selectedLocation.coordinates}
        zoom={8}
        scrollWheelZoom={false}
        className="map-canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapFocus coordinates={selectedLocation.coordinates} />

        {boundaries.map((boundary) => {
          const isSelected = boundary.locationId === selectedLocationId
          return (
            <Polygon
              key={boundary.code}
              positions={buildPolygonPositions(boundary)}
              pathOptions={{
                color: isSelected ? '#14231a' : levelColors[boundary.level],
                fillColor: levelColors[boundary.level],
                fillOpacity: isSelected ? 0.74 : 0.48,
                weight: isSelected ? 2.8 : 1.1,
              }}
              eventHandlers={{
                click: () => onSelectLocation(boundary.locationId),
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
