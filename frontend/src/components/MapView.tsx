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

    map.invalidateSize()
    map.flyTo(coordinates, 8, {
      animate: !prefersReducedMotion,
      duration: prefersReducedMotion ? 0 : 0.9,
    })

    const timeoutId = window.setTimeout(() => {
      map.invalidateSize()
    }, 60)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [coordinates, map])

  return null
}

export function MapView({
  locations,
  selectedLocationId,
  onSelectLocation,
  diseaseLabel,
  selectedLocation,
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

  return (
    <div className="map-shell">
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
          return (
            <Polygon
              key={boundary.code}
              positions={buildPolygonPositions(boundary)}
              pathOptions={{
                color: isSelected ? '#14231a' : levelColors[boundary.level],
                fillColor: levelColors[boundary.level],
                fillOpacity: isSelected ? 0.8 : 0.42,
                weight: isSelected ? 3.1 : 1.05,
              }}
              eventHandlers={{
                click: (event) => {
                  event.target.bringToFront()
                  onSelectLocation(boundary.locationId)
                },
              }}
            >
              <Tooltip sticky>
                <strong>{boundary.name}</strong>
                <br />
                {boundary.level} občinsko tveganje za {diseaseLabel.toLowerCase()}
              </Tooltip>
            </Polygon>
          )
        })}
      </MapContainer>
    </div>
  )
}
