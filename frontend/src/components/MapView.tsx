import { useEffect } from 'react'
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet'

export type MapRiskLocation = {
  id: string
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

const levelColors: Record<MapRiskLocation['level'], string> = {
  Nizko: '#2f8f68',
  Srednje: '#d49845',
  Visoko: '#c24a37',
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

        {locations.map((location) => (
          <CircleMarker
            key={location.id}
            center={location.coordinates}
            pathOptions={{
              color: levelColors[location.level],
              fillColor: levelColors[location.level],
              fillOpacity: location.id === selectedLocationId ? 0.88 : 0.52,
              weight: location.id === selectedLocationId ? 2.5 : 1.5,
            }}
            radius={Math.max(6, Math.round(location.score / 10))}
            eventHandlers={{
              click: () => onSelectLocation(location.id),
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1} permanent={false}>
              <strong>{location.name}</strong>
              <br />
              {location.level} okoljsko tveganje za {diseaseLabel.toLowerCase()}
              <br />
              Relativni okoljski indeks: {location.score}/100
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
