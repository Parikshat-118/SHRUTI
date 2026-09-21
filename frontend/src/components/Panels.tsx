/**
 * The non-plot panels: verdict, container reasoning, measurements, waveform
 * ranking, capability gates, field map and payload.
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
import { useStore, project } from '../lib/store'
import { t } from '../lib/i18n'
import type { AnalysisResult, Capability, FieldMap, Match, Proposal } from '../lib/types'

export function Verdict({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const cls =
    res.verdict === 'IDENTIFIED' ? 'ok' : res.verdict === 'PROBABLE' ? 'warn' : 'bad'
  const best = res.matches[0]
  return (
    <div className={`verdict ${cls}`}>
      <div className="verdict-head">
        <span className="verdict-label">{t(lang, 'verdict')}</span>
        <strong>{res.verdict}</strong>
      </div>
      {best && res.verdict !== 'UNKNOWN' && (
        <div className="verdict-body">
          <div className="big">{best.id}</div>
          <div className="muted">
            {best.reencode_agreement != null && (
              <>
                {t(lang, 'reencode')}{' '}
                <b>{(best.reencode_agreement * 100).toFixed(1)}%</b>
                {' — '}
              </>
            )}
            {best.detail}
          </div>
          <p className="plain">
            The signal was rebuilt from what we recovered and compared against your file.
            The error-correcting code decoded, which it could not have done if any
            measurement had been wrong.
          </p>
        </div>
      )}
      {res.verdict === 'UNKNOWN' && (
        <div className="verdict-body">
          <p>{t(lang, 'unknownHelp')}</p>
          <div className="resolve">
            <b>{t(lang, 'whatWouldResolve')} →</b>
            <ul>
              <li>a longer capture of the same emitter</li>
              <li>a sidecar with the tuned frequency</li>
              <li>
                a cartridge for this waveform family <em>[ author one ]</em>
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

export function ContainerPanel({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const c = res.container
  return (
    <section className="panel">
      <h3>{t(lang, 'container')}</h3>
      <dl className="kv">
        <dt>kind</dt><dd>{c.kind}</dd>
        <dt>format</dt><dd>{c.dtype}, {c.channels}ch</dd>
        <dt>{t(lang, 'sampleRate')}</dt>
        <dd>
          {c.sample_rate ? `${c.sample_rate.toLocaleString()} Hz` : '—'}{' '}
          <span className={`basis ${c.rate_basis === 'NOT IDENTIFIABLE' ? 'bad' : ''}`}>
            {c.rate_basis}
          </span>
        </dd>
        <dt>centre</dt>
        <dd>
          {c.centre_hz ? `${(c.centre_hz / 1e6).toFixed(6)} MHz` : 'unknown'}{' '}
          <span className="basis">{c.centre_basis}</span>
        </dd>
        <dt>samples</dt><dd>{c.n_samples.toLocaleString()}</dd>
      </dl>
      <details className="reasons">
        <summary>{t(lang, 'notes')}</summary>
        <ul>{c.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
      </details>
    </section>
  )
}

export function Measurements({ proposals }: { proposals: Proposal[] }) {
  const lang = useStore((s) => s.lang)
  const resolved = useStore((s) => s.result?.resolved_physical)
  if (!proposals.length) return null
  const p = proposals[0]
  return (
    <section className="panel">
      <h3>{t(lang, 'physical')}</h3>
      {resolved && <p className="summary mono">{resolved}</p>}
      <div className="metric-grid">
        <div className="metric"><span>modulation</span><b>{p.modulation}</b></div>
        <div className="metric"><span>symbol rate</span><b>{p.symbol_rate_bd.toFixed(1)} Bd</b></div>
        <div className="metric"><span>SNR</span><b>{p.snr_db.toFixed(1)} dB</b></div>
        <div className="metric"><span>carrier offset</span><b>{p.cfo_hz >= 0 ? '+' : ''}{p.cfo_hz.toFixed(1)} Hz</b></div>
        <div className="metric"><span>EVM</span><b>{p.evm.toFixed(3)}</b></div>
        <div className="metric"><span>bits / symbol</span><b>{p.bits_per_symbol}</b></div>
      </div>
      {proposals.length > 1 && (
        <details className="reasons">
          <summary>other hypotheses considered</summary>
          <ul>
            {proposals.slice(1).map((q, i) => (
              <li key={i}>{q.modulation} @ {q.symbol_rate_bd.toFixed(1)} Bd (EVM {q.evm.toFixed(3)})</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export function WaveformRanking({ matches }: { matches: Match[] }) {
  const lang = useStore((s) => s.lang)
  if (!matches.length) return null
  return (
    <section className="panel">
      <h3>{t(lang, 'waveform')}</h3>
      <table className="rank">
        <tbody>
          {matches.map((m) => (
            <tr key={m.id} className={m.ok ? 'ok' : ''}>
              <td className="mono">{m.id}</td>
              <td className="num">{m.score.toFixed(1)}</td>
              <td className="num">
                {m.reencode_agreement != null ? `${(m.reencode_agreement * 100).toFixed(1)}%` : '—'}
              </td>
              <td className="muted small">{m.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function Capabilities({ caps }: { caps: Capability[] }) {
  const lang = useStore((s) => s.lang)
  if (!caps.length) return null
  return (
    <section className="panel">
      <h3>{t(lang, 'capabilities')}</h3>
      <ul className="caps">
        {caps.map((c) => (
          <li key={c.name} className={c.available ? 'on' : 'off'}>
            <span className="dot" />
            <span className="cap-name">{c.name.replace(/_/g, ' ')}</span>
            {!c.available && (
              <span className="cap-why">
                needs ≥ {c.required_bits.toLocaleString()} bits, this capture holds{' '}
                {c.have_bits.toLocaleString()}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="footnote">
        Capabilities disable themselves rather than guess. A tool that refuses is a
        tool an analyst can use.
      </p>
    </section>
  )
}

export function FieldTable({ fieldmap }: { fieldmap: FieldMap }) {
  const lang = useStore((s) => s.lang)
  const select = useStore((s) => s.select)
  const selection = useStore((s) => s.selection)
  const pm = useStore((s) => s.result?.plots?.provenance)
  const sel = selection ? project(selection, pm) : null

  return (
    <section className="panel">
      <h3>{t(lang, 'framing')}</h3>
      <p className="summary">{fieldmap.summary}</p>
      <p className="hint">{t(lang, 'selectionHint')}</p>
      <table className="fields">
        <thead>
          <tr><th>bits</th><th>len</th><th>kind</th><th>H</th><th>note</th></tr>
        </thead>
        <tbody>
          {fieldmap.fields.map((f, i) => {
            const active = sel ? sel.bit.start === f.start : false
            return (
              <tr
                key={i}
                className={`${f.kind} ${active ? 'active' : ''}`}
                onClick={() =>
                  select({ layer: 'bit', start: f.start, end: f.start + f.length, source: 'table' })
                }
              >
                <td className="mono">{f.start}–{f.start + f.length - 1}</td>
                <td className="num">{f.length}</td>
                <td>{f.kind.replace(/_/g, ' ')}</td>
                <td className="num">{f.entropy.toFixed(3)}</td>
                <td className="muted small">{f.note}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

export function Payload({ res }: { res: AnalysisResult }) {
  const lang = useStore((s) => s.lang)
  const select = useStore((s) => s.select)
  if (!res.payload) return null
  const bytes = res.payload.hex.match(/.{2}/g)?.slice(0, 512) ?? []
  return (
    <section className="panel">
      <h3>{t(lang, 'payload')}</h3>
      <div className="muted small">{res.payload.n_bits.toLocaleString()} {t(lang, 'bits')}</div>
      <pre className="payload-text">{res.payload.text.slice(0, 600)}</pre>
      <div className="hexdump">
        {bytes.map((b, i) => (
          <span
            key={i}
            onClick={() => select({ layer: 'bit', start: i * 8, end: i * 8 + 8, source: 'hex' })}
            title={`byte ${i} — click to trace back to the samples that carried it`}
          >
            {b}
          </span>
        ))}
      </div>
    </section>
  )
}
