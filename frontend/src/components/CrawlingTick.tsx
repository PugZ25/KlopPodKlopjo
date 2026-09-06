import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

/**
 * Decorative backdrop layer: a few ticks drawn in the logo palette, slowly
 * crawling underneath every page surface. The layer is portalled to <body> and
 * painted in the negative z-layer, so it can never cover text, controls or the
 * map — it only shows through the side gutters and the gaps between panels.
 */

const TAU = Math.PI * 2

/** how many ticks share the backdrop */
const COUNT = 3
/** px per body unit and opacity per tick, so the three never read as clones */
const VARIANTS = [
  { unit: 19, tint: 1 },
  { unit: 15, tint: 0.78 },
  { unit: 17, tint: 0.9 },
]
/** css px of the square canvas that carries one sprite around the viewport */
const SPRITE = 88
/** how close two ticks drift before they steer apart */
const SPACING = 150

/** body units of travel that make up one full leg cycle */
const STRIDE = 0.62
/** share of a leg cycle a foot stays planted on the ground */
const DUTY = 0.62
const FEMUR = 0.68
const TIBIA = 0.76

/** logo palette: #252a0e shell ink, #b4481c idiosoma */
const INK = '37, 42, 14'
const SHELL = '180, 72, 28'

const LEG_ALPHA = 0.08
const SHIELD_ALPHA = 0.095
const BODY_ALPHA = 0.095
const SHADE_ALPHA = 0.04

/** leg attachment and resting foot target, body-local, for the left side */
const LEG_PAIRS = [
  { baseX: 0.3, baseY: 0.24, homeX: 1.12, homeY: 0.98 },
  { baseX: 0.16, baseY: 0.32, homeX: 0.52, homeY: 1.3 },
  { baseX: 0, baseY: 0.34, homeX: -0.28, homeY: 1.34 },
  { baseX: -0.18, baseY: 0.3, homeX: -1.02, homeY: 1.1 },
]

type Leg = {
  baseX: number
  baseY: number
  homeX: number
  homeY: number
  /** body-local direction the knee is pushed towards, away from the midline */
  poleX: number
  poleY: number
  /** gait offset in cycles */
  phase: number
  swinging: boolean
  footX: number
  footY: number
  plantX: number
  plantY: number
  fromX: number
  fromY: number
  toX: number
  toY: number
}

type Tick = {
  canvas: HTMLCanvasElement
  ctx: CanvasRenderingContext2D
  legs: Leg[]
  /** px per body unit */
  unit: number
  tint: number
  femur: number
  tibia: number
  reach: number
  /** which gutter this one favours, or -1 while the layout has none */
  lane: number
  /** phase offset that keeps the wander noise out of sync with the others */
  seed: number
  x: number
  y: number
  heading: number
  speed: number
  cruise: number
  resting: boolean
  stateTimer: number
  gait: number
}

type World = {
  width: number
  height: number
  ratio: number
  /** x positions of the side gutters the ticks are gently drawn towards */
  lanes: number[]
}

function createLegs(): Leg[] {
  return LEG_PAIRS.flatMap((pair, index) =>
    [-1, 1].map((side) => {
      const baseY = pair.baseY * side
      const homeY = pair.homeY * side
      // The knee always bulges away from the midline. Pinning that direction in
      // body space keeps the joint from flipping through the shell when a foot
      // swings past its attachment point.
      const spanX = pair.homeX - pair.baseX
      const spanY = homeY - baseY
      const length = Math.hypot(spanX, spanY)
      // Of the two normals to the resting leg, keep the one facing away from
      // the midline.
      const normalX = -spanY / length
      const normalY = spanX / length
      const outward = Math.sign(normalY * side) || 1

      return {
        baseX: pair.baseX,
        baseY,
        homeX: pair.homeX,
        homeY,
        poleX: normalX * outward,
        poleY: normalY * outward,
        // Alternating tetrapod, nudged into a slight front-to-back wave.
        phase: ((index % 2) * 0.5 + (side > 0 ? 0.5 : 0) + index * 0.02) % 1,
        swinging: false,
        footX: 0,
        footY: 0,
        plantX: 0,
        plantY: 0,
        fromX: 0,
        fromY: 0,
        toX: 0,
        toY: 0,
      }
    }),
  )
}

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function wrapAngle(angle: number) {
  return angle - TAU * Math.round(angle / TAU)
}

function clamp(value: number, min: number, max: number) {
  return value < min ? min : value > max ? max : value
}

