/**
 * The space scenery: starfield, planets, the satellite and the carrier waves.
 *
 * Everything is procedural — canvas, SVG gradients and SVG turbulence — so
 * there is no image to fetch and the page renders identically on a machine
 * that has never been online.  All motion stops under prefers-reduced-motion
 * and while the tab is hidden.
 */
import { useEffect, useId, useRef } from 'react'
import type { Palette } from '../lib/missions'

export const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Run `frame` on every animation frame while the canvas is on screen. */
function useAnimatedCanvas(
  setup: (cv: HTMLCanvasElement) => (t: number) => void,
  fps = 60,
) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    let draw = setup(cv)
    let raf = 0
    let last = 0
    let visible = true
    const still = reducedMotion()

    const resize = () => {
      draw = setup(cv)
      draw(performance.now())
    }
    const ro = new ResizeObserver(resize)
    ro.observe(cv)
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting })
    io.observe(cv)

    const loop = (t: number) => {
      raf = requestAnimationFrame(loop)
      if (!visible || document.hidden || t - last < 1000 / fps) return
      last = t
      draw(t)
    }
    if (still) draw(0)
    else raf = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return ref
}

function sizeCanvas(cv: HTMLCanvasElement) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const r = cv.getBoundingClientRect()
  cv.width = Math.max(1, Math.floor(r.width * dpr))
  cv.height = Math.max(1, Math.floor(r.height * dpr))
  const ctx = cv.getContext('2d')!
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return { ctx, w: r.width, h: r.height }
}

/** Seeded PRNG so the sky is the same on every load. */
export function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ------------------------------------------------------------------ starfield

export function Starfield() {
  const ref = useAnimatedCanvas((cv) => {
    const { ctx, w, h } = sizeCanvas(cv)
    const rand = rng(1187)
    const n = Math.round((w * h) / 2600)
    const stars = Array.from({ length: n }, () => ({
      x: rand() * w,
      y: rand() * h,
      r: rand() < 0.93 ? 0.35 + rand() * 0.7 : 1 + rand() * 0.8,
      a: 0.25 + rand() * 0.75,
      tw: 0.4 + rand() * 1.8,
      ph: rand() * Math.PI * 2,
      hue: rand() < 0.2 ? 'rgba(255,214,190,' : rand() < 0.4 ? 'rgba(190,205,255,' : 'rgba(255,255,255,',
    }))
    const sparkles = Array.from({ length: Math.max(6, Math.round(n / 90)) }, () => ({
      x: rand() * w, y: rand() * h, s: 6 + rand() * 12, ph: rand() * 6.28,
    }))
    return (t) => {
      ctx.clearRect(0, 0, w, h)
      const time = t / 1000
      for (const s of stars) {
        const k = 0.65 + 0.35 * Math.sin(time * s.tw + s.ph)
        ctx.fillStyle = `${s.hue}${(s.a * k).toFixed(3)})`
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fill()
      }
      // Four-point sparkles, the lens flare of a bright star.
      for (const p of sparkles) {
        const k = 0.55 + 0.45 * Math.sin(time * 0.9 + p.ph)
        const s = p.s * (0.8 + 0.2 * k)
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, s * 0.6)
        g.addColorStop(0, `rgba(215,220,255,${0.5 * k})`)
        g.addColorStop(1, 'rgba(160,150,255,0)')
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(p.x, p.y, s * 0.6, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = `rgba(225,228,255,${0.75 * k})`
        ctx.lineWidth = 0.8
        ctx.beginPath()
        ctx.moveTo(p.x - s, p.y); ctx.lineTo(p.x + s, p.y)
        ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x, p.y + s)
        ctx.stroke()
      }
    }
  }, 24)
  return <canvas ref={ref} className="starfield" aria-hidden="true" />
}

// ------------------------------------------------------------ carrier waves

/**
 * Three phase-modulated carriers drifting across the hero.
 *
 * The top trace really is PSK: the carrier phase jumps by a multiple of π/2 at
 * every symbol boundary, which is exactly what SHRUTI has to discover blind.
 */
export function CarrierWaves() {
  const ref = useAnimatedCanvas((cv) => {
    const { ctx, w, h } = sizeCanvas(cv)
    const rand = rng(77)
    const phases = Array.from({ length: 512 }, () => Math.floor(rand() * 4) * (Math.PI / 2))
    const traces = [
      { y: 0.5, amp: 0.13, cyc: 34, sym: 120, speed: 38, col: '169,180,255', lw: 1.6, psk: true },
      { y: 0.56, amp: 0.08, cyc: 21, sym: 0, speed: 22, col: '217,70,239', lw: 1.1, psk: false },
      { y: 0.45, amp: 0.06, cyc: 52, sym: 0, speed: 55, col: '94,234,212', lw: 0.9, psk: false },
    ]
    return (t) => {
      ctx.clearRect(0, 0, w, h)
      const time = t / 1000
      for (const tr of traces) {
        const shift = time * tr.speed
        for (const pass of [0, 1]) {
          ctx.beginPath()
          for (let x = 0; x <= w; x += 2) {
            const u = x + shift
            const env = Math.sin((Math.PI * x) / w) ** 1.6
            const phi = tr.psk ? phases[Math.floor(u / tr.sym) & 511] : 0
            const y = h * tr.y + env * h * tr.amp *
              Math.sin((2 * Math.PI * u) / tr.cyc + phi) * (tr.psk ? 1 : 0.8 + 0.2 * Math.sin(time + x / 300))
            x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
          }
          ctx.strokeStyle = pass === 0 ? `rgba(${tr.col},0.08)` : `rgba(${tr.col},0.55)`
          ctx.lineWidth = pass === 0 ? tr.lw * 5 : tr.lw
          ctx.stroke()
        }
      }
    }
  }, 40)
  return <canvas ref={ref} className="carrier-waves" aria-hidden="true" />
}

