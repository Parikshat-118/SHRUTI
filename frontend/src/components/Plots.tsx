/**
 * The three views an analyst needs - spectrum, waterfall (time-frequency)
 * and constellation - plus the entropy profile that segments header from
 * payload.
 *
 * Hand-written canvas rather than a chart library, for one reason that matters:
 * **brushing needs sample-accurate coordinates in both directions.**  A chart
 * library owns its own pixel mapping and hides it, which is exactly the thing
 * provenance brushing needs access to.  Canvas also keeps the bundle small
 * enough to ship inside an air-gapped folder copy.
 */
import { useEffect, useRef } from 'react'
import { useStore, project } from '../lib/store'
import type { ConstellationData, FieldMap, SpectrumData, WaterfallData } from '../lib/types'

const GRID = '#dce7e3'
const AXIS = '#333333'
const TRACE = '#087f76'
const HILITE = 'rgba(214, 152, 72, 0.23)'
const HILITE_EDGE = '#946019'

function useCanvas(draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, deps: unknown[]) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const dpr = window.devicePixelRatio || 1
    const rect = cv.getBoundingClientRect()
    cv.width = Math.max(1, Math.floor(rect.width * dpr))
    cv.height = Math.max(1, Math.floor(rect.height * dpr))
    const ctx = cv.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, rect.width, rect.height)
    draw(ctx, rect.width, rect.height)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return ref
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

// ------------------------------------------------------------------- spectrum

export function Spectrum({ data }: { data: SpectrumData }) {
  const ref = useCanvas(
    (ctx, w, h) => {
      const pad = 28
      axes(ctx, w, h, pad)
      const { freq_hz: f, power_db: p } = data
      if (!f.length) return
      const lo = Math.min(...p)
      const hi = Math.max(...p)
      const span = Math.max(hi - lo, 1)
      ctx.strokeStyle = TRACE
      ctx.lineWidth = 1.2
      ctx.beginPath()
      for (let i = 0; i < f.length; i++) {
        const x = pad + ((w - pad - 6) * i) / (f.length - 1)
        const y = h - pad - ((h - 2 * pad) * (p[i] - lo)) / span
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.stroke()
      ctx.fillStyle = AXIS
      ctx.font = '12px ui-monospace, monospace'
      ctx.fillText(`${(f[0] / 1e3).toFixed(1)} kHz`, pad, h - 8)
      ctx.fillText(`${(f[f.length - 1] / 1e3).toFixed(1)} kHz`, w - 90, h - 8)
      ctx.fillText(`${hi.toFixed(0)} dB`, pad, pad - 10)
    },
    [data],
  )
  return <canvas ref={ref} className="plot" />
}

// ------------------------------------------------------------------ waterfall

export function Waterfall({ data }: { data: WaterfallData }) {
  const selection = useStore((s) => s.selection)
  const result = useStore((s) => s.result)
  const pm = result?.plots?.provenance

  const ref = useCanvas(
    (ctx, w, h) => {
      const { rows, vmin, vmax } = data
      if (!rows.length) return
      const nf = rows[0].length
      const img = ctx.createImageData(nf, rows.length)
      const span = Math.max(vmax - vmin, 1)
      for (let r = 0; r < rows.length; r++) {
        for (let c = 0; c < nf; c++) {
          const v = Math.max(0, Math.min(1, (rows[r][c] - vmin) / span))
          // viridis-ish ramp: dark blue -> teal -> yellow
          const R = Math.floor(255 * Math.max(0, Math.min(1, 1.6 * v - 0.6)))
          const G = Math.floor(255 * Math.max(0, Math.min(1, 1.3 * v)))
          const B = Math.floor(255 * Math.max(0, Math.min(1, 1.2 - 1.6 * v)))
          const o = (r * nf + c) * 4
          img.data[o] = R
          img.data[o + 1] = G
          img.data[o + 2] = B
          img.data[o + 3] = 255
        }
      }
      const off = document.createElement('canvas')
      off.width = nf
      off.height = rows.length
      off.getContext('2d')!.putImageData(img, 0, 0)
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(off, 0, 0, w, h)

      // Provenance highlight: which rows carried the selected samples.
      if (selection && pm) {
        const pr = project(selection, pm)
        const r0 = (pr.sample.start - data.sample_start[0]) / data.hop
        const r1 = (pr.sample.end - data.sample_start[0]) / data.hop
        const y0 = (r0 / rows.length) * h
        const y1 = (r1 / rows.length) * h
        if (y1 > 0 && y0 < h) {
          ctx.fillStyle = HILITE
          ctx.fillRect(0, y0, w, Math.max(2, y1 - y0))
          ctx.strokeStyle = HILITE_EDGE
          ctx.lineWidth = 1.5
          ctx.strokeRect(0, y0, w, Math.max(2, y1 - y0))
        }
      }
    },
    [data, selection, pm],
  )
  return <canvas ref={ref} className="plot waterfall" />
}

// -------------------------------------------------------------- constellation

export function Constellation({ data }: { data: ConstellationData }) {
  const selection = useStore((s) => s.selection)
  const result = useStore((s) => s.result)
  const pm = result?.plots?.provenance

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
      ctx.beginPath()
      ctx.arc(cx, cy, scale, 0, 2 * Math.PI)
      ctx.stroke()

      let sel: { start: number; end: number } | null = null
      if (selection && pm) sel = project(selection, pm).symbol

      for (let k = 0; k < data.i.length; k++) {
        const inSel = sel ? data.index[k] >= sel.start && data.index[k] < sel.end : false
        ctx.fillStyle = inSel ? HILITE_EDGE : 'rgba(8, 127, 118, 0.65)'
        const r = inSel ? 2.4 : 1.1
        ctx.beginPath()
        ctx.arc(cx + data.i[k] * scale, cy - data.q[k] * scale, r, 0, 2 * Math.PI)
        ctx.fill()
      }

      ctx.fillStyle = AXIS
      ctx.font = '12px ui-monospace, monospace'
      ctx.fillText(`${data.n_total} symbols`, 4, h - 6)
    },
    [data, selection, pm],
  )
  return <canvas ref={ref} className="plot square" />
}