function createTick(canvas: HTMLCanvasElement, index: number): Tick | null {
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return null
  }

  const variant = VARIANTS[index % VARIANTS.length]
  return {
    canvas,
    ctx,
    legs: createLegs(),
    unit: variant.unit,
    tint: variant.tint,
    femur: FEMUR * variant.unit,
    tibia: TIBIA * variant.unit,
    reach: (FEMUR + TIBIA) * variant.unit * 0.985,
    lane: -1,
    seed: randomBetween(0, TAU),
    x: 0,
    y: 0,
    heading: randomBetween(0, TAU),
    speed: 0,
    cruise: randomBetween(12, 19),
    resting: true,
    stateTimer: randomBetween(0.6, 2.4),
    gait: randomBetween(0, 1),
  }
}

/** Sets every foot down at its resting position around the current body pose. */
function plantFeet(tick: Tick) {
  const forwardX = Math.cos(tick.heading)
  const forwardY = Math.sin(tick.heading)

  for (const leg of tick.legs) {
    const homeX =
      tick.x + leg.homeX * tick.unit * forwardX - leg.homeY * tick.unit * forwardY
    const homeY =
      tick.y + leg.homeX * tick.unit * forwardY + leg.homeY * tick.unit * forwardX
    leg.footX = homeX
    leg.footY = homeY
    leg.plantX = homeX
    leg.plantY = homeY
    leg.fromX = homeX
    leg.fromY = homeY
    leg.toX = homeX
    leg.toY = homeY
  }
}

function updateTick(
  tick: Tick,
  world: World,
  others: Tick[],
  dt: number,
  clock: number,
) {
  tick.stateTimer -= dt
  if (tick.stateTimer <= 0) {
    tick.resting = !tick.resting
    tick.stateTimer = tick.resting ? randomBetween(1.6, 4.8) : randomBetween(5, 13)
    if (!tick.resting) {
      tick.cruise = randomBetween(11, 20)
    }
  }

  const wanted = tick.resting
    ? 0
    : tick.cruise * (0.84 + 0.16 * Math.sin(clock * 0.63 + tick.seed))
  tick.speed += (wanted - tick.speed) * Math.min(1, dt * 2.2)

  // Steer as a sum of vectors: keep going, drift on slow noise, back away from
  // the viewport edges, lean towards an assigned side gutter, and give the
  // other ticks a wide berth.
  const wander =
    Math.sin(clock * 0.37 + tick.seed) * 0.6 +
    Math.sin(clock * 0.13 + tick.seed * 1.7) * 0.45 +
    Math.sin(clock * 0.71 + tick.seed * 2.3) * 0.2

  let steerX = Math.cos(tick.heading) - Math.sin(tick.heading) * wander * 0.55
  let steerY = Math.sin(tick.heading) + Math.cos(tick.heading) * wander * 0.55

  const pad = SPRITE * 0.5 + 26
  if (tick.x < pad) {
    steerX += ((pad - tick.x) / pad) * 2.4
  } else if (tick.x > world.width - pad) {
    steerX -= ((tick.x - (world.width - pad)) / pad) * 2.4
  }
  if (tick.y < pad) {
    steerY += ((pad - tick.y) / pad) * 2.4
  } else if (tick.y > world.height - pad) {
    steerY -= ((tick.y - (world.height - pad)) / pad) * 2.4
  }

  if (tick.lane >= 0) {
    steerX += clamp((world.lanes[tick.lane] - tick.x) / 240, -1, 1) * 0.45
  }

  for (const other of others) {
    if (other === tick) {
      continue
    }
    const awayX = tick.x - other.x
    const awayY = tick.y - other.y
    const gap = Math.hypot(awayX, awayY)
    if (gap < SPACING && gap > 0.001) {
      const push = (1 - gap / SPACING) * 1.8
      steerX += (awayX / gap) * push
      steerY += (awayY / gap) * push
    }
  }

  const difference = wrapAngle(Math.atan2(steerY, steerX) - tick.heading)
  const agility = (0.35 + 0.65 * Math.min(1, tick.speed / 14)) * 1.1 * dt
  tick.heading += clamp(difference, -agility, agility)

  const moved = tick.speed * dt
  tick.x += Math.cos(tick.heading) * moved
  tick.y += Math.sin(tick.heading) * moved
  tick.gait += moved / (STRIDE * tick.unit)
}

