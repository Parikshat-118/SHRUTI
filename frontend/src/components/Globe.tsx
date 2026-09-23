/**
 * A planet that turns.
 *
 * The surface is fractal noise painted once into an equirectangular texture,
 * then mapped onto a sphere pixel by pixel.  Every screen pixel's latitude and
 * longitude are worked out in advance, so a frame is only a texture lookup
 * shifted by the current rotation - a few milliseconds even without a GPU.
 *
 * It turns slowly on its own, and can be spun by dragging it sideways; after a
 * flick it coasts back to its resting speed.
 */
import { useEffect, useRef } from 'react'
import type { Palette } from '../lib/missions'
import { PALETTES, reducedMotion, rng } from './Space'

const TEX_W = 768
const TEX_H = 384
/** Axial tilt towards the viewer, so latitude lines read as ellipses. */
const TILT = 0.24
/** Resting spin, in radians per second: one turn in about forty seconds. */
const SPIN = 0.16
const texCache = new Map<string, Uint8ClampedArray>()

type RGB = [number, number, number]
const hex = (h: string): RGB => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]
const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
const smooth = (a: number, b: number, x: number) => {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

/** Surface colour for a noise value `n` and a polar-ice weight `p`, per body. */
const SURFACE: Record<Palette, (n: number, p: number) => RGB> = {
  mars: (n, p) => {
    let c = mix(hex('#f39a5a'), hex('#c24e1f'), n)
    c = mix(c, hex('#4f1606'), smooth(0.56, 0.82, n) * 0.85)
    return mix(c, hex('#f4e4d8'), p)
  },
  earth: (n, p) => {
    const c = n < 0.53
      ? mix(hex('#0a2f78'), hex('#2f86dd'), n / 0.53)
      : mix(hex('#2f8a55'), hex('#b89c63'), smooth(0.53, 0.8, n))
    return mix(c, hex('#eef6ff'), p)
  },
  violet: (n, p) => {
    let c = mix(hex('#c3c8ff'), hex('#4b41c4'), n)
    c = mix(c, hex('#a15b3a'), smooth(0.6, 0.85, n) * 0.7)
    return mix(c, hex('#f1eeff'), p)
  },
}
/** Latitude band (radians) over which polar ice fades in. */
const ICE: Record<Palette, [number, number]> = { mars: [1.3, 1.42], earth: [1.2, 1.34], violet: [9, 10] }

/** Fractal value noise that wraps in longitude, coloured for the body. */
function surfaceTexture(palette: Palette, seed: number): Uint8ClampedArray {
  const key = `${palette}:${seed}`
  const hit = texCache.get(key)
  if (hit) return hit
  const rand = rng(seed * 7919 + 13)
  const field = new Float32Array(TEX_W * TEX_H)
  let amp = 1
  let total = 0
  for (const gw of [5, 10, 20, 40, 80]) {
    const gh = Math.max(2, Math.round(gw / 2))
    const grid = Float32Array.from({ length: gw * (gh + 1) }, () => rand())
    for (let y = 0; y < TEX_H; y++) {
      const fy = (y / TEX_H) * gh
      const j0 = Math.floor(fy)
      const ty = smooth(0, 1, fy - j0)
      for (let x = 0; x < TEX_W; x++) {
        const fx = (x / TEX_W) * gw
        const i0 = Math.floor(fx)
        const i1 = (i0 + 1) % gw
        const tx = smooth(0, 1, fx - i0)
        const a = grid[j0 * gw + i0]
        const b = grid[j0 * gw + i1]
        const c = grid[(j0 + 1) * gw + i0]
        const d = grid[(j0 + 1) * gw + i1]
        const top = a + (b - a) * tx
        const bot = c + (d - c) * tx
        field[y * TEX_W + x] += amp * (top + (bot - top) * ty)
      }
    }
    total += amp
    amp *= 0.5
  }

  const tex = new Uint8ClampedArray(TEX_W * TEX_H * 3)
  const [ice0, ice1] = ICE[palette]
  const paint = SURFACE[palette]
  for (let y = 0; y < TEX_H; y++) {
    const lat = Math.abs((0.5 - (y + 0.5) / TEX_H) * Math.PI)
    for (let x = 0; x < TEX_W; x++) {
      const raw = field[y * TEX_W + x] / total
      const n = Math.max(0, Math.min(1, (raw - 0.5) * 2.4 + 0.5))
      const c = paint(n, smooth(ice0, ice1, lat + (raw - 0.5) * 0.4))
      const o = (y * TEX_W + x) * 3
      tex[o] = c[0]
      tex[o + 1] = c[1]
      tex[o + 2] = c[2]
    }
  }
  texCache.set(key, tex)
  return tex
}

interface Geometry {
  ctx: CanvasRenderingContext2D
  size: number
  R: number
  dpr: number
  off: HTMLCanvasElement
  octx: CanvasRenderingContext2D
  img: ImageData
  /** Per disk pixel: output offset, texture column, texture row offset, light, edge alpha. */
  n: number
  pix: Int32Array
  col: Int32Array
  row: Int32Array
  shade: Float32Array
  alpha: Uint8Array
}

export function SpinningPlanet({ palette, seed = 5, title }: { palette: Palette; seed?: number; title?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const tex = surfaceTexture(palette, seed)
    const colours = PALETTES[palette]
    const base = reducedMotion() ? 0 : SPIN
    const ct = Math.cos(TILT)
    const st = Math.sin(TILT)

    let rot = 0
    let vel = base
    let dragging = false
    let lastX = 0
    let lastT = 0
    let dirty = true
    let geo: Geometry | null = null

    const build = (): Geometry | null => {
      const rect = cv.getBoundingClientRect()
      if (rect.width < 4) return null
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      cv.width = Math.round(rect.width * dpr)
      cv.height = Math.round(rect.height * dpr)
      const ctx = cv.getContext('2d')!
      const size = Math.min(rect.width, rect.height)
      // Same proportions as the SVG planets: body radius 200 in a 520 box,
      // which is also what the constellation overlay assumes.
      const R = (size * 200) / 520
      const res = Math.max(64, Math.min(640, Math.round(2 * R * dpr)))
      const off = document.createElement('canvas')
      off.width = off.height = res
      const octx = off.getContext('2d')!
      const img = octx.createImageData(res, res)

      const cap = res * res
      const pix = new Int32Array(cap)
      const col = new Int32Array(cap)
      const row = new Int32Array(cap)
      const shade = new Float32Array(cap)
      const alpha = new Uint8Array(cap)
      const lx = -0.55
      const ly = 0.62
      const lz = 0.56
      const ll = Math.hypot(lx, ly, lz)
      let n = 0
      for (let py = 0; py < res; py++) {
        for (let px = 0; px < res; px++) {
          const x = ((px + 0.5) / res) * 2 - 1
          const y = 1 - ((py + 0.5) / res) * 2
          const r = Math.hypot(x, y)
          if (r > 1 + 1 / res) continue
          const z = Math.sqrt(Math.max(0, 1 - r * r))
          // view -> world: undo the tilt towards the viewer
          const yw = y * ct + z * st
          const zw = -y * st + z * ct
          const lat = Math.asin(Math.max(-1, Math.min(1, yw)))
          const lon = Math.atan2(x, zw)
          const lam = Math.max(0, (x * lx + y * ly + z * lz) / ll)
          pix[n] = (py * res + px) * 4
          col[n] = Math.floor(((((lon / (2 * Math.PI)) % 1) + 1) % 1) * TEX_W) % TEX_W
          row[n] = Math.min(TEX_H - 1, Math.floor((0.5 - lat / Math.PI) * TEX_H)) * TEX_W
          shade[n] = 0.14 + 0.98 * lam
          alpha[n] = Math.round(255 * Math.max(0, Math.min(1, (1 - r) * res * 0.5 + 0.5)))
          n++
        }
      }
      dirty = true
      return { ctx, size, R, dpr, off, octx, img, n, pix, col, row, shade, alpha }
    }

    /** World (lat, lon) -> screen, with z > 0 on the near side. */
    const project = (g: Geometry, lat: number, lon: number): [number, number, number] => {
      const cl = Math.cos(lat)
      const xw = cl * Math.sin(lon)
      const yw = Math.sin(lat)
      const zw = cl * Math.cos(lon)
      return [g.size / 2 + xw * g.R, g.size / 2 - (yw * ct - zw * st) * g.R, yw * st + zw * ct]
    }

    const stroke = (g: Geometry, pts: [number, number, number][]) => {
      g.ctx.beginPath()
      let pen = false
      for (const [x, y, z] of pts) {
        if (z > 0.02) {
          if (pen) g.ctx.lineTo(x, y)
          else g.ctx.moveTo(x, y)
          pen = true
        } else {
          pen = false
        }
      }
      g.ctx.stroke()
    }

    const draw = () => {
      const g = geo
      if (!g) return
      const shift = Math.floor(((((rot / (2 * Math.PI)) % 1) + 1) % 1) * TEX_W)
      const d = g.img.data
      for (let i = 0; i < g.n; i++) {
        let u = g.col[i] - shift
        if (u < 0) u += TEX_W
        const t = (g.row[i] + u) * 3
        const s = g.shade[i]
        const p = g.pix[i]
        d[p] = tex[t] * s
        d[p + 1] = tex[t + 1] * s
        d[p + 2] = tex[t + 2] * s
        d[p + 3] = g.alpha[i]
      }
      g.octx.putImageData(g.img, 0, 0)

      const { ctx, size, R, dpr } = g
      const c = size / 2
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, size, size)

      const glow = ctx.createRadialGradient(c, c, R * 0.9, c, c, R * 1.28)
      glow.addColorStop(0, `${colours.glow}8c`)
      glow.addColorStop(1, `${colours.glow}00`)
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(c, c, R * 1.28, 0, Math.PI * 2)
      ctx.fill()

      ctx.imageSmoothingEnabled = true
      ctx.drawImage(g.off, c - R, c - R, 2 * R, 2 * R)

      // The graticule turns with the surface.
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.17)'
      ctx.lineWidth = 1
      for (let k = 0; k < 12; k++) {
        const lon = (k * Math.PI) / 6 + rot
        stroke(g, Array.from({ length: 49 }, (_, i) => project(g, -Math.PI / 2 + (i * Math.PI) / 48, lon)))
      }
      for (const deg of [-60, -30, 0, 30, 60]) {
        const lat = (deg * Math.PI) / 180
        stroke(g, Array.from({ length: 97 }, (_, i) => project(g, lat, (i * 2 * Math.PI) / 96)))
      }

      const rim = ctx.createLinearGradient(c - R, c + R, c + R, c - R)
      rim.addColorStop(0, `${colours.rim}d9`)
      rim.addColorStop(0.35, `${colours.rim}00`)
      ctx.strokeStyle = rim
      ctx.lineWidth = 2.5
      ctx.beginPath()
      ctx.arc(c, c, R - 1.2, 0, Math.PI * 2)
      ctx.stroke()
      dirty = false
    }

    geo = build()
    draw()

    let raf = 0
    let prev = performance.now()
    let visible = true
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      const dt = Math.min(0.1, (now - prev) / 1000)
      if (dt < 1 / 45) return
      prev = now
      if (!visible || document.hidden) return
      if (!dragging) {
        vel += (base - vel) * Math.min(1, dt * 1.2)
        if (Math.abs(vel) > 1e-4) {
          rot += vel * dt
          dirty = true
        }
      }
      if (dirty) draw()
    }
    raf = requestAnimationFrame(loop)

    const ro = new ResizeObserver(() => {
      geo = build()
      draw()
    })
    ro.observe(cv)
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting })
    io.observe(cv)

    // Drag sideways to spin: one radius of drag is about one radian of turn.
    const down = (e: PointerEvent) => {
      dragging = true
      lastX = e.clientX
      lastT = performance.now()
      vel = 0
      cv.setPointerCapture(e.pointerId)
    }
    const move = (e: PointerEvent) => {
      if (!dragging || !geo) return
      const now = performance.now()
      const dth = (e.clientX - lastX) / geo.R
      const dts = Math.max(0.008, (now - lastT) / 1000)
      rot += dth
      vel = vel * 0.6 + (dth / dts) * 0.4
      lastX = e.clientX
      lastT = now
      dirty = true
      if (visible) draw()
    }
    const up = (e: PointerEvent) => {
      dragging = false
      vel = Math.max(-6, Math.min(6, vel))
      if (cv.hasPointerCapture(e.pointerId)) cv.releasePointerCapture(e.pointerId)
    }
    cv.addEventListener('pointerdown', down)
    cv.addEventListener('pointermove', move)
    cv.addEventListener('pointerup', up)
    cv.addEventListener('pointercancel', up)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
      cv.removeEventListener('pointerdown', down)
      cv.removeEventListener('pointermove', move)
      cv.removeEventListener('pointerup', up)
      cv.removeEventListener('pointercancel', up)
    }
  }, [palette, seed])

  return <canvas ref={ref} className="planet-canvas" title={title} aria-hidden="true" />
}
