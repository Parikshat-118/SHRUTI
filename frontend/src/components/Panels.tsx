/**
 * The non-plot panels: ground truth, verdict, container reasoning,
 * measurements, waveform ranking, capability gates, field map and payload.
 *
 * Two of these carry more weight than they look:
 *
 * - **Container reasoning** is shown, never hidden.  Refusing to open with a
 *   "what is your sample rate?" dialogue saves the analyst real time, but only
 *   if the inference is visible and overridable.
 * - **The UNKNOWN panel** is the most important screen in the product.  When
 *   SHRUTI declines it must be the most *useful* screen, not an error: every
 *   measurement it could still make is printed, and the refusal names its own
 *   cure.
 */
import type { ReactNode } from 'react'
import { useStore, project } from '../lib/store'
import { t } from '../lib/i18n'
import { hz, int, pct, printable, signed } from '../lib/format'
import type { AnalysisResult, Capability, FieldMap, Match, Proposal } from '../lib/types'
import { FIELD_COLOURS } from './Plots'
import * as I from './icons'

export function Card({
  title, children, className = '', aside,
}: {
  title: string
  children: ReactNode
  className?: string
  aside?: ReactNode
}) {
  return (
    <section className={`card ${className}`}>
      <header className="card-head">
        <h3>{title}</h3>
        {aside}
      </header>
      {children}
    </section>
  )
}

// --------------------------------------------------------------- ground truth

type Mark = 'ok' | 'bad' | 'info'

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')

/**
 * What the transmitter was configured with, beside what SHRUTI measured
 * without being told.  Only present for recorded missions and self-tests,
 * where the configuration exists to compare against.
 */