function updateLegs(
  tick: Tick,
  bodyX: number,
  bodyY: number,
  forwardX: number,
  forwardY: number,
) {
  const lead = STRIDE * tick.unit * 0.38

  for (const leg of tick.legs) {
    const homeX =
      bodyX + leg.homeX * tick.unit * forwardX - leg.homeY * tick.unit * forwardY
    const homeY =
      bodyY + leg.homeX * tick.unit * forwardY + leg.homeY * tick.unit * forwardX

    const cycle = tick.gait + leg.phase
    const progress = cycle - Math.floor(cycle)
    const swinging = progress >= DUTY

    if (swinging && !leg.swinging) {
      leg.fromX = leg.plantX
      leg.fromY = leg.plantY
      leg.toX = homeX + forwardX * lead
      leg.toY = homeY + forwardY * lead
    } else if (!swinging && leg.swinging) {
      leg.plantX = leg.toX
      leg.plantY = leg.toY
    }
    leg.swinging = swinging

    if (swinging) {
      const t = (progress - DUTY) / (1 - DUTY)
      const eased = t * t * (3 - 2 * t)
      // A lifted foot arcs a little outboard, which reads as height from above.
      const arc = Math.sin(t * Math.PI) * tick.unit * 0.12 * Math.sign(leg.homeY)
      leg.footX = leg.fromX + (leg.toX - leg.fromX) * eased - forwardY * arc
      leg.footY = leg.fromY + (leg.toY - leg.fromY) * eased + forwardX * arc
    } else {
      leg.footX = leg.plantX
      leg.footY = leg.plantY
    }
  }
}

function drawLegs(
  tick: Tick,
  originX: number,
  originY: number,
  bodyX: number,
  bodyY: number,
  forwardX: number,
  forwardY: number,
) {
  const { ctx, unit, femur, tibia } = tick

  ctx.lineCap = 'round'
  ctx.strokeStyle = `rgba(${INK}, ${LEG_ALPHA * tick.tint})`

  for (const leg of tick.legs) {
    const baseX = bodyX + leg.baseX * unit * forwardX - leg.baseY * unit * forwardY
    const baseY = bodyY + leg.baseX * unit * forwardY + leg.baseY * unit * forwardX

    const deltaX = leg.footX - baseX
    const deltaY = leg.footY - baseY
    const distance = Math.max(Math.hypot(deltaX, deltaY), 0.001)
    const span = Math.min(distance, tick.reach)
    const unitX = deltaX / distance
    const unitY = deltaY / distance

    // Two-bone solve. Of the two mirrored knee positions, take the one on the
    // side the leg's outward pole points to.
    const poleX = leg.poleX * forwardX - leg.poleY * forwardY
    const poleY = leg.poleX * forwardY + leg.poleY * forwardX
    const bend = unitX * poleY - unitY * poleX >= 0 ? 1 : -1

    const along = (femur * femur - tibia * tibia + span * span) / (2 * span)
    const lift = Math.sqrt(Math.max(0, femur * femur - along * along)) * bend
    const kneeX = baseX + unitX * along - unitY * lift - originX
    const kneeY = baseY + unitY * along + unitX * lift - originY
    const tipX = baseX + unitX * span - originX
    const tipY = baseY + unitY * span - originY

    ctx.lineWidth = unit * 0.105
    ctx.beginPath()
    ctx.moveTo(baseX - originX, baseY - originY)
    ctx.lineTo(kneeX, kneeY)
    ctx.stroke()

    // The tibia bows back against the knee, so each leg finishes in the hooked
    // tip the logo draws rather than a straight spike.
    const curlX = (tipY - kneeY) * 0.1 * bend
    const curlY = -(tipX - kneeX) * 0.1 * bend
    ctx.lineWidth = unit * 0.072
    ctx.beginPath()
    ctx.moveTo(kneeX, kneeY)
    ctx.quadraticCurveTo(
      (kneeX + tipX) / 2 + curlX,
      (kneeY + tipY) / 2 + curlY,
      tipX,
      tipY,
    )
    ctx.stroke()
  }
}

/**
 * Paints the shell, shield and mouthparts. `shell` and `head` are separate so
 * the same outline can be stamped as a solid mask before the real colours.
 */
