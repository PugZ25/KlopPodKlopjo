export type MunicipalityBoundary = {
  code: string
  name: string
  bbox: [number, number, number, number]
  polygons: Array<Array<Array<[number, number]>>>
}

type RawMunicipalityBoundary = {
  code: string
  name: string
  bbox: [number, number, number, number]
  polygons?: Array<Array<Array<[number, number]>>>
  ring?: Array<[number, number]>
}

let boundaryPromise: Promise<MunicipalityBoundary[]> | null = null

function normalizeMunicipalityBoundary(boundary: RawMunicipalityBoundary) {
  if (Array.isArray(boundary.polygons)) {
    return {
      code: boundary.code,
      name: boundary.name,
      bbox: boundary.bbox,
      polygons: boundary.polygons,
    } satisfies MunicipalityBoundary
  }

  if (Array.isArray(boundary.ring)) {
    return {
      code: boundary.code,
      name: boundary.name,
      bbox: boundary.bbox,
      polygons: [[boundary.ring]],
    } satisfies MunicipalityBoundary
  }

  throw new Error(`Boundary asset for ${boundary.code} is missing polygons.`)
}

export async function loadMunicipalityBoundaries() {
  if (!boundaryPromise) {
    boundaryPromise = fetch('/municipality-boundaries.json').then(
      async (response) => {
        if (!response.ok) {
          throw new Error('Boundary asset ni bil naložen.')
        }
        return ((await response.json()) as RawMunicipalityBoundary[]).map(
          normalizeMunicipalityBoundary,
        )
      },
    )
  }

  return boundaryPromise
}

function pointInBoundingBox(
  longitude: number,
  latitude: number,
  [minLongitude, minLatitude, maxLongitude, maxLatitude]: MunicipalityBoundary['bbox'],
) {
  return (
    longitude >= minLongitude &&
    longitude <= maxLongitude &&
    latitude >= minLatitude &&
    latitude <= maxLatitude
  )
}

function pointInRing(
  longitude: number,
  latitude: number,
  ring: Array<[number, number]>,
) {
  let isInside = false

  for (let currentIndex = 0, previousIndex = ring.length - 1; currentIndex < ring.length; previousIndex = currentIndex++) {
    const [currentLongitude, currentLatitude] = ring[currentIndex]
    const [previousLongitude, previousLatitude] = ring[previousIndex]

    const crossesLatitude =
      currentLatitude > latitude !== previousLatitude > latitude
    if (!crossesLatitude) {
      continue
    }

    const edgeLongitude =
      ((previousLongitude - currentLongitude) * (latitude - currentLatitude)) /
        (previousLatitude - currentLatitude) +
      currentLongitude

    if (longitude < edgeLongitude) {
      isInside = !isInside
    }
  }

  return isInside
}

function pointInPolygon(
  longitude: number,
  latitude: number,
  polygon: MunicipalityBoundary['polygons'][number],
) {
  const [outerRing, ...holes] = polygon
  if (!outerRing || !pointInRing(longitude, latitude, outerRing)) {
    return false
  }

  return !holes.some((ring) => pointInRing(longitude, latitude, ring))
}

export async function findMunicipalityByCoordinates(
  latitude: number,
  longitude: number,
) {
  const boundaries = await loadMunicipalityBoundaries()
  return (
    boundaries.find(
      (boundary) =>
        pointInBoundingBox(longitude, latitude, boundary.bbox) &&
        boundary.polygons.some((polygon) =>
          pointInPolygon(longitude, latitude, polygon),
        ),
    ) ?? null
  )
}
