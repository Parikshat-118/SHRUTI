/**
 * The views an analyst needs - spectrum, waterfall (time-frequency) and
 * constellation - plus the entropy profile that segments header from payload,
 * and the dashboard instruments built from the same data.
 *
 * Hand-written canvas and SVG rather than a chart library, for one reason that
 * matters: **brushing needs sample-accurate coordinates in both directions.**
 * A chart library owns its own pixel mapping and hides it, which is exactly the
 * thing provenance brushing needs access to.  It also keeps the bundle small
 * enough to ship inside an air-gapped folder copy.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useStore, project } from '../lib/store'
import type { ConstellationData, FieldMap, SpectrumData, WaterfallData } from '../lib/types'
import type { Palette } from '../lib/missions'
import { SpinningPlanet } from './Globe'
import { t } from '../lib/i18n'

const GRID = 'rgba(169, 180, 255, 0.09)'
const AXIS = 'rgba(169, 180, 255, 0.32)'
const LABEL = '#e2e4ee'
const TRACE = '#c3caff'
const HILITE = 'rgba(255, 154, 92, 0.22)'
const HILITE_EDGE = '#ff9a5c'
const MONO = '12px ui-monospace, "Cascadia Code", Consolas, monospace'

/** Paint a canvas whenever its deps change or its box is resized. */
function useCanvas(draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, deps: unknown[]) {
  const ref = useRef<HTMLCanvasElement>(null)
  const drawRef = useRef(draw)

  const paint = () => {
    const cv = ref.current
    if (!cv) return
    const dpr = window.devicePixelRatio || 1
    const rect = cv.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) return
    cv.width = Math.floor(rect.width * dpr)
    cv.height = Math.floor(rect.height * dpr)
    const ctx = cv.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, rect.width, rect.height)
    drawRef.current(ctx, rect.width, rect.height)
  }

  useEffect(() => {
    drawRef.current = draw
    paint()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ro = new ResizeObserver(() => paint())
    ro.observe(cv)
    return () => ro.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return ref
}

/** Track an element's content box. */
function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      const r = e.contentRect
      setSize({ w: Math.round(r.width), h: Math.round(r.height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, size] as const
}

function axes(ctx: CanvasRenderingContext2D, w: number, h: number, pad = 28) {
  ctx.strokeStyle = GRID
  ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = pad + ((h - 2 * pad) * i) / 4
    ctx.beginPath()
    ctx.moveTo(pad, y)
    ctx.lineTo(w - 6, y)
    ctx.stroke()
  }
  ctx.strokeStyle = AXIS
  ctx.beginPath()
  ctx.moveTo(pad, pad)
  ctx.lineTo(pad, h - pad)
  ctx.lineTo(w - 6, h - pad)
  ctx.stroke()
}

/** Peak-hold decimation: keeps narrow carriers visible at any width. */
function peakHold(v: number[], n: number): { v: number[]; idx: number[] } {
  if (v.length <= n) return { v, idx: v.map((_, i) => i) }
  const out: number[] = []
  const idx: number[] = []
  const step = v.length / n
  for (let k = 0; k < n; k++) {
    const a = Math.floor(k * step)
    const b = Math.max(a + 1, Math.floor((k + 1) * step))
    let best = a
    for (let i = a; i < b; i++) if (v[i] > v[best]) best = i
    out.push(v[best])
    idx.push(best)
  }
  return { v: out, idx }
}

function fmtHz(f: number) {
  const a = Math.abs(f)
  if (a >= 1e6) return `${(f / 1e6).toFixed(2)} MHz`
  if (a >= 1e3) return `${(f / 1e3).toFixed(2)} kHz`
  return `${f.toFixed(0)} Hz`
}

// ------------------------------------------------------------------- spectrum

export function Spectrum({ data }: { data: SpectrumData }) {
  const ref = useCanvas(
    (ctx, w, h) => {
      const pad = 28
      axes(ctx, w, h, pad)
      const { freq_hz: f, power_db: p } = data
      if (!f.length) return
      let lo = Infinity
      let hi = -Infinity
      for (const v of p) { if (v < lo) lo = v; if (v > hi) hi = v }
      const span = Math.max(hi - lo, 1)
      const X = (i: number) => pad + ((w - pad - 6) * i) / (f.length - 1)
      const Y = (v: number) => h - pad - ((h - 2 * pad) * (v - lo)) / span

      const grad = ctx.createLinearGradient(0, pad, 0, h - pad)
      grad.addColorStop(0, 'rgba(139, 92, 246, 0.45)')
      grad.addColorStop(1, 'rgba(139, 92, 246, 0)')
      ctx.beginPath()
      ctx.moveTo(X(0), h - pad)
      for (let i = 0; i < f.length; i++) ctx.lineTo(X(i), Y(p[i]))
      ctx.lineTo(X(f.length - 1), h - pad)
      ctx.closePath()
      ctx.fillStyle = grad
      ctx.fill()

      ctx.strokeStyle = TRACE
      ctx.lineWidth = 1.2
      ctx.beginPath()
      for (let i = 0; i < f.length; i++) i === 0 ? ctx.moveTo(X(i), Y(p[i])) : ctx.lineTo(X(i), Y(p[i]))
      ctx.stroke()

      ctx.fillStyle = LABEL
      ctx.font = MONO
      ctx.fillText(fmtHz(f[0]), pad, h - 8)
      const right = fmtHz(f[f.length - 1])
      ctx.fillText(right, w - 8 - ctx.measureText(right).width, h - 8)
      ctx.fillText(`${hi.toFixed(0)} dB`, pad + 4, pad - 10)
    },
    [data],
  )
  return <canvas ref={ref} className="plot" role="img" aria-label="Power spectrum" />
}

// ------------------------------------------------------------------ waterfall

/** Magma-like ramp: the sky at night, warming to a hot carrier. */
const RAMP: [number, [number, number, number]][] = [
  [0, [5, 6, 18]], [0.22, [36, 16, 88]], [0.45, [120, 38, 140]],
  [0.66, [214, 72, 96]], [0.84, [252, 150, 84]], [1, [253, 238, 178]],
]
const LUT = (() => {
  const lut = new Uint8ClampedArray(256 * 3)
  for (let i = 0; i < 256; i++) {
    const v = i / 255
    let k = 0
    while (k < RAMP.length - 2 && v > RAMP[k + 1][0]) k++
    const [a, ca] = RAMP[k]
    const [b, cb] = RAMP[k + 1]
    const u = (v - a) / (b - a)
    for (let c = 0; c < 3; c++) lut[i * 3 + c] = ca[c] + (cb[c] - ca[c]) * u
  }
  return lut
})()

export function Waterfall({ data }: { data: WaterfallData }) {
  const selection = useStore((s) => s.selection)
  const pm = useStore((s) => s.result?.plots?.provenance)

  // The image itself only depends on the data; build it once.
  const image = useMemo(() => {
    const { rows, vmin, vmax } = data
    if (!rows.length) return null
    const nf = rows[0].length
    const off = document.createElement('canvas')
    off.width = nf
    off.height = rows.length
    const octx = off.getContext('2d')!
    const img = octx.createImageData(nf, rows.length)
    const span = Math.max(vmax - vmin, 1)
    for (let r = 0; r < rows.length; r++) {
      for (let c = 0; c < nf; c++) {
        const v = Math.max(0, Math.min(1, (rows[r][c] - vmin) / span))
        const li = Math.round(v * 255) * 3
        const o = (r * nf + c) * 4
        img.data[o] = LUT[li]
        img.data[o + 1] = LUT[li + 1]
        img.data[o + 2] = LUT[li + 2]
        img.data[o + 3] = 255
      }
    }
    octx.putImageData(img, 0, 0)
    return off
  }, [data])

  const ref = useCanvas(
    (ctx, w, h) => {
      if (!image) return
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(image, 0, 0, w, h)

      // Provenance highlight: which rows carried the selected samples.
      if (selection && pm) {
        const pr = project(selection, pm)
        const rows = data.rows.length
        const r0 = (pr.sample.start - data.sample_start[0]) / data.hop
        const r1 = (pr.sample.end - data.sample_start[0]) / data.hop
        const y0 = (r0 / rows) * h
        const y1 = (r1 / rows) * h
        if (y1 > 0 && y0 < h) {
          ctx.fillStyle = HILITE
          ctx.fillRect(0, y0, w, Math.max(2, y1 - y0))
          ctx.strokeStyle = HILITE_EDGE
          ctx.lineWidth = 1.5
          ctx.strokeRect(0.75, y0, w - 1.5, Math.max(2, y1 - y0))
        }
      }
    },
    [image, selection, pm],
  )
  return <canvas ref={ref} className="plot waterfall" role="img" aria-label="Waterfall: time on the vertical axis, frequency on the horizontal" />
}

// -------------------------------------------------------------- constellation

export function Constellation({ data }: { data: ConstellationData }) {
  const selection = useStore((s) => s.selection)
  const pm = useStore((s) => s.result?.plots?.provenance)

  const ref = useCanvas(
    (ctx, w, h) => {
      const pad = 16
      const size = Math.min(w, h) - 2 * pad
      const cx = w / 2
      const cy = h / 2
      const scale = size / 2 / 1.6

      ctx.strokeStyle = GRID
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cx - size / 2, cy)
      ctx.lineTo(cx + size / 2, cy)
      ctx.moveTo(cx, cy - size / 2)
      ctx.lineTo(cx, cy + size / 2)
      ctx.stroke()
      ctx.strokeStyle = AXIS
      ctx.beginPath()
      ctx.arc(cx, cy, scale, 0, 2 * Math.PI)
      ctx.stroke()

      let sel: { start: number; end: number } | null = null
      if (selection && pm) sel = project(selection, pm).symbol

      ctx.globalCompositeOperation = 'lighter'
      ctx.fillStyle = 'rgba(169, 180, 255, 0.55)'
      for (let k = 0; k < data.i.length; k++) {
        ctx.beginPath()
        ctx.arc(cx + data.i[k] * scale, cy - data.q[k] * scale, 1.1, 0, 2 * Math.PI)
        ctx.fill()
      }
      ctx.globalCompositeOperation = 'source-over'
      if (sel) {
        ctx.fillStyle = HILITE_EDGE
        for (let k = 0; k < data.i.length; k++) {
          if (data.index[k] < sel.start || data.index[k] >= sel.end) continue
          ctx.beginPath()
          ctx.arc(cx + data.i[k] * scale, cy - data.q[k] * scale, 2.6, 0, 2 * Math.PI)
          ctx.fill()
        }
      }

      ctx.fillStyle = LABEL
      ctx.font = MONO
      ctx.fillText(`${data.n_total.toLocaleString()} symbols`, 6, h - 8)
    },
    [data, selection, pm],
  )
  return <canvas ref={ref} className="plot square" role="img" aria-label="Constellation diagram" />
}