function traceBody(
  tick: Tick,
  bodyAngle: number,
  offsetX: number,
  offsetY: number,
  shell: string,
  head: string,
) {
  const { ctx } = tick

  ctx.save()
  ctx.translate(offsetX, offsetY)
  ctx.rotate(bodyAngle)
  ctx.scale(tick.unit, tick.unit)

  // Idiosoma: the rounded shell, widest just behind the shield.
  ctx.fillStyle = shell
  ctx.beginPath()
  ctx.moveTo(0.28, 0)
  ctx.bezierCurveTo(0.28, -0.4, 0.02, -0.59, -0.27, -0.58)
  ctx.bezierCurveTo(-0.66, -0.57, -0.84, -0.3, -0.84, 0)
  ctx.bezierCurveTo(-0.84, 0.3, -0.66, 0.57, -0.27, 0.58)
  ctx.bezierCurveTo(0.02, 0.59, 0.28, 0.4, 0.28, 0)
  ctx.fill()

  ctx.fillStyle = head
  ctx.strokeStyle = head

  // Scutum: the dark shield over the front of the shell.
  ctx.beginPath()
  ctx.ellipse(0.16, 0, 0.32, 0.34, 0, 0, TAU)
  ctx.fill()

  // Capitulum: a stubby basis carrying the palps and the hypostome.
  ctx.beginPath()
  ctx.ellipse(0.46, 0, 0.13, 0.14, 0, 0, TAU)
  ctx.fill()

  ctx.beginPath()
  ctx.moveTo(0.5, -0.06)
  ctx.lineTo(0.72, 0)
  ctx.lineTo(0.5, 0.06)
  ctx.closePath()
  ctx.fill()

  ctx.lineWidth = 0.07
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(0.5, -0.1)
  ctx.lineTo(0.62, -0.15)
  ctx.moveTo(0.5, 0.1)
  ctx.lineTo(0.62, 0.15)
  ctx.stroke()

  ctx.restore()
}

function drawTick(tick: Tick, world: World, clock: number) {
  const { ctx, unit } = tick
  const energy = Math.min(1, tick.speed / 14)
  // The body rocks a little over the gait and settles when the tick stops.
  const sway = Math.sin(tick.gait * TAU * 2) * unit * 0.05 * energy
  const bodyAngle =
    tick.heading +
    Math.sin(tick.gait * TAU) * 0.035 * energy +
    Math.sin(clock * 0.9 + tick.seed) * 0.012 * (1 - energy)
  const bodyX = tick.x - Math.sin(tick.heading) * sway
  const bodyY = tick.y + Math.cos(tick.heading) * sway
  const forwardX = Math.cos(bodyAngle)
  const forwardY = Math.sin(bodyAngle)

  updateLegs(tick, bodyX, bodyY, forwardX, forwardY)

  const originX = Math.round(tick.x - SPRITE / 2)
  const originY = Math.round(tick.y - SPRITE / 2)
  tick.canvas.style.transform = `translate3d(${originX}px, ${originY}px, 0)`

  ctx.setTransform(world.ratio, 0, 0, world.ratio, 0, 0)
  ctx.clearRect(0, 0, SPRITE, SPRITE)
  // A hair of blur keeps the thin legs from reading as crisp UI at this size.
  ctx.filter = 'blur(0.4px)'

  drawLegs(tick, originX, originY, bodyX, bodyY, forwardX, forwardY)

  // Punch the body out of the leg layer first, so overlapping limbs never stack
  // into a darker patch where the shell should read as one flat shape.
  ctx.globalCompositeOperation = 'destination-out'
  traceBody(tick, bodyAngle, bodyX - originX, bodyY - originY, '#000', '#000')
  ctx.globalCompositeOperation = 'source-over'

  // Soft contact shade, laid down once the body footprint is clear.
  const shade = ctx.createRadialGradient(
    bodyX - originX,
    bodyY - originY,
    unit * 0.15,
    bodyX - originX,
    bodyY - originY,
    unit * 1.15,
  )
  shade.addColorStop(0, `rgba(${INK}, ${SHADE_ALPHA * tick.tint})`)
  shade.addColorStop(1, `rgba(${INK}, 0)`)
  ctx.fillStyle = shade
  ctx.fillRect(0, 0, SPRITE, SPRITE)

  traceBody(
    tick,
    bodyAngle,
    bodyX - originX,
    bodyY - originY,
    `rgba(${SHELL}, ${BODY_ALPHA * tick.tint})`,
    `rgba(${INK}, ${SHIELD_ALPHA * tick.tint})`,
  )

  ctx.filter = 'none'
}

