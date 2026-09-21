/** Typed client for the SHRUTI engine. Same origin in production; Vite proxies in dev. */
import type { AnalysisResult, CartridgeSummary } from './types'

const BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

async function jsonOrThrow<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const detail = await r.text().catch(() => r.statusText)
    throw new Error(`${r.status}: ${detail.slice(0, 300)}`)
  }
  return r.json() as Promise<T>
}

export async function health() {
  return jsonOrThrow<{ status: string; version: string; cartridges: number; offline: boolean }>(
    await fetch(`${BASE}/api/health`),
  )
}

export async function listCartridges() {
  return jsonOrThrow<{ summary: string; errors: string[]; cartridges: CartridgeSummary[] }>(
    await fetch(`${BASE}/api/cartridges`),
  )
}

/** Upload a capture. No sample rate, dtype or centre frequency is asked for. */
export async function analyse(file: File, holdOut?: string): Promise<AnalysisResult> {
  const fd = new FormData()
  fd.append('file', file)
  const q = holdOut ? `?hold_out=${encodeURIComponent(holdOut)}` : ''
  return jsonOrThrow<AnalysisResult>(
    await fetch(`${BASE}/api/analyse${q}`, { method: 'POST', body: fd }),
  )
}

export async function runSelfTest(body: {
  message: string
  seed?: number
  snr_db?: number | null
  hold_out?: string | null
}): Promise<AnalysisResult> {
  return jsonOrThrow<AnalysisResult>(
    await fetch(`${BASE}/api/selftest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

export async function synth(body: {
  cartridge: string
  message: string
  snr_db: number
  cfo_hz: number
  watterson?: string | null
  seed: number
  repeat: number
}) {
  return jsonOrThrow<{
    path: string
    download: string
    data_file: string
    truth: Record<string, unknown>
    summary: string
  }>(
    await fetch(`${BASE}/api/synth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}