// -------------------------------------------------------- entropy / field map

export const FIELD_COLOURS: Record<string, string> = {
  sync: '#f472b6',
  constant: '#94a3b8',
  counter: '#a78bfa',
  address: '#fbbf24',
  payload: '#34d399',
  padding: '#64748b',
  encrypted_or_compressed: '#f87171',
  unknown: '#7c8aa5',
}

export function EntropyProfile({ fieldmap }: { fieldmap: FieldMap }) {
  const select = useStore((s) => s.select)
  const selection = useStore((s) => s.selection)

  const ref = useCanvas(
    (ctx, w, h) => {
      const pad = 24
      const ent = fieldmap.entropy
      if (!ent.length) return
      axes(ctx, w, h, pad)

      for (const f of fieldmap.fields) {
        const x0 = pad + ((w - pad - 6) * f.start) / ent.length
        const x1 = pad + ((w - pad - 6) * (f.start + f.length)) / ent.length
        ctx.fillStyle = (FIELD_COLOURS[f.kind] ?? '#7c8aa5') + '2e'
        ctx.fillRect(x0, pad, Math.max(1, x1 - x0), h - 2 * pad)
      }

      ctx.strokeStyle = TRACE
      ctx.lineWidth = 1.2
      ctx.beginPath()
      for (let i = 0; i < ent.length; i++) {
        const x = pad + ((w - pad - 6) * i) / Math.max(1, ent.length - 1)
        const y = h - pad - (h - 2 * pad) * Math.max(0, Math.min(1, ent[i]))
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.stroke()

      if (selection?.layer === 'bit') {
        const x0 = pad + ((w - pad - 6) * (selection.start % ent.length)) / ent.length
        const x1 = pad + ((w - pad - 6) * (selection.end % (ent.length + 1))) / ent.length
        ctx.strokeStyle = HILITE_EDGE
        ctx.lineWidth = 2
        ctx.strokeRect(x0, pad, Math.max(2, x1 - x0), h - 2 * pad)
      }

      ctx.fillStyle = LABEL
      ctx.font = MONO
      ctx.fillText('1.0', 2, pad + 8)
      ctx.fillText('0', 8, h - pad)
      ctx.fillText('bit 0', pad, h - 6)
      const last = `bit ${ent.length - 1}`
      ctx.fillText(last, w - 8 - ctx.measureText(last).width, h - 6)
    },
    [fieldmap, selection],
  )

  return (
    <canvas
      ref={ref}
      className="plot clickable"
      role="img"
      aria-label="Entropy per bit position across one frame period. Click a region to select that field."
      onClick={(e) => {
        const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
        const pad = 24
        const frac = (e.clientX - rect.left - pad) / (rect.width - pad - 6)
        const bit = Math.round(frac * fieldmap.entropy.length)
        const f = fieldmap.fields.find((s) => bit >= s.start && bit < s.start + s.length)
        if (f) select({ layer: 'bit', start: f.start, end: f.start + f.length, source: 'entropy' })
      }}
    />
  )
}

// ======================================================= dashboard instruments

/**
 * The constellation, drawn on the body it came from.
 *
 * The IQ constellation is plotted over a planet, and for PSK the ideal points
 * are recovered with the M-th power estimator (arg E[z^M] / M) and joined into
 * the wireframe mesh — the lattice the received cloud is scattered around.
 */
export function ConstellationOrb({
  data, palette, modulation, order,
}: {
  data: ConstellationData
  palette: Palette
  modulation: string
  order: number
}) {
  const selection = useStore((s) => s.selection)
  const pm = useStore((s) => s.result?.plots?.provenance)
  const lang = useStore((s) => s.lang)

  const ref = useCanvas(
    (ctx, w, h) => {
      const R = (Math.min(w, h) * 200) / 520
      const cx = w / 2
      const cy = h / 2
      const n = data.i.length
      if (!n) return

      // Robust scale: the 95th-percentile radius lands at 62% of the body.
      const rad = new Float64Array(n)
      for (let k = 0; k < n; k++) rad[k] = Math.hypot(data.i[k], data.q[k])
      const sorted = Array.from(rad).sort((a, b) => a - b)
      const p95 = sorted[Math.floor(0.95 * (n - 1))] || 1
      const s = (R * 0.62) / p95

      // Instrument window: darken the middle so the cloud reads on a lit body.
      const v = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.92)
      v.addColorStop(0, 'rgba(6, 5, 24, 0.62)')
      v.addColorStop(0.7, 'rgba(6, 5, 24, 0.35)')
      v.addColorStop(1, 'rgba(6, 5, 24, 0)')
      ctx.fillStyle = v
      ctx.beginPath()
      ctx.arc(cx, cy, R * 0.92, 0, Math.PI * 2)
      ctx.fill()

      let sel: { start: number; end: number } | null = null
      if (selection && pm) sel = project(selection, pm).symbol

      ctx.globalCompositeOperation = 'lighter'
      ctx.fillStyle = 'rgba(214, 220, 255, 0.5)'
      for (let k = 0; k < n; k++) {
        ctx.beginPath()
        ctx.arc(cx + data.i[k] * s, cy - data.q[k] * s, 1.05, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalCompositeOperation = 'source-over'

      // Ideal lattice for M-PSK.
      const isPsk = /PSK/i.test(modulation) && !/FSK/i.test(modulation) && order >= 2 && order <= 16
      if (isPsk) {
        let re = 0
        let im = 0
        let r = 0
        for (let k = 0; k < n; k++) {
          const th = Math.atan2(data.q[k], data.i[k]) * order
          re += Math.cos(th)
          im += Math.sin(th)
          r += rad[k]
        }
        const phi = Math.atan2(im, re) / order
        const rr = (r / n) * s
        const pts = Array.from({ length: order }, (_, k) => {
          const a = phi + (2 * Math.PI * k) / order
          return [cx + rr * Math.cos(a), cy - rr * Math.sin(a)] as const
        })
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)'
        ctx.lineWidth = 1
        ctx.beginPath()
        pts.forEach(([x, y], k) => (k === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
        ctx.closePath()
        const hop = order >= 6 ? 3 : 2
        for (let k = 0; k < order; k++) {
          const [x0, y0] = pts[k]
          const [x1, y1] = pts[(k + hop) % order]
          ctx.moveTo(x0, y0)
          ctx.lineTo(x1, y1)
        }
        ctx.stroke()
        for (const [x, y] of pts) {
          ctx.fillStyle = 'rgba(255,255,255,0.95)'
          ctx.beginPath()
          ctx.arc(x, y, 3.2, 0, Math.PI * 2)
          ctx.fill()
          ctx.strokeStyle = 'rgba(255,255,255,0.35)'
          ctx.beginPath()
          ctx.arc(x, y, 9, 0, Math.PI * 2)
          ctx.stroke()
        }
      }

      if (sel) {
        ctx.fillStyle = HILITE_EDGE
        for (let k = 0; k < n; k++) {
          if (data.index[k] < sel.start || data.index[k] >= sel.end) continue
          ctx.beginPath()
          ctx.arc(cx + data.i[k] * s, cy - data.q[k] * s, 2.8, 0, Math.PI * 2)
          ctx.fill()
        }
      }
    },
    [data, selection, pm, modulation, order],
  )

  return (
    <div className="orb">
      <SpinningPlanet palette={palette} seed={palette === 'earth' ? 11 : 5} title={t(lang, 'dragToSpin')} />
      <canvas
        ref={ref}
        className="orb-canvas"
        role="img"
        aria-label={`${modulation} constellation, ${data.n_total} symbols`}
      />
    </div>
  )
}

/** Spectrum as an area chart with a hover readout, for the overview. */
export function SpectrumArea({ data, height = 170 }: { data: SpectrumData; height?: number }) {
  const [box, { w }] = useSize<HTMLDivElement>()
  const n = Math.max(24, Math.min(260, Math.floor(w / 3)))
  const { v, idx } = useMemo(() => peakHold(data.power_db, n), [data, n])
  const peak = useMemo(() => v.reduce((b, x, i) => (x > v[b] ? i : b), 0), [v])
  const [hover, setHover] = useState<number | null>(null)

  const lo = Math.min(...v)
  const hi = Math.max(...v)
  const span = Math.max(hi - lo, 1)
  const top = 34
  const bottom = 22
  const X = (i: number) => (w * i) / Math.max(1, v.length - 1)
  const Y = (x: number) => top + (height - top - bottom) * (1 - (x - lo) / span)

  const line = v.map((x, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(x).toFixed(1)}`).join('')
  const area = `${line}L${w},${height - bottom}L0,${height - bottom}Z`
  const at = hover ?? peak
  const f = data.freq_hz[idx[at]] ?? 0

  return (
    <div className="spec-area" ref={box} style={{ height }}>
      {w > 0 && v.length > 1 && (
        <svg
          width={w} height={height}
          onPointerMove={(e) => {
            const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
            setHover(Math.max(0, Math.min(v.length - 1, Math.round(((e.clientX - r.left) / w) * (v.length - 1)))))
          }}
          onPointerLeave={() => setHover(null)}
          role="img"
          aria-label={`Spectrum from ${fmtHz(data.freq_hz[0])} to ${fmtHz(data.freq_hz[data.freq_hz.length - 1])}, peak ${hi.toFixed(0)} dB`}
        >
          <defs>
            <linearGradient id="specFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#c026d3" stopOpacity=".55" />
              <stop offset=".6" stopColor="#7c3aed" stopOpacity=".18" />
              <stop offset="1" stopColor="#7c3aed" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#specFill)" />
          <path d={line} fill="none" stroke="#e9d5ff" strokeOpacity=".9" strokeWidth="1.4" />
          <line x1={X(at)} x2={X(at)} y1={Y(v[at])} y2={height - bottom} stroke="#fff" strokeOpacity=".35" strokeDasharray="2 3" />
          <circle cx={X(at)} cy={Y(v[at])} r="4.5" fill="#fff" />
          <circle cx={X(at)} cy={Y(v[at])} r="9" fill="none" stroke="#fff" strokeOpacity=".35" />
          <text x="0" y={height - 5} className="axis-text">{fmtHz(data.freq_hz[0])}</text>
          <text x={w} y={height - 5} textAnchor="end" className="axis-text">{fmtHz(data.freq_hz[data.freq_hz.length - 1])}</text>
        </svg>
      )}
      {w > 0 && v.length > 1 && (
        <div
          className="spec-tip"
          style={{ left: Math.max(56, Math.min(w - 56, X(at))), top: Math.max(0, Y(v[at]) - 34) }}
        >
          f = {fmtHz(f)} · {v[at].toFixed(0)} dB
        </div>
      )}
    </div>
  )
}

/** Log-scale bars: how many samples became how many bits. */
export function FunnelBars({ items }: { items: { label: string; value: number }[] }) {
  const decades = [7, 6, 5, 4, 3]
  const frac = (x: number) => Math.max(0.04, Math.min(1, (Math.log10(Math.max(1, x)) - 3) / 4))
  return (
    <div className="funnel">
      <div className="funnel-bars">
        {items.map((it) => (
          <div className="funnel-col" key={it.label}>
            <span className="funnel-val">{compact(it.value)}</span>
            <div className="funnel-track">
              <div className="funnel-bar" style={{ height: `${frac(it.value) * 100}%` }} />
            </div>
            <span className="funnel-label">{it.label}</span>
          </div>
        ))}
      </div>
      <div className="funnel-axis" aria-hidden="true">
        {decades.map((d) => <span key={d}>10<sup>{d}</sup></span>)}
      </div>
    </div>
  )
}

function compact(v: number) {
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}k`
  return String(Math.round(v))
}

/** A ring gauge, as in the reference instrument cluster. */
export function Ring({
  value, label, frac, tone = 'violet', children,
}: {
  value: string
  label: string
  frac: number
  tone?: 'violet' | 'teal' | 'amber' | 'rose'
  children?: ReactNode
}) {
  const r = 38
  const c = 2 * Math.PI * r
  const f = Math.max(0, Math.min(1, frac))
  return (
    <div className={`ring ring-${tone}`}>
      <svg viewBox="0 0 96 96" width="96" height="96" aria-hidden="true">
        <circle cx="48" cy="48" r={r} className="ring-track" />
        <circle
          cx="48" cy="48" r={r} className="ring-value"
          strokeDasharray={`${c * f} ${c}`} transform="rotate(-90 48 48)"
        />
      </svg>
      <div className="ring-text">
        <b>{value}</b>
        <span>{label}</span>
      </div>
      {children}
    </div>
  )
}

/** Thumbnail spectrum for a mission card. */
export function Sparkline({ values, id }: { values: number[]; id: string }) {
  if (values.length < 2) return null
  const w = 300
  const h = 70
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = Math.max(hi - lo, 1)
  const pts = values.map((v, i) => [(w * i) / (values.length - 1), 6 + (h - 8) * (1 - (v - lo) / span)] as const)
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('')
  return (
    <svg className="sparkline" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={`spk-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity=".45" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line}L${w},${h}L0,${h}Z`} fill={`url(#spk-${id})`} />
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
