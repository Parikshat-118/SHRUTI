/**
 * The demo missions: recorded engine runs shipped with the bundle.
 *
 * `scripts/build_demos.py` renders each capture with the twin, analyses it with
 * the real pipeline and writes the exact `/api/analyse` payload here, so the
 * interface can show a complete result with no engine running (the static
 * GitHub Pages tier) and on a machine that has never been online.
 */
import type { AnalysisResult } from './types'

export interface MissionMeta {
  id: string
  title: string
  title_hi: string
  tagline: string
  tagline_hi: string
  band: string
  container: string
  file: string
  centre_hz: number | null
  /** Wall-clock time the recorded engine run took, in seconds. */
  analysis_s: number
  generated: string
  /** Peak-held spectrum of the real capture, in dB, for the card thumbnail. */
  preview: number[]
}

/** Visual identity per mission — which planet it is drawn as. */
export type Palette = 'mars' | 'earth' | 'violet'

export const MISSION_PALETTE: Record<string, Palette> = {
  'deep-space-telemetry': 'mars',
  'hf-data-relay': 'earth',
}

const ROOT = `${import.meta.env.BASE_URL}demos/`
const cache = new Map<string, Promise<AnalysisResult>>()

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${r.status}: could not load ${url}`)
  return r.json() as Promise<T>
}

export interface Catalogue {
  /** Size of the waveform library the missions were analysed against. */
  cartridges: number
  missions: MissionMeta[]
}

export function loadIndex(): Promise<Catalogue> {
  return getJson<Catalogue>(`${ROOT}index.json`)
}

export function loadMission(id: string): Promise<AnalysisResult> {
  let p = cache.get(id)
  if (!p) {
    p = getJson<AnalysisResult>(`${ROOT}${encodeURIComponent(id)}.json`)
    p.catch(() => cache.delete(id))
    cache.set(id, p)
  }
  return p
}
