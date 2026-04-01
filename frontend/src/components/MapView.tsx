import { useEffect } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { RegionRisk } from '../data/regionRisk'

type MapViewProps = {
  regions: RegionRisk[]
  selectedRegionId: string
  onSelectRegion: (regionId: string) => void
}

const levelColors: Record<RegionRisk['level'], string> = {
  Nizko: '#2f8f68',
  Srednje: '#d49845',
  Visoko: '#c24a37',
}

function MapFocus({ coordinates }: { coordinates: [number, number] }) {
  const map = useMap()

  useEffect(() => {
    map.flyTo(coordinates, 8, {
      animate: true,
      duration: 0.9,
    })
  }, [coordinates, map])

  return null
}

export function MapView({
  regions,
  selectedRegionId,
  onSelectRegion,
}: MapViewProps) {
  const selectedRegion =
    regions.find((region) => region.id === selectedRegionId) ?? regions[0]

  return (
    <div className="map-shell">
      <MapContainer
        center={selectedRegion.coordinates}
        zoom={8}
        scrollWheelZoom={false}
        className="map-canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapFocus coordinates={selectedRegion.coordinates} />

        {regions.map((region) => (
          <CircleMarker
            key={region.id}
            center={region.coordinates}
            pathOptions={{
              color: levelColors[region.level],
              fillColor: levelColors[region.level],
              fillOpacity: region.id === selectedRegionId ? 0.85 : 0.55,
              weight: region.id === selectedRegionId ? 3 : 2,
            }}
            radius={Math.max(12, Math.round(region.score / 6))}
            eventHandlers={{
              click: () => onSelectRegion(region.id),
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1} permanent={false}>
              <strong>{region.name}</strong>
              <br />
              {region.level} tveganje
              <br />
              Score: {region.score}/100
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