// -------------------------------------------------------------------- planets

export const PALETTES: Record<Palette, { hi: string; mid: string; lo: string; tex: string; glow: string; rim: string }> = {
  mars: { hi: '#ffb27a', mid: '#d0592b', lo: '#4a1407', tex: '#5c1a08', glow: '#ff8a4c', rim: '#ffd0a8' },
  earth: { hi: '#8fd3ff', mid: '#2463b8', lo: '#07163b', tex: '#1d7a62', glow: '#6ab6ff', rim: '#c8e6ff' },
  violet: { hi: '#b9c4ff', mid: '#4d4fc9', lo: '#0c0b35', tex: '#a15b3a', glow: '#8b7bff', rim: '#ffc4a0' },
}

/**
 * A lit sphere with a procedural surface.  `grid` overlays a slowly turning
 * latitude/longitude wireframe — the instrument's view of the body.
 */
export function Planet({
  palette, size, seed = 3, grid = false, className = '', rings = false,
}: {
  palette: Palette
  /** Pixels, or any CSS length such as '100%'. */
  size: number | string
  seed?: number
  grid?: boolean
  className?: string
  rings?: boolean
}) {
  const id = useId().replace(/:/g, '')
  const c = PALETTES[palette]
  return (
    <svg className={`planet ${className}`} width={size} height={size} viewBox="-60 -60 520 520" aria-hidden="true">
      <defs>
        <radialGradient id={`body${id}`} cx="34%" cy="30%" r="78%">
          <stop offset="0" stopColor={c.hi} />
          <stop offset=".45" stopColor={c.mid} />
          <stop offset="1" stopColor={c.lo} />
        </radialGradient>
        <radialGradient id={`shade${id}`} cx="30%" cy="26%" r="85%">
          <stop offset=".45" stopColor="#000" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".78" />
        </radialGradient>
        <radialGradient id={`glow${id}`} cx="50%" cy="50%" r="50%">
          <stop offset=".72" stopColor={c.glow} stopOpacity=".5" />
          <stop offset="1" stopColor={c.glow} stopOpacity="0" />
        </radialGradient>
        <filter id={`tex${id}`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency={palette === 'earth' ? '0.011 0.016' : '0.018 0.03'} numOctaves="5" seed={seed} />
          <feColorMatrix type="matrix" values={`0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 ${palette === 'earth' ? 5.5 : 3.2} ${palette === 'earth' ? -2.5 : -1.3}`} />
          <feComposite in2="SourceGraphic" operator="in" />
        </filter>
        <clipPath id={`clip${id}`}><circle cx="200" cy="200" r="200" /></clipPath>
        <linearGradient id={`rim${id}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor={c.rim} stopOpacity=".9" />
          <stop offset=".35" stopColor={c.rim} stopOpacity="0" />
        </linearGradient>
      </defs>
      <circle cx="200" cy="200" r="250" fill={`url(#glow${id})`} />
      {rings && (
        <ellipse cx="200" cy="200" rx="300" ry="62" fill="none" stroke={c.rim} strokeOpacity=".28" strokeWidth="10" transform="rotate(-18 200 200)" />
      )}
      <g clipPath={`url(#clip${id})`}>
        <circle cx="200" cy="200" r="200" fill={`url(#body${id})`} />
        <rect x="0" y="0" width="400" height="400" fill={c.tex} filter={`url(#tex${id})`} opacity={palette === 'earth' ? 0.95 : 0.55} />
        {grid && (
          <g className="planet-grid" stroke="#fff" strokeOpacity=".16" fill="none" strokeWidth="1.2">
            {[-60, -30, 0, 30, 60].map((lat) => {
              const y = 200 - 200 * Math.sin((lat * Math.PI) / 180)
              const rx = 200 * Math.cos((lat * Math.PI) / 180)
              return <ellipse key={lat} cx="200" cy={y} rx={rx} ry={rx * 0.16} />
            })}
            <g className="planet-meridians">
              {[0, 30, 60, 90, 120, 150].map((lon) => (
                <ellipse key={lon} cx="200" cy="200" rx={Math.max(2, 200 * Math.abs(Math.cos((lon * Math.PI) / 180)))} ry="200" />
              ))}
            </g>
          </g>
        )}
        <circle cx="200" cy="200" r="200" fill={`url(#shade${id})`} />
        <circle cx="200" cy="200" r="198" fill="none" stroke={`url(#rim${id})`} strokeWidth="5" />
      </g>
      {rings && (
        <path d="M -95 290 A 300 62 0 0 0 495 110" transform="rotate(-18 200 200)" fill="none" stroke={c.rim} strokeOpacity=".35" strokeWidth="10" />
      )}
    </svg>
  )
}

// ------------------------------------------------------------------ satellite

/** A relay satellite, transmitting.  The arcs are the signal we are chasing. */
export function SatelliteArt({ className = '' }: { className?: string }) {
  return (
    <svg className={`satellite ${className}`} viewBox="0 0 320 260" aria-hidden="true">
      <g className="sat-waves" fill="none" stroke="#a9b4ff" strokeWidth="2" strokeLinecap="round">
        <path d="M 163.5 181.6 A 26 26 0 0 1 142.3 159.6" />
        <path d="M 159.3 205.2 A 50 50 0 0 1 118.5 163.0" />
        <path d="M 155.2 228.9 A 74 74 0 0 1 94.7 166.3" />
        <path d="M 151.0 252.5 A 98 98 0 0 1 71.0 169.6" />
      </g>
      <g className="sat-body" transform="rotate(28 190 110)">
        {[60, 228].map((x0) => (
          <g key={x0}>
            <rect x={x0} y="92" width="92" height="36" rx="3" fill="#1b2150" stroke="#8fa0ff" strokeWidth="1.5" />
            {[1, 2, 3].map((i) => (
              <line key={i} x1={x0 + 23 * i} y1="92" x2={x0 + 23 * i} y2="128" stroke="#8fa0ff" strokeOpacity=".6" />
            ))}
            <line x1={x0} y1="110" x2={x0 + 92} y2="110" stroke="#8fa0ff" strokeOpacity=".6" />
          </g>
        ))}
        <line x1="152" y1="110" x2="228" y2="110" stroke="#cfd6ff" strokeWidth="3" />
        <rect x="166" y="86" width="48" height="48" rx="6" fill="#d7a64a" stroke="#ffe0a3" strokeWidth="1.5" />
        <path d="M166 100h48M166 120h48" stroke="#8a5d17" strokeOpacity=".6" />
        <line x1="190" y1="86" x2="190" y2="70" stroke="#cfd6ff" strokeWidth="1.5" />
        <circle cx="190" cy="68" r="3" fill="#ff9a5c" className="sat-beacon" />
        <path d="M184 134 l6 12 l6 -12" fill="none" stroke="#cfd6ff" strokeWidth="2" />
        <path d="M172 146 a 18 11 0 0 0 36 0 z" fill="#e8ecff" stroke="#fff" strokeWidth="1" />
      </g>
    </svg>
  )
}

// --------------------------------------------------------------------- rocket

/** A small launch, for news that is on its way. */
export function RocketArt() {
  return (
    <svg className="rocket" viewBox="0 0 160 150" aria-hidden="true">
      <defs>
        <linearGradient id="rk-body" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#b9c2ff" />
        </linearGradient>
        <linearGradient id="rk-flame" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff4c7" />
          <stop offset=".45" stopColor="#ffb36b" />
          <stop offset="1" stopColor="#ff5a3d" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g className="rk-stars" fill="#dfe5ff">
        <circle cx="22" cy="30" r="1.6" />
        <circle cx="138" cy="22" r="1.3" />
        <circle cx="130" cy="96" r="1.8" />
        <circle cx="30" cy="104" r="1.2" />
        <path d="M118 52v10M113 57h10" stroke="#dfe5ff" strokeWidth="1.4" strokeLinecap="round" />
        <path d="M40 62v8M36 66h8" stroke="#dfe5ff" strokeWidth="1.2" strokeLinecap="round" />
      </g>
      <g className="rk-ship">
        <path className="rk-flame" d="M70 104 Q80 148 90 104 Z" fill="url(#rk-flame)" />
        <path d="M80 12 C98 28 102 58 97 102 H63 C58 58 62 28 80 12 Z" fill="url(#rk-body)" />
        <circle cx="80" cy="54" r="10" fill="#1b2150" stroke="#ffffff" strokeWidth="3.5" />
        <circle cx="76.5" cy="50.5" r="3" fill="#8fa0ff" />
        <path d="M63 76 L46 104 L63 101 Z" fill="#ff7a3d" />
        <path d="M97 76 L114 104 L97 101 Z" fill="#ff7a3d" />
        <path d="M80 80 V103" stroke="#ff7a3d" strokeWidth="5" strokeLinecap="round" />
        <rect x="70" y="100" width="20" height="7" rx="2" fill="#6b73c9" />
      </g>
    </svg>
  )
}