export function GroundTruth({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const st = res.selftest
  if (!st) return null
  const truth = st.truth as Record<string, string | number | null>
  const p = res.proposals[0]
  const best = res.matches[0]
  const sps = Number(truth.sps) || p?.sps || 1

  const rows: { k: string; tx: string; rx: string; mark: Mark; note?: string }[] = []
  rows.push({
    k: 'waveform',
    tx: st.transmitter.cartridge_id,
    rx: best && res.verdict !== 'UNKNOWN' ? best.id : '—',
    mark: best && best.id === st.transmitter.cartridge_id && res.verdict !== 'UNKNOWN' ? 'ok' : 'bad',
  })
  if (p) {
    rows.push({
      k: t(lang, 'modulation'),
      tx: String(truth.modulation ?? '—'),
      rx: p.modulation,
      mark: norm(String(truth.modulation ?? '')) === norm(p.modulation) ? 'ok' : 'bad',
    })
    const rs = Number(truth.symbol_rate_bd)
    const ppm = rs ? ((p.symbol_rate_bd - rs) / rs) * 1e6 : NaN
    rows.push({
      k: t(lang, 'symbolRate'),
      tx: `${rs.toLocaleString()} Bd`,
      rx: `${p.symbol_rate_bd.toLocaleString(undefined, { maximumFractionDigits: 3 })} Bd`,
      mark: Math.abs(ppm) < 1000 ? 'ok' : 'bad',
      note: Number.isFinite(ppm) ? `${signed(ppm, 2)} ppm` : undefined,
    })
    const dcfo = p.cfo_hz - st.transmitter.cfo_hz
    rows.push({
      k: t(lang, 'carrierOffset'),
      tx: `${signed(st.transmitter.cfo_hz)} Hz`,
      rx: `${signed(p.cfo_hz, 2)} Hz`,
      mark: Math.abs(dcfo) < Math.max(5, 0.002 * rs) ? 'ok' : 'bad',
      note: `Δ ${signed(dcfo, 2)} Hz`,
    })
    // The twin sets SNR per sample over the whole sample band; L3 measures
    // Es/N0 on matched-filtered symbols.  They differ by 10·log10(sps).
    const inband = st.transmitter.snr_db + 10 * Math.log10(sps)
    rows.push({
      k: t(lang, 'snr'),
      tx: `${st.transmitter.snr_db.toFixed(1)} dB → ${inband.toFixed(1)} dB`,
      rx: `${p.snr_db.toFixed(1)} dB`,
      mark: Math.abs(p.snr_db - inband) < 3 ? 'ok' : 'info',
      note: `full band + 10·log₁₀(${sps}) = in-band`,
    })
  }
  if (res.container.sample_rate && truth.fs) {
    rows.push({
      k: t(lang, 'sampleRate'),
      tx: hz(Number(truth.fs)),
      rx: hz(res.container.sample_rate),
      mark: Math.abs(res.container.sample_rate - Number(truth.fs)) < 1 ? 'ok' : 'bad',
      note: res.container.rate_basis,
    })
  }

  const chain: [string, unknown][] = [
    ['FEC', truth.fec], ['FEC (outer)', truth.fec_outer],
    ['interleaver', truth.interleaver], ['interleaver (outer)', truth.interleaver_outer],
    ['scrambler', truth.scrambler], ['scrambler (post)', truth.scrambler_post],
    ['roll-off', truth.rolloff], ['channel', st.transmitter.watterson ?? 'AWGN'],
  ]
  const shown = chain.filter(([, v]) => v != null && v !== 'none' && v !== '')

  const recovered = printable(st.recovered).slice(0, Math.max(st.message.length + 40, 120))

  return (
    <div className="truth">
      <div className="truth-messages">
        <div className="msg msg-sent">
          <div className="msg-head">
            <span className="msg-dot" />
            {t(lang, 'truthSent')} <em>{t(lang, 'truthSentNote')}</em>
          </div>
          <p>{st.message}</p>
        </div>
        <div className={`msg msg-got ${st.success ? 'ok' : 'bad'}`}>
          <div className="msg-head">
            <span className="msg-dot" />
            {t(lang, 'truthGot')} <em>{t(lang, 'truthGotNote')}</em>
            <span className={`pill ${st.success ? 'pill-ok' : 'pill-bad'}`}>
              {st.success ? <I.Check width={14} height={14} /> : <I.Cross width={14} height={14} />}
              {st.success ? 'PASS' : 'FAIL'}
            </span>
          </div>
          <p className="mono">{recovered}</p>
        </div>
      </div>
      <p className="truth-line">{st.success ? t(lang, 'truthOk') : t(lang, 'truthBad')}</p>

      <div className="truth-grid">
        <Card title={t(lang, 'truthTitle')}>
          <div className="table-wrap">
            <table className="cmp">
              <thead>
                <tr>
                  <th>{t(lang, 'parameter')}</th>
                  <th>{t(lang, 'transmitter')}</th>
                  <th>{t(lang, 'measured')}</th>
                  <th aria-label="check" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.k}>
                    <td className="muted">{r.k}</td>
                    <td className="mono">{r.tx}</td>
                    <td className="mono">
                      {r.rx}
                      {r.note && <span className="cmp-note">{r.note}</span>}
                    </td>
                    <td className={`mark mark-${r.mark}`}>
                      {r.mark === 'ok' ? <I.Check width={16} height={16} aria-label="matches" />
                        : r.mark === 'bad' ? <I.Cross width={16} height={16} aria-label="differs" /> : '≈'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title={t(lang, 'revealed')}>
          <dl className="kv">
            {shown.map(([k, v]) => (
              <div key={k} className="kv-row">
                <dt>{k}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
          </dl>
          <p className="footnote">{t(lang, 'revealedNote')}</p>
        </Card>
      </div>
    </div>
  )
}

// -------------------------------------------------------------------- verdict

export function Verdict({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const cls = res.verdict === 'IDENTIFIED' ? 'ok' : res.verdict === 'PROBABLE' ? 'warn' : 'bad'
  const best = res.matches[0]
  return (
    <div className={`verdict verdict-${cls}`}>
      <div className="verdict-head">
        <span className="eyebrow">{t(lang, 'verdict')}</span>
        <strong>{res.verdict}</strong>
      </div>
      {best && res.verdict !== 'UNKNOWN' && (
        <div className="verdict-body">
          <div className="big mono">{best.id}</div>
          <div className="muted">
            {best.reencode_agreement != null && (
              <>
                {t(lang, 'reencode')} <b>{pct(best.reencode_agreement)}</b>{' — '}
              </>
            )}
            {best.detail}
          </div>
          <p className="plain">{t(lang, 'verdictPlain')}</p>
        </div>
      )}
      {res.verdict === 'UNKNOWN' && (
        <div className="verdict-body">
          <p>{t(lang, 'unknownHelp')}</p>
          <div className="resolve">
            <b>{t(lang, 'whatWouldResolve')} →</b>
            <ul>
              <li>{t(lang, 'resolve1')}</li>
              <li>{t(lang, 'resolve2')}</li>
              <li>{t(lang, 'resolve3')}</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------- the evidence

export function ContainerPanel({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const c = res.container
  return (
    <Card title={t(lang, 'container')}>
      <dl className="kv">
        <div className="kv-row"><dt>{t(lang, 'kind')}</dt><dd>{c.kind}</dd></div>
        <div className="kv-row"><dt>{t(lang, 'format')}</dt><dd>{c.dtype}, {c.channels}ch</dd></div>
        <div className="kv-row">
          <dt>{t(lang, 'sampleRate')}</dt>
          <dd>
            {c.sample_rate ? `${c.sample_rate.toLocaleString()} Hz` : '—'}{' '}
            <span className={`basis ${c.rate_basis === 'NOT IDENTIFIABLE' ? 'bad' : ''}`}>{c.rate_basis}</span>
          </dd>
        </div>
        <div className="kv-row">
          <dt>{t(lang, 'centre')}</dt>
          <dd>
            {c.centre_hz ? `${(c.centre_hz / 1e6).toFixed(6)} MHz` : 'unknown'}{' '}
            <span className="basis">{c.centre_basis}</span>
          </dd>
        </div>
        <div className="kv-row"><dt>{t(lang, 'samples')}</dt><dd>{int(c.n_samples)}</dd></div>
      </dl>
      <details className="reasons" open>
        <summary>{t(lang, 'notes')}</summary>
        <ul>{c.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
      </details>
    </Card>
  )
}

export function Measurements({ proposals }: { proposals: Proposal[] }) {
  const lang = useStore((s) => s.lang)
  const resolved = useStore((s) => s.result?.resolved_physical)
  if (!proposals.length) return null
  const p = proposals[0]
  return (
    <Card title={t(lang, 'physical')}>
      {resolved && <p className="summary mono">{resolved}</p>}
      <div className="metric-grid">
        <div className="metric"><span>{t(lang, 'modulation')}</span><b>{p.modulation}</b></div>
        <div className="metric"><span>{t(lang, 'symbolRate')}</span><b>{p.symbol_rate_bd.toFixed(1)} Bd</b></div>
        <div className="metric"><span>{t(lang, 'snr')}</span><b>{p.snr_db.toFixed(1)} dB</b></div>
        <div className="metric"><span>{t(lang, 'carrierOffset')}</span><b>{signed(p.cfo_hz)} Hz</b></div>
        <div className="metric"><span>{t(lang, 'evm')}</span><b>{p.evm.toFixed(3)}</b></div>
        <div className="metric"><span>{t(lang, 'bitsPerSymbol')}</span><b>{p.bits_per_symbol}</b></div>
      </div>
      {proposals.length > 1 && (
        <details className="reasons">
          <summary>{t(lang, 'otherHypotheses')}</summary>
          <ul>
            {proposals.slice(1).map((q, i) => (
              <li key={i}>{q.modulation} @ {q.symbol_rate_bd.toFixed(1)} Bd (EVM {q.evm.toFixed(3)})</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  )
}

export function WaveformRanking({ matches }: { matches: Match[] }) {
  const lang = useStore((s) => s.lang)
  if (!matches.length) return null
  const top = Math.max(...matches.map((m) => Math.abs(m.score)), 1)
  return (
    <Card title={t(lang, 'waveform')} className="span-2">
      <div className="table-wrap">
        <table className="rank">
          <tbody>
            {matches.map((m, i) => (
              <tr key={m.id} className={i === 0 && m.ok ? 'lead' : ''}>
                <td className="mono">{m.id}</td>
                <td className="rank-bar">
                  <span style={{ width: `${Math.max(2, (Math.max(0, m.score) / top) * 100)}%` }} />
                </td>
                <td className="num">{m.score.toFixed(1)}</td>
                <td className="num">{pct(m.reencode_agreement)}</td>
                <td className="muted small">{m.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function Capabilities({ caps }: { caps: Capability[] }) {
  const lang = useStore((s) => s.lang)
  if (!caps.length) return null
  return (
    <Card title={t(lang, 'capabilities')}>
      <ul className="caps">
        {caps.map((c) => (
          <li key={c.name} className={c.available ? 'on' : 'off'}>
            <span className="dot" />
            <span className="cap-name">{c.name.replace(/_/g, ' ')}</span>
            <span className="cap-bits mono">{int(c.required_bits)}</span>
            {!c.available && (
              <span className="cap-why">
                {t(lang, 'needs')} {int(c.required_bits)} {t(lang, 'holds')} {int(c.have_bits)}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="footnote">{t(lang, 'capFootnote')}</p>
    </Card>
  )
}

export function Timings({ timings }: { timings: Record<string, number> }) {
  const lang = useStore((s) => s.lang)
  const order = ['loaded', 'proposals', 'shortlist', 'match', 'framing', 'done']
  const keys = order.filter((k) => k in timings)
  if (keys.length < 2) return null
  const steps = keys.slice(1).map((k, i) => ({ k, dt: Math.max(0, timings[k] - timings[keys[i]]) }))
  const total = timings[keys[keys.length - 1]] || 1
  return (
    <Card title={t(lang, 'timings')} aside={<span className="muted mono small">{total.toFixed(1)} s</span>}>
      <div className="timeline" role="img" aria-label="Share of analysis time per stage">
        {steps.map((s) => (
          <span key={s.k} className={`seg seg-${s.k}`} style={{ flexGrow: Math.max(s.dt, total * 0.012) }} title={`${s.k} ${s.dt.toFixed(2)} s`} />
        ))}
      </div>
      <ul className="timeline-legend">
        {steps.map((s) => (
          <li key={s.k}><span className={`seg-dot seg-${s.k}`} />{s.k}<b className="mono">{s.dt.toFixed(2)} s</b></li>
        ))}
      </ul>
    </Card>
  )
}

// ------------------------------------------------------------------ the bits

export function FieldTable({ fieldmap }: { fieldmap: FieldMap }) {
  const lang = useStore((s) => s.lang)
  const select = useStore((s) => s.select)
  const selection = useStore((s) => s.selection)
  const pm = useStore((s) => s.result?.plots?.provenance)
  const sel = selection ? project(selection, pm) : null

  return (
    <Card title={t(lang, 'framing')}>
      <p className="summary">{fieldmap.summary}</p>
      <p className="hint">{t(lang, 'selectionHint')}</p>
      <div className="table-wrap scroll-y">
        <table className="fields">
          <thead>
            <tr><th>bits</th><th>len</th><th>{t(lang, 'kind')}</th><th>H</th><th>note</th></tr>
          </thead>
          <tbody>
            {fieldmap.fields.map((f, i) => {
              const active = sel ? sel.bit.start === f.start : false
              return (
                <tr
                  key={i}
                  className={active ? 'active' : ''}
                  tabIndex={0}
                  onClick={() => select({ layer: 'bit', start: f.start, end: f.start + f.length, source: 'table' })}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      select({ layer: 'bit', start: f.start, end: f.start + f.length, source: 'table' })
                    }
                  }}
                >
                  <td className="mono">{f.start}–{f.start + f.length - 1}</td>
                  <td className="num">{f.length}</td>
                  <td><span className="kind" style={{ color: FIELD_COLOURS[f.kind] }}>{f.kind.replace(/_/g, ' ')}</span></td>
                  <td className="num">{f.entropy.toFixed(3)}</td>
                  <td className="muted small">{f.note}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function Payload({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const select = useStore((s) => s.select)
  const selection = useStore((s) => s.selection)
  if (!res.payload) return null
  const bytes = res.payload.hex.match(/.{2}/g)?.slice(0, 512) ?? []
  const selByte = selection?.layer === 'bit' && selection.source === 'hex' ? selection.start / 8 : -1
  return (
    <Card
      title={t(lang, 'payload')}
      aside={<span className="muted small mono">{int(res.payload.n_bits)} {t(lang, 'bits')}</span>}
    >
      <pre className="payload-text">{printable(res.payload.text.slice(0, 600))}</pre>
      <div className="hexdump">
        {bytes.map((b, i) => (
          <button
            type="button"
            key={i}
            className={i === selByte ? 'on' : ''}
            onClick={() => select({ layer: 'bit', start: i * 8, end: i * 8 + 8, source: 'hex' })}
            title={`byte ${i} — ${t(lang, 'byteHint')}`}
          >
            {b}
          </button>
        ))}
      </div>
    </Card>
  )
}
