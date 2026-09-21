/**
 * Shared state, and in particular THE SELECTION.
 *
 * Provenance brushing is the flagship UI idea, and mechanically it is one thing:
 * a single selected range, expressed in whichever layer the user touched, which
 * every view then renders in its own coordinates.  Click a byte in the bitstream
 * and the symbols that carried it light up in the constellation and the samples
 * light up in the waterfall.
 *
 * Keeping that in one store - rather than threading props through four levels of
 * component - is why a state library earns its place in this app.
 */
import { create } from 'zustand'
import type { AnalysisResult, ProvenanceMap } from './types'

export type Layer = 'bit' | 'symbol' | 'sample'

export interface Selection {
  layer: Layer
  start: number
  end: number
  source: string
}

interface State {
  result: AnalysisResult | null
  busy: boolean
  stage: string
  error: string | null
  selection: Selection | null
  lang: 'en' | 'hi'
  setResult: (r: AnalysisResult | null) => void
  setBusy: (b: boolean, stage?: string) => void
  setError: (e: string | null) => void
  select: (s: Selection | null) => void
  setLang: (l: 'en' | 'hi') => void
}

export const useStore = create<State>((set) => ({
  result: null,
  busy: false,
  stage: '',
  error: null,
  selection: null,
  lang: 'en',
  setResult: (result) => set({ result, selection: null, error: null }),
  setBusy: (busy, stage = '') => set({ busy, stage }),
  setError: (error) => set({ error, busy: false }),
  select: (selection) => set({ selection }),
  setLang: (lang) => set({ lang }),
}))

export interface Projected {
  bit: { start: number; end: number }
  symbol: { start: number; end: number }
  sample: { start: number; end: number }
}

/**
 * Convert a selection into every other layer's coordinates.
 *
 * This is the entire provenance mechanism, and it is deliberately arithmetic
 * rather than a lookup table: the chain was modelled end to end, so the mapping
 * between layers is known in closed form.
 */
export function project(sel: Selection, pm?: ProvenanceMap): Projected {
  const bps = Math.max(1, pm?.bits_per_symbol ?? 1)
  const sps = Math.max(1, pm?.samples_per_symbol ?? 1)
  const off = pm?.sample_offset ?? 0

  let bitStart: number
  let bitEnd: number
  switch (sel.layer) {
    case 'bit':
      bitStart = sel.start
      bitEnd = sel.end
      break
    case 'symbol':
      bitStart = sel.start * bps
      bitEnd = sel.end * bps
      break
    default:
      bitStart = Math.floor((sel.start - off) / sps) * bps
      bitEnd = Math.ceil((sel.end - off) / sps) * bps
      break
  }
  const symStart = Math.max(0, Math.floor(bitStart / bps))
  const symEnd = Math.max(symStart + 1, Math.ceil(bitEnd / bps))
  return {
    bit: { start: bitStart, end: bitEnd },
    symbol: { start: symStart, end: symEnd },
    sample: { start: symStart * sps + off, end: symEnd * sps + off },
  }
}
