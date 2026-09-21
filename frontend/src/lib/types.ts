/**
 * The contract between the Python engine and this UI.
 *
 * These types mirror `shruti/web/app.py::_result_payload` deliberately and
 * exactly.  Keeping them written down is the reason for choosing TypeScript
 * here: when a layer's output shape changes, the build breaks instead of a
 * panel silently rendering `undefined` in front of an analyst.
 */

export type Verdict = 'IDENTIFIED' | 'PROBABLE' | 'UNKNOWN'

export interface ContainerInfo {
  summary: string
  kind: string
  dtype: string
  channels: number
  sample_rate: number | null
  rate_basis: string
  centre_hz: number | null
  centre_basis: string
  n_samples: number
  /** Why L0 concluded what it concluded — shown, never hidden. */
  reasons: string[]
}

export interface Proposal {
  modulation: string
  order: number
  bits_per_symbol: number
  symbol_rate_bd: number
  sps: number
  evm: number
  snr_db: number
  cfo_hz: number
}

export interface Match {
  id: string
  score: number
  ok: boolean
  detail: string
  reencode_agreement: number | null
  rs_blocks: number
  rs_failed: number
  rs_corrected: number
  ldpc_blocks: number
  ldpc_converged: number
}

/** A capability that grades itself out when the capture is too short. */
export interface Capability {
  name: string
  available: boolean
  required_bits: number
  have_bits: number
  reason: string
}

export interface FrameInfo {
  found: boolean
  period_bits: number
  confidence: number
  n_frames: number
  sync_hex: string
  sync_offset: number
  summary: string
  notes: string[]
}

export type FieldKind =
  | 'sync' | 'constant' | 'counter' | 'address'
  | 'payload' | 'padding' | 'encrypted_or_compressed' | 'unknown'

export interface FieldSpan {
  start: number
  length: number
  kind: FieldKind
  entropy: number
  note: string
}

export interface FieldMap {
  summary: string
  period_bits: number
  header_bits: number
  payload_bits: number
  payload_entropy: number
  looks_encrypted: boolean
  entropy: number[]
  fields: FieldSpan[]
}

export interface SpectrumData { freq_hz: number[]; power_db: number[]; nfft: number }
export interface WaterfallData {
  rows: number[][]
  sample_start: number[]
  freq_hz: number[]
  nfft: number
  hop: number
  vmin: number
  vmax: number
  duration_s: number
}
export interface ConstellationData {
  i: number[]; q: number[]; index: number[]
  n_total: number; decimation: number
}
export interface TimeData { t_s: number[]; magnitude_db: number[]; decimation: number }

/** The linear map bit -> symbol -> sample that makes brushing possible. */
export interface ProvenanceMap {
  bits_per_symbol: number
  samples_per_symbol: number
  sample_offset: number
  n_bits: number
  n_symbols: number
}

export interface Plots {
  spectrum: SpectrumData
  waterfall: WaterfallData
  time: TimeData
  constellation?: ConstellationData
  provenance?: ProvenanceMap
}

export interface AnalysisResult {
  verdict: Verdict
  /** Physical layer as concluded from the decoded waveform, not as first proposed. */
  resolved_physical?: string
  container: ContainerInfo
  proposals: Proposal[]
  matches: Match[]
  capabilities: Capability[]
  frame?: FrameInfo
  fieldmap?: FieldMap
  payload?: { n_bits: number; hex: string; text: string }
  plots?: Plots
  timings: Record<string, number>
  notes: string[]
  selftest?: SelfTestOutcome
}

export interface SelfTestOutcome {
  message: string
  recovered: string
  success: boolean
  hold_out: string | null
  truth: Record<string, unknown>
  transmitter: {
    cartridge_id: string
    snr_db: number
    cfo_hz: number
    timing_offset: number
    watterson: string | null
  }
}

export interface CartridgeSummary {
  id: string
  name: string
  band: string
  digest: string
  description: string
  symbol_rate_bd: number
  blocks: Record<string, Record<string, unknown>>
  identifiability: Record<string, string>
}