// -------------------------------------------------------- entropy / field map

export function EntropyProfile({ fieldmap }: { fieldmap: FieldMap }) {
  const select = useStore((s) => s.select)
  const selection = useStore((s) => s.selection)

  const ref = useCanvas(
    (ctx, w, h) => {
      const pad = 24
      const ent = fieldmap.entropy
      if (!ent.length) return
      axes(ctx, w, h, pad)

      const colours: Record<string, string> = {
        sync: '#aa4070',
        constant: '#829692',
        counter: '#7553aa',
        address: '#946019',
        payload: '#16704e',
        padding: '#475569',
        encrypted_or_compressed: '#bd4148',
        unknown: '#5d7070',
      }
      for (const f of fieldmap.fields) {
        const x0 = pad + ((w - pad - 6) * f.start) / ent.length
        const x1 = pad + ((w - pad - 6) * (f.start + f.length)) / ent.length
        ctx.fillStyle = (colours[f.kind] ?? '#5d7070') + '33'
        ctx.fillRect(x0, pad, Math.max(1, x1 - x0), h - 2 * pad)
      }

      ctx.strokeStyle = TRACE
      ctx.lineWidth = 1.2
      ctx.beginPath()
      for (let i = 0; i < ent.length; i++) {
        const x = pad + ((w - pad - 6) * i) / (ent.length - 1)
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

      ctx.fillStyle = AXIS
      ctx.font = '12px ui-monospace, monospace'
      ctx.fillText('1.0', 2, pad + 8)
      ctx.fillText('0', 6, h - pad)
      ctx.fillText(`bit 0`, pad, h - 6)
      ctx.fillText(`bit ${ent.length - 1}`, w - 80, h - 6)
    },
    [fieldmap, selection],
  )

  return (
    <canvas
      ref={ref}
      className="plot clickable"
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
