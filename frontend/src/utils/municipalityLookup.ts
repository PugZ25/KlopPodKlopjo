export type MunicipalityBoundary = {
  code: string
  name: string
  bbox: [number, number, number, number]
  ring: Array<[number, number]>
}

let boundaryPromise: Promise<MunicipalityBoundary[]> | null = null

async function loadMunicipalityBoundaries() {
  if (!boundaryPromise) {
    boundaryPromise = fetch('/municipality-boundaries.json').then(
      async (response) => {
        if (!response.ok) {
          throw new Error('Boundary asset ni bil nalozen.')
        }
        return (await response.json()) as MunicipalityBoundary[]
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
  ring: MunicipalityBoundary['ring'],
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

export async function findMunicipalityByCoordinates(
  latitude: number,
  longitude: number,
) {
  const boundaries = await loadMunicipalityBoundaries()
  return (
    boundaries.find(
      (boundary) =>
        pointInBoundingBox(longitude, latitude, boundary.bbox) &&
        pointInRing(longitude, latitude, boundary.ring),
    ) ?? null
  )
}