function startColony(canvases: HTMLCanvasElement[]) {
  const ticks = canvases
    .map((canvas, index) => createTick(canvas, index))
    .filter((tick): tick is Tick => tick !== null)

  if (ticks.length === 0) {
    return () => {}
  }

  const world: World = {
    width: window.innerWidth,
    height: window.innerHeight,
    ratio: Math.min(window.devicePixelRatio || 1, 2),
    lanes: [],
  }

  let clock = 0
  let previous = 0
  let frameId = 0

  function measureLanes() {
    const shell = document.querySelector('.app-shell')
    world.lanes = []
    if (shell) {
      // The page is one centred column, so the visible backdrop is whatever
      // sits beside it. Only bother with a gutter wide enough to hold a sprite.
      const rect = shell.getBoundingClientRect()
      if (rect.left > SPRITE * 0.9) {
        world.lanes.push(rect.left / 2)
      }
      if (world.width - rect.right > SPRITE * 0.9) {
        world.lanes.push((world.width + rect.right) / 2)
      }
    }

    // Share the gutters out rather than letting the colony queue up in one.
    ticks.forEach((tick, index) => {
      tick.lane = world.lanes.length > 0 ? index % world.lanes.length : -1
    })
  }

  function resize() {
    world.width = window.innerWidth
    world.height = window.innerHeight
    world.ratio = Math.min(window.devicePixelRatio || 1, 2)
    measureLanes()

    const pad = SPRITE * 0.5 + 12
    for (const tick of ticks) {
      tick.canvas.width = Math.round(SPRITE * world.ratio)
      tick.canvas.height = Math.round(SPRITE * world.ratio)
      tick.canvas.style.width = `${SPRITE}px`
      tick.canvas.style.height = `${SPRITE}px`

      const nextX = clamp(tick.x, pad, Math.max(pad, world.width - pad))
      const nextY = clamp(tick.y, pad, Math.max(pad, world.height - pad))
      if (nextX !== tick.x || nextY !== tick.y) {
        // The body was nudged back into view, so the planted feet no longer
        // belong to it — set them down again around the new position.
        tick.x = nextX
        tick.y = nextY
        plantFeet(tick)
      }
    }
  }

  function frame(now: number) {
    const dt = Math.min((now - previous) / 1000, 0.05)
    previous = now
    clock += dt

    for (const tick of ticks) {
      updateTick(tick, world, ticks, dt, clock)
    }
    for (const tick of ticks) {
      drawTick(tick, world, clock)
    }

    frameId = window.requestAnimationFrame(frame)
  }

  function start() {
    if (frameId) {
      return
    }
    previous = performance.now()
    frameId = window.requestAnimationFrame(frame)
  }

  function stop() {
    if (frameId) {
      window.cancelAnimationFrame(frameId)
      frameId = 0
    }
  }

  function handleVisibility() {
    if (document.hidden) {
      stop()
    } else {
      start()
    }
  }

  resize()

  // Start each one in its own gutter and its own band of the page, so they read
  // as scattered rather than as a swarm.
  const pad = SPRITE * 0.5 + 12
  const reveals = ticks.map((tick, index) => {
    const lane = tick.lane >= 0 ? world.lanes[tick.lane] : null
    tick.x = clamp(
      lane ?? world.width * (0.2 + 0.28 * index),
      pad,
      Math.max(pad, world.width - pad),
    )
    tick.y = clamp(
      world.height * (0.22 + 0.27 * index) + randomBetween(-40, 40),
      pad,
      Math.max(pad, world.height - pad),
    )
    plantFeet(tick)
    drawTick(tick, world, 0)

    return window.setTimeout(
      () => {
        tick.canvas.dataset.visible = 'true'
      },
      240 + index * 420,
    )
  })

  window.addEventListener('resize', resize)
  document.addEventListener('visibilitychange', handleVisibility)
  start()

  return () => {
    stop()
    reveals.forEach(window.clearTimeout)
    window.removeEventListener('resize', resize)
    document.removeEventListener('visibilitychange', handleVisibility)
  }
}

export default function CrawlingTick() {
  const [layer, setLayer] = useState<HTMLDivElement | null>(null)
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setEnabled(!query.matches)

    sync()
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    if (!layer) {
      return
    }

    return startColony(Array.from(layer.querySelectorAll('canvas')))
  }, [layer])

  if (!enabled) {
    return null
  }

  return createPortal(
    <div className="tick-layer" ref={setLayer} aria-hidden="true">
      {Array.from({ length: COUNT }, (_, index) => (
        <canvas key={index} className="tick-layer-sprite" />
      ))}
    </div>,
    document.body,
  )
}
